"""Admin-only Lex research health: per-jurisdiction retrieval success, AI-discovery use, Tavily use, latency, cost per
answer by tier, the jurisdiction coverage register, and the queue of official-source changes awaiting review."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import global_law
import national_law


class Review(BaseModel):
    outcome: str  # no_guidance_affected | guidance_flagged_for_lawyer


class Toggle(BaseModel):
    enabled: bool


def coverage_register() -> list:
    rows = []
    for j, name in global_law.NAMES.items():
        c = global_law.coverage(j)
        src = {"GB": "legislation.gov.uk API (official)", "US": "govinfo.gov U.S. Code + eCFR (federal); state law via official "
               "legislature-site search"}.get(j) or (national_law.SOURCE_NAME.get(j) if c == "verified" else
                                                      ", ".join(global_law.SITE_DOMAINS.get(j, [])) or "none")
        if j == "FR" and c != "verified":
            src = "Légifrance API built — waiting for LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET; until then legifrance.gouv.fr site search"
        topics = sorted(national_law.MAP.get(j, {}).keys())
        n = sum(len(v) for v in national_law.MAP.get(j, {}).values())
        if j == "GB":
            import legal_research
            topics, n = [t[0] for t in legal_research.TOPICS], sum(len(t[2]) for t in legal_research.TOPICS)
        rows.append({"code": j, "name": name, "coverage": c, "sources": src, "mapped_topics": topics, "mapped_provisions": n})
    return rows


def build_router(db, require_admin) -> APIRouter:
    r = APIRouter()

    @r.get("/admin/lex-research/health")
    async def health(days: int = 30, admin: dict = Depends(require_admin)):
        since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 180)))
        by_j = {}
        async for m in db.research_metrics.find({"created_at": {"$gte": since}}, {"_id": 0}):
            j = m.get("primary") or "GB"
            b = by_j.setdefault(j, {"questions": 0, "with_official_sources": 0, "national_refs_tried": 0,
                                    "national_refs_retrieved": 0, "ai_discovery_used": 0, "ai_refs_suggested": 0,
                                    "ai_refs_confirmed": 0, "tavily_calls": 0, "cross_border": 0, "total_ms": 0})
            b["questions"] += 1
            b["with_official_sources"] += 1 if m.get("official_count") else 0
            b["national_refs_tried"] += m.get("det_refs", 0)
            b["national_refs_retrieved"] += m.get("det_ok", 0)
            b["ai_discovery_used"] += 1 if m.get("ai_used") else 0
            b["ai_refs_suggested"] += m.get("ai_refs", 0)
            b["ai_refs_confirmed"] += m.get("ai_verified", 0)
            b["tavily_calls"] += m.get("tavily_calls", 0) + m.get("uk_paid_calls", 0)
            b["cross_border"] += 1 if m.get("cross_border") else 0
            b["total_ms"] += m.get("total_ms", 0)
        for b in by_j.values():
            q = b["questions"] or 1
            b["avg_research_ms"] = int(b.pop("total_ms") / q)
            b["official_source_rate"] = round(b["with_official_sources"] / q, 3)
            b["ai_discovery_rate"] = round(b["ai_discovery_used"] / q, 3)
            b["citation_verification_failures"] = b["ai_refs_suggested"] - b["ai_refs_confirmed"]
        cost = {}
        pipe = [{"$match": {"ts": {"$gte": since.isoformat()}, "feature": {"$in": ["lex_chat", "lex_stream"]}}},
                {"$group": {"_id": {"r": "$request_id", "t": "$tier"}, "c": {"$sum": "$cost_gbp"}}},
                {"$group": {"_id": "$_id.t", "answers": {"$sum": 1}, "avg": {"$avg": "$c"}, "total": {"$sum": "$c"}}}]
        async for row in db.llm_usage.aggregate(pipe):
            cost[row["_id"] or "unknown"] = {"answers": row["answers"], "avg_cost_gbp_per_answer": round(row["avg"] or 0, 5),
                                             "total_gbp": round(row["total"] or 0, 4)}
        disc = await db.llm_usage.aggregate([{"$match": {"ts": {"$gte": since.isoformat()}, "call_site": "global_research_discovery"}},
                                             {"$group": {"_id": None, "n": {"$sum": 1}, "gbp": {"$sum": "$cost_gbp"}}}]).to_list(1)
        tav = await db.llm_usage.aggregate([{"$match": {"ts": {"$gte": since.isoformat()}, "provider": "tavily"}},
                                            {"$group": {"_id": "$status", "n": {"$sum": 1}, "gbp": {"$sum": "$cost_gbp"}}}]).to_list(5)
        return {"days": days, "by_jurisdiction": by_j, "ai_cost_per_answer_by_tier": cost,
                "ai_discovery": {"calls": disc[0]["n"] if disc else 0, "cost_gbp": round(disc[0]["gbp"], 4) if disc else 0},
                "tavily": {row["_id"]: {"calls": row["n"], "cost_gbp": round(row["gbp"] or 0, 4)} for row in tav},
                "source_changes_awaiting_review": await db.legal_source_changes.count_documents({"status": "needs_review"}),
                "ai_discovery_enabled": await global_law._discovery_enabled(db)}

    @r.get("/admin/lex-research/coverage")
    async def coverage(admin: dict = Depends(require_admin)):
        return {"jurisdictions": coverage_register(), "france_keys_configured": national_law.france_enabled()}

    @r.get("/admin/lex-research/source-changes")
    async def changes(status: str = "needs_review", admin: dict = Depends(require_admin)):
        rows = await db.legal_source_changes.find({"status": status}).sort("detected_at", -1).to_list(200)
        return {"items": [{**{k: v for k, v in x.items() if k != "_id"}, "id": str(x["_id"])} for x in rows]}

    @r.post("/admin/lex-research/source-changes/{cid}/review")
    async def review(cid: str, body: Review, admin: dict = Depends(require_admin)):
        from bson import ObjectId
        if body.outcome not in ("no_guidance_affected", "guidance_flagged_for_lawyer"):
            raise HTTPException(400, "Unknown outcome")
        res = await db.legal_source_changes.update_one(
            {"_id": ObjectId(cid)}, {"$set": {"status": "reviewed", "outcome": body.outcome, "reviewed_by": admin["email"],
                                              "reviewed_at": datetime.now(timezone.utc).isoformat(),
                                              "professional_approval": False}})
        if not res.matched_count:
            raise HTTPException(404, "Not found")
        return {"ok": True}

    @r.post("/admin/lex-research/ai-discovery")
    async def toggle(body: Toggle, admin: dict = Depends(require_admin)):
        await db.app_settings.update_one({"_id": global_law.SETTINGS_ID},
                                         {"$set": {"enabled": body.enabled, "updated_by": admin["email"],
                                                   "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"enabled": body.enabled}

    return r
