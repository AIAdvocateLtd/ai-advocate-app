"""Round 2 features: file delete, outcome predictor, cost estimator, hearing transcribe,
legal aid finder, case share links, anonymous stats wall."""
import os, uuid, time, io, struct, wave
import pytest
import requests

def _read_frontend_env_url():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None

_URL = os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env_url()
assert _URL, "REACT_APP_BACKEND_URL not configured"
BASE = _URL.rstrip("/") + "/api"
PWD = "TestPass123!"


def _signup():
    em = f"r2_{uuid.uuid4().hex[:10]}@advocate.app"
    r = requests.post(f"{BASE}/auth/signup", json={
        "email": em, "password": PWD, "full_name": "R2 Test",
        "language": "en-GB", "country": "GB",
    }, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    return j["access_token"], em


@pytest.fixture(scope="module")
def auth():
    tok, em = _signup()
    return {"token": tok, "email": em, "h": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def other_user():
    tok, em = _signup()
    return {"token": tok, "h": {"Authorization": f"Bearer {tok}"}}


# ---------- Outcome Predictor ----------
class TestOutcomePredictor:
    def test_short_summary_rejected(self, auth):
        r = requests.post(f"{BASE}/outcome/predict",
                          headers=auth["h"],
                          json={"case_summary": "too short", "category": "property"},
                          timeout=30)
        assert r.status_code == 400, r.text

    def test_predict_returns_structured_json(self, auth):
        body = {
            "case_summary": ("My landlord kept my £1200 deposit and never put it in a "
                             "tenancy deposit scheme. I lived there 14 months and left "
                             "the flat clean."),
            "category": "property",
            "language": "en-GB",
            "country": "GB",
        }
        r = requests.post(f"{BASE}/outcome/predict", headers=auth["h"], json=body, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("success_probability_pct", "key_factors_for", "key_factors_against",
                  "similar_cases", "recommended_strategy", "confidence"):
            assert k in d, f"missing key {k}: {d}"
        assert isinstance(d["success_probability_pct"], int)
        assert 0 <= d["success_probability_pct"] <= 100


# ---------- Cost Estimator ----------
class TestCostEstimator:
    def test_estimate_full_schema(self, auth):
        r = requests.post(f"{BASE}/cost/estimate", headers=auth["h"], json={
            "case_summary": "Unfair dismissal claim against my old employer after 3 years service.",
            "category": "employment", "country": "GB", "language": "en-GB",
        }, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("low_estimate_gbp", "high_estimate_gbp", "court_fees_gbp",
                  "typical_hours", "hourly_rate_range_gbp", "no_win_no_fee_available",
                  "explanation", "ai_advocate_saving"):
            assert k in d, f"missing {k}: {d}"


# ---------- Legal Aid Finder ----------
class TestLegalAid:
    def test_low_income_qualifies(self, auth):
        r = requests.post(f"{BASE}/legal-aid/check", headers=auth["h"], json={
            "monthly_income_gbp": 1800, "savings_gbp": 2000,
            "household_size": 2, "case_category": "eviction", "country": "GB",
        }, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["qualifies"] is True
        assert any("Shelter" in s["name"] for s in d["signposts"]), d["signposts"]

    def test_high_income_disqualifies(self, auth):
        r = requests.post(f"{BASE}/legal-aid/check", headers=auth["h"], json={
            "monthly_income_gbp": 5000, "savings_gbp": 2000,
            "household_size": 1, "case_category": "employment", "country": "GB",
        }, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["qualifies"] is False
        assert any("ACAS" in s["name"] for s in d["signposts"]), d["signposts"]


# ---------- File Delete ----------
class TestFileDelete:
    @pytest.fixture
    def created_file_id(self, auth):
        # Use hearing/transcribe to actually create a legal_files row.
        wav = io.BytesIO()
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)  # ~1s silence
        wav.seek(0)
        r = requests.post(f"{BASE}/hearing/transcribe", headers=auth["h"],
                          files={"audio": ("t.wav", wav, "audio/wav")},
                          data={"language": "en-GB", "country": "GB", "title": "TEST_hearing"},
                          timeout=180)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_delete_then_404_on_second(self, auth, created_file_id):
        r1 = requests.delete(f"{BASE}/legal-files/{created_file_id}", headers=auth["h"], timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.delete(f"{BASE}/legal-files/{created_file_id}", headers=auth["h"], timeout=30)
        assert r2.status_code == 404

    def test_other_user_cannot_delete(self, auth, other_user, created_file_id):
        r = requests.delete(f"{BASE}/legal-files/{created_file_id}", headers=other_user["h"], timeout=30)
        assert r.status_code == 404


# ---------- Hearing Recorder ----------
class TestHearingTranscribe:
    def test_upload_returns_analysis(self, auth):
        wav = io.BytesIO()
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        wav.seek(0)
        r = requests.post(f"{BASE}/hearing/transcribe", headers=auth["h"],
                          files={"audio": ("t.wav", wav, "audio/wav")},
                          data={"language": "en-GB", "country": "GB",
                                "title": "TEST_hearing2"},
                          timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "transcript" in d
        a = d.get("analysis", {})
        for k in ("summary", "key_points", "favourable_moments",
                  "unfavourable_moments", "next_actions", "follow_up_deadlines"):
            assert k in a, f"missing analysis key {k}: {a}"


# ---------- Case Share ----------
class TestCaseShare:
    @pytest.fixture
    def case_id(self, auth):
        r = requests.post(f"{BASE}/cases", headers=auth["h"], json={
            "name": "TEST_share_case", "summary": "share test", "category": "property",
        }, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_share_returns_token_url(self, auth, case_id):
        r = requests.post(f"{BASE}/cases/{case_id}/share", headers=auth["h"], timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["token"] and d["url"] and d["expires_at"]
        # Public access without auth
        pr = requests.get(f"{BASE}/share/{d['token']}", timeout=30)
        assert pr.status_code == 200, pr.text
        pd = pr.json()
        assert "case" in pd and "items" in pd

    def test_share_token_uniqueness(self, auth, case_id):
        r1 = requests.post(f"{BASE}/cases/{case_id}/share", headers=auth["h"], timeout=30)
        t1 = r1.json()["token"]
        r2 = requests.post(f"{BASE}/cases/{case_id}/share", headers=auth["h"], timeout=30)
        t2 = r2.json()["token"]
        assert t1 != t2
        # First token should now be revoked → 404
        g = requests.get(f"{BASE}/share/{t1}", timeout=30)
        assert g.status_code == 404

    def test_invalid_token_404(self):
        r = requests.get(f"{BASE}/share/totallybogus_xxxxxxx", timeout=30)
        assert r.status_code == 404

    def test_revoke_share(self, auth, case_id):
        r = requests.post(f"{BASE}/cases/{case_id}/share", headers=auth["h"], timeout=30)
        token = r.json()["token"]
        d = requests.delete(f"{BASE}/cases/{case_id}/share", headers=auth["h"], timeout=30)
        assert d.status_code == 200
        g = requests.get(f"{BASE}/share/{token}", timeout=30)
        assert g.status_code == 404


# ---------- Stats Wall ----------
class TestStatsPublic:
    def test_no_auth_required_and_cached(self):
        r = requests.get(f"{BASE}/stats/public", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("users_helped_total", "cases_active", "letters_drafted",
                  "documents_analysed", "hearings_transcribed", "live_sessions"):
            assert k in d, f"missing {k}: {d}"
            assert isinstance(d[k], int)
        # second call should return identical cached data
        r2 = requests.get(f"{BASE}/stats/public", timeout=30)
        assert r2.json() == d
