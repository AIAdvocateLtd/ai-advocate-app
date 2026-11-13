"""Account erasure + data export coverage. Synthetic users in an isolated test database only; no network, no AI.
Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_account_erasure_export.py -q"""
import asyncio
import os
import sys

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import account_erasure as E  # noqa: E402
from tests.test_stage3_limits import run, db, LOOP  # noqa: E402

TDB = db.client["aia_erasure_test"]
A = {"id": "synthetic-a", "email": "Synthetic.A@example.test", "full_name": "Alice Synthetic", "country": "GB",
     "password_hash": "$2b$12$syntheticsyntheticsyntheticsyntheticsyntheticsynthe", "latitude": 51.5, "longitude": -0.1,
     "language": "en", "stripe_customer_id": "cus_synthetic", "stripe_subscription_id": "sub_synthetic", "totp_secret": "x"}
B = {"id": "synthetic-b", "email": "synthetic.b@example.test", "full_name": "Bob Synthetic", "password_hash": "$2b$12$b"}
ALL = sorted(set(E.DELETE_BY_USER_ID + E.DELETE_BY_EMAIL + [c for c, *_ in E.ANONYMISE] +
                 ["users", "engagements", "engagement_messages", "engagement_files", "taster_answers"]))
TOMB_KEYS = {"id", "deleted", "deleted_at", "email", "deletion"}


def seed(u):
    run(TDB.users.insert_one(dict(u)))
    for c in [x for x in E.DELETE_BY_USER_ID if x != "conversations"]:
        run(TDB[c].insert_one({"id": f"{c}-{u['id']}", "user_id": u["id"], "text": f"private {c}",
                               "token": "secret-token", "description": server.encrypt_text(f"secret {c} of {u['id']}")}))
    for c in E.DELETE_BY_EMAIL:
        run(TDB[c].insert_one({"email": u["email"].lower(), "x": 1}))
    run(TDB.taster_answers.insert_one({"id": f"t-{u['id']}", "claimed_by": u["id"], "question": server.encrypt_text("q")}))
    run(TDB.llm_usage.insert_one({"user_id": u["id"], "cost_gbp": 0.01}))
    run(TDB.usage.insert_one({"user_id": u["id"], "count": 3}))
    run(TDB.gift_topups.insert_one({"recipient_user_id": u["id"], "recipient_email": u["email"], "price_gbp": 5}))
    run(TDB.comp_audit.insert_one({"target_id": u["id"], "target_email": u["email"], "days": 7}))
    run(TDB.privacy_analytics_deletions.insert_one({"user_id": u["id"], "user_email": u["email"]}))
    run(TDB.engagements.insert_one({"id": f"eng-{u['id']}", "client_user_id": u["id"]}))
    run(TDB.engagement_messages.insert_one({"engagement_id": f"eng-{u['id']}", "body": "hello"}))
    for i in range(5):
        run(TDB.conversations.insert_one({"id": f"c{i}-{u['id']}", "user_id": u["id"], "created_at": f"2026-01-0{i + 1}",
                                          "user_message": server.encrypt_text(f"question {i} from {u['id']}"),
                                          "assistant_response": server.encrypt_text(f"answer {i}")}))


def owned(uid):
    n = 0
    for c in ALL:
        n += run(TDB[c].count_documents({"$or": [{"user_id": uid}, {"client_user_id": uid}, {"claimed_by": uid},
                                                 {"recipient_user_id": uid}, {"target_id": uid}, {"id": f"eng-{uid}"}]}))
    return n


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    asyncio.set_event_loop(LOOP)
    monkeypatch.setattr(server, "db", TDB)
    monkeypatch.setattr(server.stripe.Subscription, "delete", lambda sid: {"id": sid, "status": "canceled"})
    for c in ALL:
        run(TDB[c].delete_many({}))
    seed(A)
    seed(B)
    yield
    for c in ALL:
        run(TDB[c].delete_many({}))


def delete(u=A):
    return run(server.gdpr_delete_my_account(user=dict(u)))


# ------------------------------------------------------------------ deletion
def test_deletion_removes_all_personal_data_and_leaves_pii_free_tombstone():
    assert owned(A["id"]) > 30
    r = delete()
    assert r["deleted"] and "permanently deleted" in r["message"]
    for c in E.DELETE_BY_USER_ID + ["engagements"]:
        assert run(TDB[c].count_documents({"$or": [{"user_id": A["id"]}, {"client_user_id": A["id"]}]})) == 0, c
    assert run(TDB.engagement_messages.count_documents({"engagement_id": f"eng-{A['id']}"})) == 0
    assert run(TDB.taster_answers.count_documents({"claimed_by": A["id"]})) == 0
    for c in E.DELETE_BY_EMAIL:
        assert run(TDB[c].count_documents({"email": A["email"].lower()})) == 0, c
    tomb = run(TDB.users.find_one({"id": A["id"]}, {"_id": 0}))
    assert set(tomb) == TOMB_KEYS and tomb["deleted"] and tomb["email"] == f"deleted-{A['id']}@ai-advocate.local"
    assert tomb["deletion"]["status"] == "complete" and tomb["deletion"]["failed"] == []
    flat = str(tomb)
    for v in ("Alice", "Synthetic.A", "synthetic.a@", "$2b$", "cus_synthetic", "sub_synthetic", "51.5"):
        assert v not in flat


def test_retained_records_are_anonymised_not_linked():
    delete()
    code = E.anon_code(A["id"], server.JWT_SECRET)
    assert run(TDB.llm_usage.find_one({"user_id": code}))["cost_gbp"] == 0.01
    assert run(TDB.usage.find_one({"user_id": code}))["count"] == 3
    g = run(TDB.gift_topups.find_one({"recipient_user_id": code}))
    assert g["recipient_email"] is None and g["price_gbp"] == 5
    assert run(TDB.comp_audit.find_one({"target_id": code}))["target_email"] is None
    assert run(TDB.privacy_analytics_deletions.find_one({"user_id": code}))["user_email"] is None
    assert owned(A["id"]) == 0 and A["id"] not in code


def test_other_customers_untouched():
    before = owned(B["id"])
    delete()
    assert owned(B["id"]) == before
    assert run(TDB.users.find_one({"id": B["id"]}))["full_name"] == "Bob Synthetic"


def test_deleted_account_cannot_sign_in():
    delete()
    tok = server.make_token(A["id"], A["email"])
    with pytest.raises(HTTPException) as e:
        run(server.get_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok)))
    assert e.value.status_code == 401


class _Flaky:
    """Wraps the test DB so one collection fails mid-deletion."""
    def __init__(self, real, bad):
        self.real, self.bad = real, bad

    def __getitem__(self, name):
        col = self.real[name]
        if name == self.bad:
            class C:
                def __getattr__(s, a):
                    return getattr(col, a)

                async def delete_many(s, *a, **k):
                    raise RuntimeError("simulated outage")
            return C()
        return col

    def __getattr__(self, name):
        return self[name]


def test_partial_failure_locks_account_and_sweeper_finishes():
    r = run(E.erase_user(_Flaky(TDB, "lex_uploads"), A["id"], A["email"], server.JWT_SECRET))
    assert r["status"] == "incomplete" and r["failed"] == ["lex_uploads"]
    tomb = run(TDB.users.find_one({"id": A["id"]}, {"_id": 0}))
    assert tomb["deleted"] and "password_hash" not in tomb and "full_name" not in tomb
    assert tomb["deletion"]["pending_email"] == A["email"].lower()
    assert run(TDB.lex_uploads.count_documents({"user_id": A["id"]})) == 1
    assert run(TDB.conversations.count_documents({"user_id": A["id"]})) == 0
    assert run(E.retry_incomplete(TDB, server.JWT_SECRET)) == 1
    tomb = run(TDB.users.find_one({"id": A["id"]}, {"_id": 0}))
    assert tomb["deletion"]["status"] == "complete" and "pending_email" not in tomb["deletion"]
    assert owned(A["id"]) == 0 and run(E.retry_incomplete(TDB, server.JWT_SECRET)) == 0


def test_rerun_is_idempotent():
    delete()
    r = run(E.erase_user(TDB, A["id"], None, server.JWT_SECRET))
    assert r["status"] == "complete" and run(TDB.users.count_documents({"id": A["id"]})) == 1


def test_stripe_cancel_kept_and_failure_keeps_only_subscription_reference(monkeypatch):
    called = []
    monkeypatch.setattr(server.stripe.Subscription, "delete", lambda sid: called.append(sid))
    delete()
    assert called == ["sub_synthetic"]
    run(TDB.users.delete_many({}))
    seed({**A, "id": "synthetic-c", "email": "c@example.test"})

    def boom(sid):
        raise RuntimeError("stripe down")
    monkeypatch.setattr(server.stripe.Subscription, "delete", boom)
    delete({**A, "id": "synthetic-c", "email": "c@example.test"})
    tomb = run(TDB.users.find_one({"id": "synthetic-c"}, {"_id": 0}))
    assert tomb["stripe_subscription_id"] == "sub_synthetic" and tomb["stripe_cancel_failed"] is True
    assert "full_name" not in tomb and "stripe_customer_id" not in tomb


# ------------------------------------------------------------------ export
def test_export_readable_complete_and_own_data_only():
    p = run(server._build_user_export(dict(A)))
    assert [c["user_message"] for c in p["conversations"]][:2] == ["question 0 from synthetic-a", "question 1 from synthetic-a"]
    assert p["conversations_total"] == 5 and p["conversations_truncated"] is False
    other = p["other_records"]
    for c in ("lex_uploads", "emergency_profile", "emergency_events", "emergency_tracks", "evidence_files", "witness_statements",
              "witness_invites", "form_drafts", "form_ocr_scans", "live_notes", "contract_analyses", "share_tokens",
              "taster_answers", "law_firm_inquiries"):
        assert c in other, c
    assert other["witness_statements"][0]["description"] == "secret witness_statements of synthetic-a"
    flat = str(p)
    assert "enc:v1:" not in flat and "secret-token" not in flat and "synthetic-b" not in flat and "$2b$" not in flat
    assert "totp_secret" not in p["user"] and "password_hash" not in p["user"]
    html = server._render_user_export_html(p)
    assert "Other Records" in html and "question 4 from synthetic-a" in html and "enc:v1:" not in html


def test_large_accounts_flagged_when_truncated(monkeypatch):
    monkeypatch.setattr(E, "EXPORT_LIMIT", 3)
    p = run(server._build_user_export(dict(A)))
    assert len(p["conversations"]) == 3 and p["conversations_total"] == 5 and p["conversations_truncated"]
    assert "first 3 of 5 conversations" in server._render_user_export_html(p)


def test_export_requires_login():
    from fastapi.testclient import TestClient
    c = TestClient(server.app)
    assert c.post("/api/users/me/export-email").status_code in (401, 403)
    assert c.delete("/api/users/me").status_code in (401, 403)


def test_preview_customer_data_untouched():
    names = ("users", "conversations", "cases", "llm_usage")
    before = {n: run(db[n].count_documents({})) for n in names}
    delete()
    assert before == {n: run(db[n].count_documents({})) for n in names}
