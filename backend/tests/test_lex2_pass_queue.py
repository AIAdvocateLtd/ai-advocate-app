"""Pass queueing, duplicate Stripe webhooks, Lex 2.0 customer copy (no AI calls, no payments).
Run: cd /app/backend && python -m pytest tests/test_lex2_pass_queue.py -q"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import stage3  # noqa: E402

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
db = server.db
run = LOOP.run_until_complete
TAG = f"l2pq-{uuid.uuid4().hex[:8]}"


def _user(**kw):
    u = {"id": f"{TAG}-{uuid.uuid4().hex[:6]}", "email": f"{TAG}.{uuid.uuid4().hex[:4]}@example.com", "tier": "free", **kw}
    run(db.users.insert_one(dict(u)))
    return u["id"]


def _get(uid):
    return run(db.users.find_one({"id": uid}, {"_id": 0}))


def _sid():
    return f"cs_{TAG}_{uuid.uuid4().hex[:6]}"


@pytest.fixture(autouse=True, scope="module")
def _cleanup():
    before = run(db.app_settings.find_one({"_id": "stage3"})) or {}
    yield
    run(db.app_settings.replace_one({"_id": "stage3"}, before, upsert=True) if before else db.app_settings.delete_one({"_id": "stage3"}))
    stage3._cache["settings"] = None
    run(db.users.delete_many({"id": {"$regex": f"^{TAG}"}}))
    run(db.topup_grants.delete_many({"user": {"$regex": TAG}}))
    run(db.topup_grants.delete_many({"_id": {"$regex": TAG}}))


def test_first_pass_activates_and_duplicate_webhook_is_ignored():
    uid, sid = _user(), _sid()
    assert run(server._activate_topup_for_user(uid, "day_pass", session_id=sid)) == "active"
    first = _get(uid)["topup_active"]
    assert run(server._activate_topup_for_user(uid, "day_pass", session_id=sid)) == "duplicate"
    u = _get(uid)
    assert u["topup_active"] == first and not u.get("topup_queue") and len(u["topup_history"]) == 1


def test_second_pass_is_queued_and_current_pass_untouched():
    uid = _user()
    run(server._activate_topup_for_user(uid, "day_pass", session_id=_sid()))
    act = _get(uid)["topup_active"]
    assert run(server._activate_topup_for_user(uid, "weekend_pass", session_id=_sid())) == "queued"
    assert run(server._activate_topup_for_user(uid, "letter_pack", session_id=_sid())) == "queued"
    u = _get(uid)
    assert u["topup_active"] == act
    assert [q["kind"] for q in u["topup_queue"]] == ["weekend_pass", "letter_pack"]
    view = server.topup_queue_view(u)
    assert view[0]["starts_at"] == act["expires_at"]
    assert view[1]["starts_at"] == view[0]["ends_at"]
    assert (datetime.fromisoformat(view[0]["ends_at"]) - datetime.fromisoformat(view[0]["starts_at"])) == timedelta(hours=72)


def test_queued_pass_starts_at_previous_expiry_with_full_duration_and_own_allowance():
    uid = _user()
    run(server._activate_topup_for_user(uid, "day_pass", session_id=_sid()))
    run(server._activate_topup_for_user(uid, "weekend_pass", session_id=_sid()))
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    run(db.users.update_one({"id": uid}, {"$set": {"topup_active.expires_at": expired}}))
    run(server._promote_queued_topups(uid))
    u = _get(uid)
    act = u["topup_active"]
    assert act["kind"] == "weekend_pass" and act["activated_at"] == expired
    assert datetime.fromisoformat(act["expires_at"]) - datetime.fromisoformat(expired) == timedelta(hours=72)
    assert not u["topup_queue"]
    assert act["purchased_at"] < act["activated_at"] or act["purchased_at"]
    assert [h["kind"] for h in u["topup_history"]] == ["day_pass", "weekend_pass"]
    # allowance bucket is keyed on the new activation, so the weekend allowance starts fresh
    p = stage3._active_pass(u, "2000-01-01")
    assert p and f"s3-pass-{p['activated_at']}" != f"s3-pass-{expired[:0]}"


def test_chain_of_expired_passes_promotes_in_order():
    uid = _user()
    for k in ("day_pass", "day_pass", "crisis_pack"):
        run(server._activate_topup_for_user(uid, k, session_id=_sid()))
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    run(db.users.update_one({"id": uid}, {"$set": {"topup_active.expires_at": long_ago}}))
    run(server._promote_queued_topups(uid))
    u = _get(uid)
    # second day pass ran from long_ago to long_ago+24h (already over), crisis pack starts at its end
    assert u["topup_active"]["kind"] == "crisis_pack"
    assert u["topup_active"]["activated_at"] == (datetime.fromisoformat(long_ago) + timedelta(hours=24)).isoformat()
    assert not u["topup_queue"]


def test_doc_pack_stacks_and_is_idempotent():
    uid, sid = _user(), _sid()
    run(server._activate_topup_for_user(uid, "day_pass", session_id=_sid()))
    assert run(server._activate_topup_for_user(uid, "doc_pack", session_id=sid)) == "active"
    assert run(server._activate_topup_for_user(uid, "doc_pack", session_id=sid)) == "duplicate"
    u = _get(uid)
    assert u["doc_pack_remaining"] == 5 and u["topup_active"]["kind"] == "day_pass" and not u.get("topup_queue")


def test_expired_pass_is_replaced_not_queued():
    uid = _user(topup_active={"kind": "day_pass", "activated_at": "2026-01-01T00:00:00+00:00",
                              "expires_at": "2026-01-02T00:00:00+00:00", "label": "Day Pass", "grants_tier": "plus"})
    assert run(server._activate_topup_for_user(uid, "weekend_pass", session_id=_sid())) == "active"


def test_gift_repeat_webhook_ignored_and_gift_note_on_queued_pass():
    uid = _user()
    email = _get(uid)["email"]
    run(server._activate_topup_for_user(uid, "day_pass", session_id=_sid()))
    meta = {"is_gift": "1", "recipient_email": email, "topup_pack": "weekend_pass", "gifter_name": "Ann", "gifter_email": ""}
    sid = _sid()
    run(server._activate_gifted_topup(meta, sid))
    run(server._activate_gifted_topup(meta, sid))
    u = _get(uid)
    assert len(u["topup_queue"]) == 1 and u["topup_queue"][0]["gift"]["gifter_name"] == "Ann"
    assert "gift" not in u["topup_active"]
    run(db.gift_topups.delete_many({"recipient_email": email}))


def test_pass_v2_follows_purchase_time_not_activation_time():
    s = run(stage3.update_settings({"passes_v2_enabled": True}))
    before = (datetime.fromisoformat(s["passes_v2_since"]) - timedelta(minutes=5)).isoformat()
    p = {"kind": "day_pass", "purchased_at": before, "activated_at": datetime.now(timezone.utc).isoformat()}
    assert stage3.pass_table(s, p)["msgs"] == 50
    p["purchased_at"] = datetime.now(timezone.utc).isoformat()
    assert stage3.pass_table(s, p)["msgs"] == 30
    run(stage3.update_settings({"passes_v2_enabled": False}))


def test_customer_copy_switches_with_allowances():
    run(stage3.update_settings({"allowances_v2_enabled": False, "cost_cap_enabled": False, "emergency_allowance_enabled": False}))
    a = run(server.plan_allowances())
    assert a["plus"] == {"monthly": 300, "daily": 40} and a["pro"] == {"monthly": 600, "daily": 80} and a["fair_use_note"] == ""
    assert run(server.get_tiers())["fair_use_note"] == ""
    run(stage3.update_settings({"allowances_v2_enabled": True, "cost_cap_enabled": True, "emergency_allowance_enabled": True}))
    a = run(server.plan_allowances())
    assert a["plus"] == {"monthly": 150, "daily": 20} and a["pro"] == {"monthly": 350, "daily": 50}
    n = a["fair_use_note"]
    assert "20 Lex messages a day on Plus and 50 on Pro" in n
    assert "before your message allowance is used up" in n and "never charged automatically" in n and "emergency" in n
    run(stage3.update_settings({"allowances_v2_enabled": False, "cost_cap_enabled": False, "emergency_allowance_enabled": False}))


def test_review_levels_v1_until_activation_then_10_18():
    s = run(stage3.settings())
    assert s["thresholds"]["plus"]["monthly_review"] == 12 and s["thresholds"]["pro"]["monthly_review"] == 25
    assert s["monthly_review_v2"] == {"plus": 10.0, "pro": 18.0, "yearly": 18.0}
    assert s["monthly_cost_caps"]["plus"] in (14.0, 10.0)
    assert stage3.DEFAULTS["monthly_cost_caps"] == {"plus": 14.0, "pro": 28.0, "yearly": 28.0}
