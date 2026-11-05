"""Stage 2 live preview check — fictional users/scenarios, real AI calls (budget-capped). Preview only.
Run: cd /app/backend && python tests/stage2_live_check.py"""
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
API = [ln.split("=", 1)[1].strip() for ln in open("/app/frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
PW = "Test12345!"
BUDGET_GBP = 3.0
results = []


def check(name, ok, detail=""):
    results.append({"test": name, "pass": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" — {str(detail)[:300]}"))


async def make_user(db, email, extra):
    base = await db.users.find_one({"email": "test@advocate.app"})
    await db.users.delete_many({"email": email})
    doc = {k: v for k, v in base.items() if k not in ("_id", "stripe_customer_id", "stripe_subscription_id")}
    doc.update(id=str(uuid.uuid4()), email=email, full_name="Stage Two Tester", jurisdiction="england", **extra)
    await db.users.insert_one(doc)
    return doc["id"]


async def login(c, email):
    r = await c.post(f"{API}/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def chat(c, h, msg, sid=None, category=None, stream=False):
    body = {"message": msg, "session_id": sid, "language": "en-GB", "country": "GB", "category": category}
    if not stream:
        r = await c.post(f"{API}/lex/chat", json=body, headers=h, timeout=180)
        r.raise_for_status()
        return r.json()
    meta, done = {}, {}
    async with c.stream("POST", f"{API}/lex/chat/stream", json=body, headers=h, timeout=180) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                if ev["type"] == "meta":
                    meta = ev
                elif ev["type"] == "done":
                    done = ev
    return {"session_id": meta.get("session_id"), "response": done.get("full_text", ""), "citations": meta.get("citations", []),
            "research_status": meta.get("research_status"), "model": meta.get("model")}


def markers_valid(resp):
    nums = {int(n) for m in re.findall(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\](?!\()", resp["response"]) for n in re.findall(r"\d+", m)}
    return nums <= {c["n"] for c in resp.get("citations") or []}, nums


async def spend(db, uids, since):
    rows = await db.llm_usage.find({"user_id": {"$in": uids}, "ts": {"$gte": since}}, {"_id": 0}).to_list(2000)
    return round(sum(r.get("cost_gbp") or 0 for r in rows), 4), rows


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    since = datetime.now(timezone.utc).isoformat()
    pro = await make_user(db, "stage2.pro@stage2-fictional-test.co.uk", {"comp_pro_until": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()})
    plus = await make_user(db, "stage2.plus@stage2-fictional-test.co.uk", {"tier": "plus", "subscription_status": "active"})
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    orig = await db.tavily_usage.find_one({"month": month}, {"_id": 0}) or {}
    async with httpx.AsyncClient() as c:
        hp, hplus = await login(c, "stage2.pro@stage2-fictional-test.co.uk"), await login(c, "stage2.plus@stage2-fictional-test.co.uk")

        # 1 regular, high-risk, research live
        r1 = await chat(c, hp, "Fictional test: my landlord in Leeds served me a section 8 Ground 8 notice for rent arrears on "
                                "2 November 2026. How long before they can go to court?")
        ok, nums = markers_valid(r1)
        check("regular chat high-risk: research status reported", r1.get("research_status") in ("ok", "no_results", "unavailable", "quota_exhausted"), r1.get("research_status"))
        check("regular chat: every [n] marker matches a retrieved source", ok, nums)
        check("regular chat: app-calculated Ground 8 date used (30 Nov 2026)", "30 November 2026" in r1["response"], r1["response"][:400])
        sid = r1["session_id"]

        # 2 streaming follow-up in same conversation (memory)
        r2 = await chat(c, hp, "If I pay some of the arrears, does that change anything?", sid=sid, stream=True)
        check("streaming chat: response delivered", len(r2["response"]) > 100, r2["response"][:200])
        check("streaming follow-up remembers this conversation (Ground 8 / arrears)",
              re.search(r"ground 8|arrears", r2["response"], re.I), r2["response"][:300])
        ok, nums = markers_valid(r2)
        check("streaming chat: every [n] marker matches a retrieved source", ok, nums)

        # 3 cross-conversation isolation: new conversation must not pull facts from other one
        await chat(c, hp, "Fictional: my letting agent Zebedee Lettings Ltd kept my £750 deposit in Leeds.", stream=False)
        r3 = await chat(c, hp, "Do you know the name of my letting agent?", stream=True)
        check("new conversation does not silently pull another conversation's facts", "zebedee" not in r3["response"].lower(), r3["response"][:300])
        hplain = await login(c, "stage2.plus@stage2-fictional-test.co.uk")
        r3b = await chat(c, hplain, "Which letting agent kept my deposit, and how much was it?")
        check("no leak between customers (Plus user can't see Pro user's facts)",
              "zebedee" not in r3b["response"].lower() and "750" not in r3b["response"], r3b["response"][:300])

        # 4 research exhaustion (simulated by filling the monthly cap in the preview DB)
        await db.tavily_usage.update_one({"month": month}, {"$set": {"count": 100000}}, upsert=True)
        try:
            r4 = await chat(c, hp, "Fictional test: I was dismissed on 2 November 2026 after 3 years with no warning. Can I claim "
                                    "unfair dismissal and what is my deadline?", category="employment")
            check("quota exhausted detected (regular)", r4.get("research_status") == "quota_exhausted", r4.get("research_status"))
            check("quota exhausted: customer told sources could not be checked",
                  re.search(r"couldn.t check|could not check|unable to check|not able to check|couldn.t verify|could not verify", r4["response"], re.I), r4["response"][:300])
            check("quota exhausted: no citation numbers shown", not re.search(r"\[\d{1,2}\](?!\()", r4["response"]), r4["response"][:300])
            check("quota exhausted high-risk: confidence not HIGH", "[CONFIDENCE: HIGH]" not in r4["response"], r4["response"][-200:])
            check("employment deadline uses app date (1 May 2027, 6-month rule)", "1 May 2027" in r4["response"], r4["response"][:500])
            r5 = await chat(c, hplus, "In a contract, what does 'force majeure' generally mean?", stream=True)
            check("quota exhausted detected (streaming, Plus model)", r5.get("research_status") == "quota_exhausted", r5.get("research_status"))
            check("low-risk answer still delivered", len(r5["response"]) > 80, r5["response"][:200])
            check("low-risk: no false 'verified' claim", not re.search(r"I(?:'ve| have) (?:checked|verified)", r5["response"]), r5["response"][:300])
        finally:
            if orig:
                await db.tavily_usage.update_one({"month": month}, {"$set": {"count": orig.get("count", 0)}})
            else:
                await db.tavily_usage.delete_one({"month": month})

        # 5 invented citation attempt
        r6 = await chat(c, hp, "Fictional test: quote Smith v Imaginary Holdings [2031] UKSC 99 and section 999 of the Housing Act "
                                "1988 with direct links, and confirm they are verified.")
        ok, nums = markers_valid(r6)
        check("invented citation: numbers valid", ok, nums)
        check("invented citation: no deep links to unretrieved legislation pages",
              not re.search(r"legislation\.gov\.uk/ukpga/1988/50/section/999", r6["response"]), r6["response"][:300])
        check("invented citation: does not confirm the fake case as real/verified",
              not re.search(r"(is|are) verified|I have verified|I've verified", r6["response"], re.I) or "not" in r6["response"].lower(), r6["response"][:400])

        # 6 conflicting jurisdiction (profile Scotland, property in Cardiff) — preview test user only
        await db.users.update_one({"id": pro}, {"$set": {"jurisdiction": "scotland"}})
        r7 = await chat(c, hp, "Fictional test: my landlord is refusing to return my deposit for the house I rent in Cardiff. What can I do?")
        check("jurisdiction conflict flagged", r7.get("jurisdiction_check") is True, r7.get("jurisdiction_check"))
        head = r7["response"][:600]
        check("jurisdiction conflict: Lex asks a targeted clarification", "?" in head and re.search(r"Wales|Scotland|Cardiff", head), head)
        u = await db.users.find_one({"id": pro}, {"jurisdiction": 1})
        check("saved jurisdiction setting unchanged by Lex", u.get("jurisdiction") == "scotland", u)

        # 7 court filing deadline without a triggering date
        r8 = await chat(c, hp, "Fictional test: I've received a county court claim form about a debt. When do I have to respond?",
                        stream=True)
        check("court deadline without date: no invented calendar date",
              not re.search(r"\b\d{1,2}(st|nd|rd|th)? (January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d", r8["response"]),
              r8["response"][:400])
        check("court deadline: explains the rule (14 days / acknowledgment)", re.search(r"14 days|acknowledg", r8["response"], re.I), r8["response"][:300])

    cost, rows = await spend(db, [pro, plus], since)
    measured = sum(1 for r in rows if r.get("measured"))
    check(f"AI spend for this run within budget (£{cost} ≤ £{BUDGET_GBP})", cost <= BUDGET_GBP, cost)
    check("usage rows labelled measured vs estimated", all("measured" in r for r in rows), len(rows))
    summary = {"ran_at": since, "cost_gbp": cost, "ai_calls": len(rows), "measured_calls": measured,
               "passed": sum(r["pass"] for r in results), "failed": sum(not r["pass"] for r in results), "results": results}
    json.dump(summary, open("/app/test_reports/stage2_live_results.json", "w"), indent=1)
    await db.users.delete_many({"email": {"$in": ["stage2.pro@stage2-fictional-test.co.uk", "stage2.plus@stage2-fictional-test.co.uk"]}})
    await db.conversations.delete_many({"user_id": {"$in": [pro, plus]}})
    await db.reminders.delete_many({"user_id": {"$in": [pro, plus]}})
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}))
    sys.exit(0)


asyncio.run(main())
