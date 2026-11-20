# Lex research admin endpoints (health, coverage, source-change queue, AI discovery toggle) + national chat citations
import os
import json
import pytest
import requests
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
OUT = "/app/test_reports/pytest/research_chat_outputs.json"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200 or "access_token" not in r.json():
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@aiadvocate.co.uk", "AdminLex2026!")


@pytest.fixture(scope="module")
def normal():
    return _login("test@advocate.app", "Test12345!")


@pytest.fixture(scope="module")
def mdb():
    c = MongoClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]]


# --- Health ---
class TestHealth:
    def test_health_admin(self, admin):
        r = requests.get(f"{API}/admin/lex-research/health", headers=admin, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("by_jurisdiction", "ai_cost_per_answer_by_tier", "ai_discovery", "tavily",
                  "source_changes_awaiting_review", "ai_discovery_enabled"):
            assert k in d
        assert set(d["ai_discovery"].keys()) >= {"calls", "cost_gbp"}
        assert isinstance(d["source_changes_awaiting_review"], int)
        assert isinstance(d["ai_discovery_enabled"], bool)

    def test_health_normal_403(self, normal):
        for p in ("health", "coverage", "source-changes"):
            r = requests.get(f"{API}/admin/lex-research/{p}", headers=normal, timeout=30)
            assert r.status_code == 403, (p, r.status_code)

    def test_health_unauth(self):
        r = requests.get(f"{API}/admin/lex-research/health", timeout=30)
        assert r.status_code in (401, 403)

    def test_toggle_normal_403(self, normal):
        r = requests.post(f"{API}/admin/lex-research/ai-discovery", json={"enabled": False}, headers=normal, timeout=30)
        assert r.status_code == 403


# --- Coverage register ---
class TestCoverage:
    def test_coverage(self, admin):
        r = requests.get(f"{API}/admin/lex-research/coverage", headers=admin, timeout=30)
        assert r.status_code == 200
        d = r.json()
        cov = {j["code"]: j["coverage"] for j in d["jurisdictions"]}
        for c in ("GB", "DE", "ES", "IT", "PL", "US"):
            assert cov.get(c) == "verified", (c, cov.get(c))
        for c in ("FR", "PT", "AU", "CA", "IN", "IE"):
            assert cov.get(c) == "official_site_search", (c, cov.get(c))
        for c in ("IQ", "PK", "CN", "AE"):
            assert cov.get(c) == "general_only", (c, cov.get(c))
        assert d["france_keys_configured"] is False


# --- Source-change queue ---
class TestSourceChanges:
    def test_review_flow(self, admin, mdb):
        ins = mdb.legal_source_changes.insert_one({
            "status": "needs_review", "label": "TEST_BGB §573", "url": "https://www.gesetze-im-internet.de/bgb/__573.html",
            "jurisdiction": "DE", "detected_at": datetime.now(timezone.utc).isoformat()})
        cid = str(ins.inserted_id)
        try:
            r = requests.get(f"{API}/admin/lex-research/source-changes", headers=admin, timeout=30)
            assert r.status_code == 200
            ids = [x["id"] for x in r.json()["items"]]
            assert cid in ids
            item = [x for x in r.json()["items"] if x["id"] == cid][0]
            assert item["label"] == "TEST_BGB §573" and "_id" not in item
            h = requests.get(f"{API}/admin/lex-research/health", headers=admin, timeout=60).json()
            assert h["source_changes_awaiting_review"] >= 1
            bad = requests.post(f"{API}/admin/lex-research/source-changes/{cid}/review", json={"outcome": "approved"},
                                headers=admin, timeout=30)
            assert bad.status_code == 400
            ok = requests.post(f"{API}/admin/lex-research/source-changes/{cid}/review",
                               json={"outcome": "guidance_flagged_for_lawyer"}, headers=admin, timeout=30)
            assert ok.status_code == 200 and ok.json()["ok"] is True
            doc = mdb.legal_source_changes.find_one({"_id": ins.inserted_id})
            assert doc["status"] == "reviewed" and doc["outcome"] == "guidance_flagged_for_lawyer"
            assert doc["reviewed_by"] == "admin@aiadvocate.co.uk"
            r2 = requests.get(f"{API}/admin/lex-research/source-changes", headers=admin, timeout=30)
            assert cid not in [x["id"] for x in r2.json()["items"]]
        finally:
            mdb.legal_source_changes.delete_one({"_id": ins.inserted_id})

    def test_review_unknown_id_404(self, admin):
        r = requests.post(f"{API}/admin/lex-research/source-changes/0123456789abcdef01234567/review",
                          json={"outcome": "no_guidance_affected"}, headers=admin, timeout=30)
        assert r.status_code == 404

    def test_review_malformed_id(self, admin):
        r = requests.post(f"{API}/admin/lex-research/source-changes/not-an-id/review",
                          json={"outcome": "no_guidance_affected"}, headers=admin, timeout=30)
        assert r.status_code in (400, 404), f"malformed id returned {r.status_code}"


# --- AI discovery toggle (always restore enabled=true) ---
class TestToggle:
    def test_toggle(self, admin):
        try:
            r = requests.post(f"{API}/admin/lex-research/ai-discovery", json={"enabled": False}, headers=admin, timeout=30)
            assert r.status_code == 200 and r.json()["enabled"] is False
            h = requests.get(f"{API}/admin/lex-research/health", headers=admin, timeout=60).json()
            assert h["ai_discovery_enabled"] is False
        finally:
            r = requests.post(f"{API}/admin/lex-research/ai-discovery", json={"enabled": True}, headers=admin, timeout=30)
            assert r.json()["enabled"] is True
        h = requests.get(f"{API}/admin/lex-research/health", headers=admin, timeout=60).json()
        assert h["ai_discovery_enabled"] is True


# --- Paid chat calls (4 total) ---
def _chat(admin, msg, country, lang):
    r = requests.post(f"{API}/lex/chat", json={"message": msg, "country": country, "language": lang, "auto_detect": True},
                      headers=admin, timeout=180)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    try:
        data = json.load(open(OUT)) if os.path.exists(OUT) else {}
    except Exception:
        data = {}
    data[country] = {"response": d.get("response"), "citations": d.get("citations"), "research_status": d.get("research_status")}
    json.dump(data, open(OUT, "w"), indent=1, ensure_ascii=False)
    return d


def _urls(d):
    return " ".join(json.dumps(c, ensure_ascii=False) for c in (d.get("citations") or []))


class TestChat:
    def test_de_eigenbedarf(self, admin):
        d = _chat(admin, "Mein Vermieter hat mir wegen Eigenbedarf gekündigt", "DE", "de-DE")
        u = _urls(d)
        assert "gesetze-im-internet.de" in u
        for s in ("573", "573c", "574"):
            assert s in u, s

    def test_pl_labour(self, admin):
        d = _chat(admin, "Pracodawca mnie zwolnił. Ile mam czasu na odwołanie do sądu pracy?", "PL", "pl-PL")
        assert "21 dni" in d["response"]
        u = _urls(d)
        assert "api.sejm.gov.pl" in u and "art-264" in u

    def test_us_texas(self, admin):
        d = _chat(admin, "My landlord in Texas kept my security deposit", "US", "en-US")
        u = _urls(d)
        assert "uscode" not in u.lower() and "govinfo.gov" not in u.lower(), u

    def test_gb_regression(self, admin):
        d = _chat(admin, "My employer sacked me after 3 years", "GB", "en-GB")
        assert "legislation.gov.uk" in _urls(d)
