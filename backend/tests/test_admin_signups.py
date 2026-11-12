"""Admin genuine-signup counts + paginated list (no AI). Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_admin_signups.py -q"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
from tests.test_stage3_limits import run, db  # noqa: E402

TAG = uuid.uuid4().hex[:6]
NOW = datetime.now(timezone.utc)


def _u(email, **kw):
    return {"id": str(uuid.uuid4()), "email": email, "tier": "free", "signup_ip": "198.51.100.1", "stripe_customer_id": None,
            "created_at": NOW.isoformat(), "_tag": TAG, **kw}


CASES = {
    "real_gmail": (_u(f"jane.real{TAG}x@gmail.com".replace(TAG, "q")), "genuine"),
    "real_payer_on_test_domain": (_u(f"test_{TAG}a1@advocate.app", stripe_customer_id="cus_LIVE123", tier="pro"), "genuine"),
    "dev_domain_no_evidence": (_u("sarah@advocate.app"), "genuine"),
    "fixture_suffix": (_u(f"test_router_{TAG}ab@advocate.app"), "test"),
    "direct_insert": (_u("plainname@advocate.app", signup_ip=None), "test"),
    "reserved_domain": (_u(f"someone{TAG}@example.com"), "test"),
    "resend_sink": (_u(f"delivered+TEST_{TAG}@resend.dev"), "test"),
    "fake_stripe": (_u(f"TEST_{TAG}@advocate.app", stripe_customer_id="cus_test_1"), "test"),
    "internal": (_u(f"staff{TAG}@aiadvocate.co.uk"), "internal"),
    "deleted": (_u(f"gone{TAG}@gmail.com", deleted=True), None),
    "old_datetime_type": (_u(f"older.user{TAG}@outlook.com".replace(TAG, "z"), created_at=NOW - timedelta(days=40)), "genuine"),
}


@pytest.fixture(scope="module", autouse=True)
def seeded():
    run(db.users.insert_many([dict(u) for u, _ in CASES.values()]))
    yield
    run(db.users.delete_many({"_tag": TAG}))


def _group_of(email):
    f = server._signup_filters()
    found = [g for g, q in f.items() if run(db.users.count_documents({"$and": [q, {"email": email, "_tag": TAG}]}))]
    return found[0] if len(found) == 1 else (None if not found else found)


@pytest.mark.parametrize("name", list(CASES))
def test_classification_uses_evidence(name):
    user, expected = CASES[name]
    assert _group_of(user["email"]) == expected


def test_stats_and_windows_count_genuine_only():
    s = run(server.admin_signup_stats(_={}))
    assert {"genuine", "test", "internal", "needs_review", "today", "last_24h", "last_7d", "last_30d"} <= set(s)
    assert s["last_24h"] >= 3 and s["last_30d"] >= s["last_7d"] >= s["last_24h"]
    assert s["genuine"] >= 4 and s["needs_review"] >= 1


def test_pagination_newest_first_and_no_30_cap():
    first = run(server.admin_signup_list(group="test", page=1, page_size=2, _={}))
    assert len(first["users"]) == 2 and first["total"] >= 5 and first["has_more"]
    second = run(server.admin_signup_list(group="test", page=2, page_size=2, _={}))
    assert not {u["id"] for u in first["users"]} & {u["id"] for u in second["users"]}
    allg = run(server.admin_signup_list(group="genuine", page=1, page_size=100, _={}))
    dates = [u.get("created_at") or "" for u in allg["users"]]
    assert dates == sorted(dates, reverse=True)
    assert all(isinstance(u.get("created_at", ""), str) for u in allg["users"])
    assert set(allg["users"][0]) <= {"id", "email", "full_name", "tier", "subscription_status", "email_verified",
                                      "comp_pro_until", "trial_end_date", "created_at"}


def test_bad_group_rejected_and_admin_only():
    with pytest.raises(server.HTTPException):
        run(server.admin_signup_list(group="everyone", _={}))
    with pytest.raises(server.HTTPException) as e:
        run(server.require_admin(user={"email": "someone@gmail.com"}))
    assert e.value.status_code == 403


def test_nothing_modified():
    assert run(db.users.count_documents({"_tag": TAG})) == len(CASES)
    assert run(db.users.find_one({"email": CASES["deleted"][0]["email"]}, {"_id": 0, "deleted": 1})) == {"deleted": True}
