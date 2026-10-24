# Iteration 37: Landing status, admin testimonials CRUD, taster answer + import
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}
USER = {"email": "test@advocate.app", "password": "Test12345!"}
TP = "https://www.trustpilot.com/review/aiadvocate.co.uk"


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {creds['email']}: {r.status_code} {r.text[:200]}")
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def user():
    return _login(USER)


# --- Public landing status
class TestLanding:
    def test_public_landing(self):
        r = requests.get(f"{BASE_URL}/api/public/landing", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["firms_live"] is False
        assert d["trustpilot_url"] == TP
        assert isinstance(d["testimonials"], list)
        n = mdb.testimonials.count_documents({})
        assert len(d["testimonials"]) == (min(n, 12) if n >= 3 else 0)
        for t in d["testimonials"]:
            assert "_id" not in t


# --- Admin testimonials CRUD + auth
class TestTestimonials:
    created = []

    def test_unauth(self):
        r = requests.get(f"{BASE_URL}/api/admin/testimonials", timeout=20)
        assert r.status_code in (401, 403)

    def test_non_admin(self, user):
        r = user.get(f"{BASE_URL}/api/admin/testimonials", timeout=20)
        assert r.status_code in (401, 403)
        r = user.post(f"{BASE_URL}/api/admin/testimonials", json={"name": "x", "quote": "hello world"}, timeout=20)
        assert r.status_code in (401, 403)

    def test_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/testimonials", timeout=20)
        assert r.status_code == 200
        assert r.json()["min_shown"] == 3

    def test_bad_link(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/testimonials",
                       json={"name": "TEST_bad", "quote": "Great app", "link": "http://x.com"}, timeout=20)
        assert r.status_code == 400

    def test_validation(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/testimonials", json={"name": "TEST_v", "quote": "abc"}, timeout=20)
        assert r.status_code == 422
        r = admin.post(f"{BASE_URL}/api/admin/testimonials", json={"name": "TEST_v", "quote": "abcdef", "stars": 6}, timeout=20)
        assert r.status_code == 422

    def test_add_default_link_and_delete(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/testimonials",
                       json={"name": "TEST_Reviewer", "stars": 4, "quote": "Very helpful <b>app</b>", "review_date": "Jan 2026"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["link"] == TP and d["stars"] == 4 and "_id" not in d
        items = admin.get(f"{BASE_URL}/api/admin/testimonials", timeout=20).json()["items"]
        assert any(i["id"] == d["id"] for i in items)
        land = requests.get(f"{BASE_URL}/api/public/landing", timeout=20).json()
        assert any(i["id"] == d["id"] for i in land["testimonials"])  # >=3 exist now
        r = admin.delete(f"{BASE_URL}/api/admin/testimonials/{d['id']}", timeout=20)
        assert r.status_code == 200 and r.json()["deleted"] is True
        r = admin.delete(f"{BASE_URL}/api/admin/testimonials/{d['id']}", timeout=20)
        assert r.status_code == 404


# --- Taster import
class TestTasterImport:
    def test_import_unauth(self):
        r = requests.post(f"{BASE_URL}/api/lex/taster/import", json={"taster_id": "x"}, timeout=20)
        assert r.status_code in (401, 403)

    def test_import_unknown(self, user):
        r = user.post(f"{BASE_URL}/api/lex/taster/import", json={"taster_id": str(uuid.uuid4())}, timeout=20)
        assert r.status_code == 200 and r.json()["imported"] is False

    def test_taster_and_import(self, user):
        mdb.taster_usage.delete_many({})
        stored_dev = f"TEST_{uuid.uuid4()}"
        r = requests.post(f"{BASE_URL}/api/lex/taster",
                          json={"message": "Can my landlord keep my deposit for normal wear?", "device_id": stored_dev,
                                "language": "en-GB", "country": "GB"}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["taster_id"] and len(d["response"]) > 20
        stored = mdb.taster_answers.find_one({"id": d["taster_id"]})
        assert stored and stored["claimed_by"] is None
        r1 = user.post(f"{BASE_URL}/api/lex/taster/import", json={"taster_id": d["taster_id"]}, timeout=20)
        assert r1.status_code == 200 and r1.json()["imported"] is True
        sid = r1.json()["session_id"]
        sessions = user.get(f"{BASE_URL}/api/lex/sessions", timeout=20).json()
        assert any(s["session_id"] == sid for s in sessions)
        msgs = user.get(f"{BASE_URL}/api/lex/sessions/{sid}", timeout=20).json()
        assert msgs[0]["user_message"].startswith("Can my landlord")
        assert msgs[0]["assistant_response"] == d["response"]
        r2 = user.post(f"{BASE_URL}/api/lex/taster/import", json={"taster_id": d["taster_id"]}, timeout=20)
        assert r2.json()["imported"] is False
        # second taster from same device should be 429 (NOTE: per-IP limit uses req.client.host = ingress IP, unreliable)
        r3 = requests.post(f"{BASE_URL}/api/lex/taster",
                           json={"message": "Another question here", "device_id": stored_dev}, timeout=30)
        assert r3.status_code == 429
        # cleanup imported convo
        mdb.conversations.delete_many({"session_id": sid})
        mdb.taster_usage.delete_many({})
