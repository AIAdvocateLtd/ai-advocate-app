"""
AI Advocate — Partner Programme module
======================================

Encapsulates everything needed to run the B2B referral programme:
  • Partner directory (councils, CABs, housing assocs, charities)
  • Referral attribution (?ref=CODE captured at signup)
  • Monthly commission accrual with cap enforcement
       — 10% of Year 1 revenue
       — capped at £40 per referred user (lifetime)
  • Admin endpoints (list partners, view ledger, generate quarterly payout CSV, mark paid)

DESIGN NOTES
------------
- Tiers' subscription prices (in GBP) are hard-coded mirrors of the marketing
  copy. Update both places if pricing ever changes.
- The accrual job is idempotent: a unique compound index on
  (partner_id, user_id, period) prevents double-crediting if the cron fires twice.
- £40 cap is enforced by summing the user's lifetime accrued amount BEFORE
  inserting the new period's row. Once cap is reached the user is permanently
  closed for that partner.
- 12-month window: a user's signup date + 365d. Once passed, no more credits.
"""
from __future__ import annotations

import csv
import io
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# B2B subscription tier price IDs (Stripe LIVE mode)
# ---------------------------------------------------------------------------
# Live Stripe Price IDs for the partner-facing subscription tiers shown on
# /for-organisations. The /api/partners/checkout endpoint in server.py maps
# the tier slug here to the Stripe price the partner is charged.
#
# Update these only if the underlying Stripe product/price changes.
PARTNER_TIER_PRICES = {
    "pilot":      {"price_id": "price_1TktQXFh8lRHrXPI5gSJ1SBm", "label": "Partner Pilot",      "gbp": 99},
    "union":      {"price_id": "price_1TktToFh8lRHrXPIKxugJUzF", "label": "Partner Union",      "gbp": 249},
    "council":    {"price_id": "price_1TktVVFh8lRHrXPIHKyfIi2b", "label": "Partner Council",    "gbp": 499},
    "enterprise": {"price_id": "price_1TktZ0Fh8lRHrXPIpA3P5c8P", "label": "Partner Enterprise", "gbp": 1999},
}


# Subscription prices (GBP/month). Mirror of marketing copy.
TIER_MONTHLY_PRICE_GBP = {
    "plus": 19.99,
    "pro": 34.99,
    "trial_pro": 0.0,         # No charge during trial → no commission
    "yearly": 26.66,          # 319.99 / 12 averaged
}
COMMISSION_RATE = 0.10           # 10%
CAP_PER_USER_GBP = 40.00         # Lifetime cap per referred user
COMMISSION_WINDOW_DAYS = 365     # Only credit during Year 1 from signup


# ---------------- Pydantic models ----------------

class PartnerCreate(BaseModel):
    code: str               # short, uppercase, no spaces (e.g. "LAMBETH-CAB")
    name: str               # public name ("Lambeth Citizens Advice")
    contact_name: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    payout_method: str = "bacs"      # bacs | future: stripe_connect
    payout_bank_name: Optional[str] = None
    payout_sort_code: Optional[str] = None    # XX-XX-XX
    payout_account_number: Optional[str] = None  # 8 digits
    notes: Optional[str] = None


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    payout_method: Optional[str] = None
    payout_bank_name: Optional[str] = None
    payout_sort_code: Optional[str] = None
    payout_account_number: Optional[str] = None
    status: Optional[str] = None      # active | paused | terminated
    notes: Optional[str] = None


class MarkPaidPayload(BaseModel):
    period_keys: list[str]                # ["2026-01","2026-02","2026-03"]
    reference: Optional[str] = None       # BACS reference / payment date
    amount_gbp: Optional[float] = None    # Optional override (else uses ledger sum)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _period_key(dt: datetime) -> str:
    """YYYY-MM for the calendar month."""
    return dt.strftime("%Y-%m")


# ---------------- Monthly accrual job ----------------

async def accrue_partner_commissions(db, period_key: Optional[str] = None) -> dict:
    """Walk every active paying user with a partner_code; credit 10% of their
    tier price to that partner's ledger for the given period. Returns a summary.

    Safe to call multiple times — duplicates blocked by unique index on
    (partner_id, user_id, period_key).
    """
    if not period_key:
        period_key = _period_key(datetime.now(timezone.utc))

    # Ensure the unique index exists (idempotency)
    try:
        await db.partner_commissions.create_index(
            [("partner_id", 1), ("user_id", 1), ("period_key", 1)],
            unique=True,
            name="uniq_partner_user_period",
        )
    except Exception as e:
        logger.debug(f"index create note: {e}")

    summary = {
        "period_key": period_key,
        "processed_users": 0,
        "credits_inserted": 0,
        "skipped_capped": 0,
        "skipped_expired": 0,
        "skipped_unknown_partner": 0,
        "skipped_duplicate": 0,
        "total_credited_gbp": 0.0,
    }

    users_cursor = db.users.find(
        {
            "partner_code": {"$ne": None, "$exists": True},
            "tier": {"$in": list(TIER_MONTHLY_PRICE_GBP.keys())},
            "subscription_status": {"$in": ["active", "trialing", "past_due", None]},
        },
        {"_id": 0, "id": 1, "email": 1, "tier": 1, "partner_code": 1, "created_at": 1},
    )

    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=COMMISSION_WINDOW_DAYS)).isoformat()

    async for u in users_cursor:
        summary["processed_users"] += 1

        # 12-month window check
        if (u.get("created_at") or "") < cutoff_iso:
            summary["skipped_expired"] += 1
            continue

        # Partner exists & active?
        partner = await db.partners.find_one(
            {"code": u["partner_code"], "status": {"$ne": "terminated"}},
            {"_id": 0, "id": 1, "code": 1, "status": 1},
        )
        if not partner:
            summary["skipped_unknown_partner"] += 1
            continue
        if partner.get("status") == "paused":
            # Don't credit while paused, but don't lose the user either
            continue

        price = TIER_MONTHLY_PRICE_GBP.get(u["tier"], 0.0)
        if price <= 0:
            continue
        credit = round(price * COMMISSION_RATE, 2)

        # Lifetime cap check — sum existing accrued for this user x partner
        agg = await db.partner_commissions.aggregate([
            {"$match": {"partner_id": partner["id"], "user_id": u["id"]}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_gbp"}}},
        ]).to_list(1)
        already = round((agg[0]["total"] if agg else 0) or 0, 2)
        if already >= CAP_PER_USER_GBP:
            summary["skipped_capped"] += 1
            continue
        # Trim the final credit so we never exceed the cap
        if already + credit > CAP_PER_USER_GBP:
            credit = round(CAP_PER_USER_GBP - already, 2)

        try:
            await db.partner_commissions.insert_one({
                "id": str(uuid.uuid4()),
                "partner_id": partner["id"],
                "partner_code": partner["code"],
                "user_id": u["id"],
                "user_email": u.get("email"),
                "tier": u["tier"],
                "amount_gbp": credit,
                "period_key": period_key,
                "paid": False,
                "paid_at": None,
                "payout_reference": None,
                "accrued_at": _now_iso(),
            })
            summary["credits_inserted"] += 1
            summary["total_credited_gbp"] = round(summary["total_credited_gbp"] + credit, 2)
        except Exception as e:
            if "duplicate" in str(e).lower():
                summary["skipped_duplicate"] += 1
            else:
                logger.exception(f"commission insert failed for user={u['id']}: {e}")

    summary["total_credited_gbp"] = round(summary["total_credited_gbp"], 2)
    logger.info(f"[partner-cron] {summary}")
    return summary


# ---------------- Router (admin endpoints) ----------------

def build_partner_router(db, owner_check_dependency):
    """Build a FastAPI APIRouter mounted at /api/admin/partners* with the
    owner-only dependency injected. We accept the dep as a parameter so the
    main server.py keeps a single source of truth for the admin guard."""
    router = APIRouter(prefix="/admin", tags=["partners"])

    @router.get("/partners")
    async def list_partners(_: dict = Depends(owner_check_dependency)):
        rows = await db.partners.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        # Decorate each with running totals
        for p in rows:
            agg = await db.partner_commissions.aggregate([
                {"$match": {"partner_id": p["id"]}},
                {"$group": {
                    "_id": "$paid",
                    "total": {"$sum": "$amount_gbp"},
                    "count": {"$sum": 1},
                }},
            ]).to_list(2)
            owed = paid = 0.0
            credit_count = 0
            for r in agg:
                credit_count += r["count"]
                if r["_id"]:
                    paid = round(r["total"], 2)
                else:
                    owed = round(r["total"], 2)
            p["lifetime_owed_gbp"] = owed
            p["lifetime_paid_gbp"] = paid
            p["credit_count"] = credit_count
            p["referred_users"] = await db.users.count_documents({"partner_code": p["code"]})
            # Mask bank account
            if p.get("payout_account_number"):
                acct = str(p["payout_account_number"])
                p["payout_account_number_masked"] = "****" + acct[-4:] if len(acct) >= 4 else "****"
        return {"count": len(rows), "partners": rows}

    @router.post("/partners")
    async def create_partner(data: PartnerCreate, _: dict = Depends(owner_check_dependency)):
        code = data.code.strip().upper().replace(" ", "-")
        if not code or len(code) < 3:
            raise HTTPException(400, "Code must be ≥3 chars")
        existing = await db.partners.find_one({"code": code})
        if existing:
            raise HTTPException(409, f"Partner code '{code}' already exists")
        partner = {
            "id": str(uuid.uuid4()),
            "code": code,
            "name": data.name.strip(),
            "contact_name": data.contact_name.strip(),
            "contact_email": data.contact_email,
            "contact_phone": (data.contact_phone or "").strip(),
            "payout_method": data.payout_method,
            "payout_bank_name": (data.payout_bank_name or "").strip(),
            "payout_sort_code": (data.payout_sort_code or "").strip(),
            "payout_account_number": (data.payout_account_number or "").strip(),
            "notes": (data.notes or "").strip(),
            "status": "active",
            "created_at": _now_iso(),
            "agreement_accepted": False,
            "agreement_accepted_at": None,
        }
        await db.partners.insert_one(partner)
        partner.pop("_id", None)
        partner["referred_users"] = 0
        partner["lifetime_owed_gbp"] = 0.0
        partner["lifetime_paid_gbp"] = 0.0
        return partner

    @router.patch("/partners/{partner_id}")
    async def update_partner(partner_id: str, data: PartnerUpdate, _: dict = Depends(owner_check_dependency)):
        upd = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
        if not upd:
            return {"ok": True, "updated": 0}
        if "status" in upd and upd["status"] not in ("active", "paused", "terminated"):
            raise HTTPException(400, "status must be active|paused|terminated")
        upd["updated_at"] = _now_iso()
        r = await db.partners.update_one({"id": partner_id}, {"$set": upd})
        return {"ok": True, "updated": r.modified_count}

    @router.get("/partners/{partner_id}/ledger")
    async def partner_ledger(partner_id: str, paid: Optional[str] = None,
                              _: dict = Depends(owner_check_dependency)):
        q: dict = {"partner_id": partner_id}
        if paid == "true":
            q["paid"] = True
        elif paid == "false":
            q["paid"] = False
        rows = await db.partner_commissions.find(q, {"_id": 0}).sort("accrued_at", -1).to_list(5000)
        return {"count": len(rows), "rows": rows}

    @router.post("/partners/{partner_id}/mark-paid")
    async def mark_paid(partner_id: str, data: MarkPaidPayload,
                         _: dict = Depends(owner_check_dependency)):
        if not data.period_keys:
            raise HTTPException(400, "period_keys is required")
        now = _now_iso()
        r = await db.partner_commissions.update_many(
            {"partner_id": partner_id, "paid": False, "period_key": {"$in": data.period_keys}},
            {"$set": {
                "paid": True,
                "paid_at": now,
                "payout_reference": data.reference or "",
            }}
        )
        return {"ok": True, "marked_paid": r.modified_count}

    @router.get("/partners/{partner_id}/statement.csv")
    async def partner_statement_csv(partner_id: str, period: Optional[str] = None,
                                     _: dict = Depends(owner_check_dependency)):
        """CSV statement for a partner — optionally filtered to one quarter (e.g. '2026-Q1')."""
        q: dict = {"partner_id": partner_id}
        if period:
            q["period_key"] = period if "-" in period else {"$regex": f"^{period}-"}
        rows = await db.partner_commissions.find(q, {"_id": 0}).sort("accrued_at", 1).to_list(10000)
        partner = await db.partners.find_one({"id": partner_id}, {"_id": 0})
        if not partner:
            raise HTTPException(404, "Partner not found")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Date", "Period", "User ID", "Tier", "Amount (GBP)", "Paid", "Paid Date", "Payout Ref"])
        total_owed = total_paid = 0.0
        for r in rows:
            w.writerow([
                (r.get("accrued_at") or "")[:10],
                r.get("period_key", ""),
                r.get("user_id", ""),
                r.get("tier", ""),
                f"{r.get('amount_gbp', 0):.2f}",
                "yes" if r.get("paid") else "no",
                (r.get("paid_at") or "")[:10] if r.get("paid_at") else "",
                r.get("payout_reference") or "",
            ])
            if r.get("paid"):
                total_paid += float(r.get("amount_gbp", 0))
            else:
                total_owed += float(r.get("amount_gbp", 0))
        w.writerow([])
        w.writerow(["", "", "", "TOTAL OWED", f"{total_owed:.2f}", "", "", ""])
        w.writerow(["", "", "", "TOTAL PAID", f"{total_paid:.2f}", "", "", ""])
        return Response(content=buf.getvalue(),
                        media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{partner["code"]}_statement.csv"'})

    @router.get("/partners/_summary")
    async def partners_global_summary(_: dict = Depends(owner_check_dependency)):
        """One-line dashboard summary: total owed across ALL partners + last accrual."""
        partners_count = await db.partners.count_documents({"status": {"$ne": "terminated"}})
        agg = await db.partner_commissions.aggregate([
            {"$group": {"_id": "$paid", "total": {"$sum": "$amount_gbp"}, "count": {"$sum": 1}}},
        ]).to_list(2)
        owed = paid = 0.0
        owed_count = paid_count = 0
        for r in agg:
            if r["_id"]:
                paid = round(r["total"], 2); paid_count = r["count"]
            else:
                owed = round(r["total"], 2); owed_count = r["count"]
        return {
            "active_partners": partners_count,
            "lifetime_owed_gbp": owed,
            "lifetime_paid_gbp": paid,
            "open_credits": owed_count,
            "paid_credits": paid_count,
            "rate_pct": int(COMMISSION_RATE * 100),
            "cap_per_user_gbp": CAP_PER_USER_GBP,
            "window_days": COMMISSION_WINDOW_DAYS,
        }

    @router.post("/partners/_accrue-now")
    async def accrue_now(_: dict = Depends(owner_check_dependency)):
        """Manual trigger for the monthly accrual (testing / catch-up)."""
        summary = await accrue_partner_commissions(db)
        return summary

    return router
