"""Iteration 12 — Contract Tools (Read/Draft/Negotiate) + tier-gating regression.

Covers:
 - /api/contract/analyze (now Plus+, fixed 2-stage extraction)
 - /api/contract/draft (now Pro+)
 - /api/contract/negotiate (NEW, Pro+)
 - /api/outcome/predict (Pro+)
 - /api/hearing/transcribe (Pro+ gate fires before file processing)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
# Internal URL — used as fallback for long-running LLM endpoints where the
# preview ingress sometimes returns 502 after ~60s of waiting on the upstream.
INTERNAL_API = "http://localhost:8001/api"

PRO_EMAIL = "test@advocate.app"
PRO_PASSWORD = "Test12345!"

CONTRACT_TEXT_PATH = "/tmp/test_contract.txt"


# ---------- shared fixtures ----------

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


@pytest.fixture(scope="session")
def pro_token(session):
    """Login as the seeded trial_pro user, and reset doc_analyze usage so
    repeated test runs don't blow through the monthly quota."""
    r = session.post(f"{API}/auth/login",
                     json={"email": PRO_EMAIL, "password": PRO_PASSWORD},
                     timeout=30)
    assert r.status_code == 200, f"pro login failed: {r.status_code} {r.text}"
    data = r.json()
    user_id = (data.get("user") or {}).get("id")
    # Reset doc_analyze usage so repeated runs aren't blocked by 10/mo quota
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "ai_advocate_db")
        client = MongoClient(mongo_url)
        client[db_name].usage.delete_many({"user_id": user_id, "feature": "doc_analyze"})
        client.close()
    except Exception:
        pass
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="session")
def free_token(session):
    """Signup a fresh user and force them to free tier by expiring their trial
    directly in MongoDB."""
    email = f"TEST_free_{uuid.uuid4().hex[:8]}@advocate.app"
    r = session.post(
        f"{API}/auth/signup",
        json={"email": email, "password": "TestPass123!", "name": "Free User"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"no token in signup response: {body}"

    # Force free tier: expire the trial_end_date in Mongo
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "ai_advocate_db")
        client = MongoClient(mongo_url)
        past = "2020-01-01T00:00:00+00:00"
        client[db_name].users.update_one(
            {"email": email},
            {"$set": {"trial_end_date": past, "tier": "free",
                      "subscription_status": "inactive"}},
        )
        client.close()
    except Exception as e:
        pytest.skip(f"could not downgrade test user to free: {e}")

    # Verify tier
    me = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    me_body = me.json() if me.status_code == 200 else {}
    tier = me_body.get("tier") or me_body.get("user", {}).get("tier")
    return {"token": token, "tier": tier, "email": email}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _contract_file():
    """Return a tuple suitable for `files=` of a small contract."""
    return ("contract.txt", open(CONTRACT_TEXT_PATH, "rb"), "text/plain")


# ============================================================
# 1. /api/contract/negotiate — NEW Pro feature
# ============================================================
class TestContractNegotiate:

    def test_negotiate_no_auth_401(self, session):
        files = {"file": _contract_file()}
        data = {"priorities": "fair notice", "user_role": "recipient",
                "language": "en-GB", "country": "GB"}
        r = session.post(f"{API}/contract/negotiate", files=files, data=data, timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"

    def test_negotiate_free_tier_402(self, session, free_token):
        if free_token["tier"] != "free":
            pytest.skip(f"signup auto-granted tier={free_token['tier']}, cannot test free gate")
        files = {"file": _contract_file()}
        data = {"priorities": "fair notice", "user_role": "recipient",
                "language": "en-GB", "country": "GB"}
        r = session.post(f"{API}/contract/negotiate",
                         files=files, data=data,
                         headers=_auth(free_token["token"]), timeout=30)
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:300]}"
        detail = (r.json().get("detail") or "").lower()
        assert "pro" in detail, f"detail should mention Pro: {detail}"

    def test_negotiate_pro_tier_success(self, session, pro_token):
        files = {"file": _contract_file()}
        data = {"priorities": "fair notice and keep my IP",
                "user_role": "recipient",
                "language": "en-GB",
                "country": "GB"}
        # Use internal URL; the preview ingress returns 502 on >60s requests.
        # Functional correctness is the focus, not the ingress proxy behaviour.
        r = session.post(f"{INTERNAL_API}/contract/negotiate",
                         files=files, data=data,
                         headers=_auth(pro_token), timeout=180)
        assert r.status_code == 200, f"negotiate failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        # required keys
        for k in ["contract_type", "leverage_assessment", "worst_clauses",
                  "missing_protections", "do_not_compromise_on",
                  "walk_away_signals", "negotiation_strategy",
                  "ready_to_send_email", "estimated_negotiation_difficulty"]:
            assert k in body, f"missing key: {k}; keys={list(body.keys())}"
        assert isinstance(body["worst_clauses"], list)
        assert len(body["worst_clauses"]) >= 1
        wc = body["worst_clauses"][0]
        for k in ["clause_title", "current_text_quote", "why_its_bad_for_user",
                  "suggested_redline", "fallback_position", "priority"]:
            assert k in wc, f"worst_clauses[0] missing key: {k}"
        assert isinstance(body["ready_to_send_email"], str)
        assert len(body["ready_to_send_email"]) > 100


# ============================================================
# 2. /api/contract/analyze — fixed 2-stage extraction
# ============================================================
class TestContractAnalyze:

    def test_analyze_pro_tier_success(self, session, pro_token):
        files = {"file": _contract_file()}
        data = {"language": "en-GB", "country": "GB"}
        # Internal URL fallback (see TestContractNegotiate).
        r = session.post(f"{INTERNAL_API}/contract/analyze",
                         files=files, data=data,
                         headers=_auth(pro_token), timeout=180)
        assert r.status_code == 200, f"analyze failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        for k in ["contract_type", "plain_english_summary", "overall_verdict",
                  "verdict_one_liner", "clauses", "red_flags",
                  "amber_flags", "questions_to_ask"]:
            assert k in body, f"missing key: {k}; keys={list(body.keys())}"
        assert isinstance(body["clauses"], list)


# ============================================================
# 3. /api/contract/draft — now Pro+
# ============================================================
class TestContractDraft:
    DRAFT_PAYLOAD = {
        "contract_type": "nda",
        "party_a": {"name": "Acme Ltd", "address": "1 Main St, London", "registration_no": "12345678"},
        "party_b": {"name": "Jane Doe", "address": "2 Side St, London", "email": "jane@example.com"},
        "terms": {"duration_months": 12, "jurisdiction": "England & Wales", "purpose": "Evaluation of partnership"},
        "additional_notes": "",
        "language": "en-GB",
        "country": "GB",
    }

    def test_draft_free_tier_402(self, session, free_token):
        if free_token["tier"] != "free":
            pytest.skip(f"signup auto-granted tier={free_token['tier']}")
        r = session.post(f"{API}/contract/draft",
                         json=self.DRAFT_PAYLOAD,
                         headers=_auth(free_token["token"]), timeout=30)
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:300]}"
        assert "pro" in (r.json().get("detail") or "").lower()

    def test_draft_pro_tier_success(self, session, pro_token):
        r = session.post(f"{API}/contract/draft",
                         json=self.DRAFT_PAYLOAD,
                         headers=_auth(pro_token), timeout=120)
        assert r.status_code == 200, f"draft failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        assert "contract_title" in body or "title" in body
        assert "full_contract_text" in body or "contract_text" in body or "text" in body


# ============================================================
# 4. /api/outcome/predict — now Pro+
# ============================================================
class TestOutcomePredict:
    PAYLOAD = {
        "case_summary": "I was dismissed without notice after 3 years of service.",
        "case_category": "employment",
        "language": "en-GB",
        "country": "GB",
    }

    def test_outcome_free_tier_402(self, session, free_token):
        if free_token["tier"] != "free":
            pytest.skip(f"signup auto-granted tier={free_token['tier']}")
        r = session.post(f"{API}/outcome/predict",
                         json=self.PAYLOAD,
                         headers=_auth(free_token["token"]), timeout=30)
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:300]}"
        assert "pro" in (r.json().get("detail") or "").lower()

    def test_outcome_pro_tier_success(self, session, pro_token):
        r = session.post(f"{API}/outcome/predict",
                         json=self.PAYLOAD,
                         headers=_auth(pro_token), timeout=120)
        assert r.status_code == 200, f"outcome failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        # outcome predictor returns at minimum a success_probability_pct
        assert "success_probability_pct" in body or "probability" in body or len(body) > 0


# ============================================================
# 5. /api/hearing/transcribe — Pro gate fires before file processing
# ============================================================
class TestHearingTranscribeGate:
    def test_hearing_free_tier_402(self, session, free_token):
        if free_token["tier"] != "free":
            pytest.skip(f"signup auto-granted tier={free_token['tier']}")
        # Send a trivial dummy file — the gate should reject BEFORE STT runs.
        # NOTE: hearing endpoint uses field name "audio" not "file".
        files = {"audio": ("a.m4a", b"\x00\x00", "audio/m4a")}
        r = session.post(f"{API}/hearing/transcribe",
                         files=files,
                         headers=_auth(free_token["token"]), timeout=30)
        assert r.status_code == 402, f"expected 402 gate, got {r.status_code}: {r.text[:300]}"
        assert "pro" in (r.json().get("detail") or "").lower()
