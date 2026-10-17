# Iteration 36 — Will Writer (CRUD, generate per jurisdiction, PDF, tier gating, isolation), GDPR export, /pdf/inline
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"

mongo = MongoClient("mongodb://localhost:27017")["ai_advocate_db"]
ADMIN = {"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}

BASE_ANSWERS = {
    "full_name": "TEST_Jane Example", "address": "1 Test Street, London",
    "executors": "My sister, Anna Example", "residuary": "My sister Anna Example; if she dies before me, the British Red Cross",
    "specific_gifts": "My watch to my nephew Tom Example",
}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _signup_user():
    email = f"test_will_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "Test12345!", "full_name": "TEST Will"}, timeout=30)
    assert r.status_code == 200, r.text
    mongo.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    return email, r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def free_user():
    email, tok = _signup_user()
    yield email, tok
    u = mongo.users.find_one({"email": email})
    if u:
        mongo.wills.delete_many({"user_id": u["id"]})
    mongo.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def other_pro_user():
    email, tok = _signup_user()
    mongo.users.update_one({"email": email}, {"$set": {"comp_pro_until": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}})
    yield email, tok
    u = mongo.users.find_one({"email": email})
    if u:
        mongo.wills.delete_many({"user_id": u["id"]})
    mongo.users.delete_one({"email": email})


@pytest.fixture(scope="module")
def created_ids():
    ids = []
    yield ids
    for i in ids:
        mongo.wills.delete_one({"id": i})


# --- CRUD ---
class TestWillCrud:
    def test_create_update_get_list(self, admin_tok, created_ids):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": "ew", "answers": {"full_name": "TEST_Draft Person"}})
        assert r.status_code == 200, r.text
        w = r.json(); created_ids.append(w["id"])
        assert w["title"] == "Will of TEST_Draft Person" and w["answers"]["full_name"] == "TEST_Draft Person"
        assert "answers_enc" not in w and "_id" not in w and w["has_draft"] is False
        # encrypted at rest
        raw = mongo.wills.find_one({"id": w["id"]})
        assert "TEST_Draft Person" not in str(raw.get("answers_enc"))
        # update
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"id": w["id"], "jurisdiction": "scotland", "answers": {"full_name": "TEST_Updated"}})
        assert r.status_code == 200 and r.json()["jurisdiction"] == "scotland" and r.json()["title"] == "Will of TEST_Updated"
        g = requests.get(f"{API}/wills/{w['id']}", headers=_h(admin_tok)).json()
        assert g["answers"]["full_name"] == "TEST_Updated" and "full_text" not in g
        lst = requests.get(f"{API}/wills", headers=_h(admin_tok)).json()["wills"]
        item = next(x for x in lst if x["id"] == w["id"])
        assert "answers" not in item and "answers_enc" not in item and "draft_enc" not in item and "draft_text" not in item

    def test_invalid_jurisdiction(self, admin_tok):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": "mars", "answers": {}})
        assert r.status_code == 400

    def test_update_unknown_id_404(self, admin_tok):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"id": "nope-" + uuid.uuid4().hex, "jurisdiction": "ew", "answers": {}})
        assert r.status_code == 404

    def test_generate_missing_fields_400(self, admin_tok, created_ids):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": "ew", "answers": {"full_name": "TEST_Only Name"}})
        wid = r.json()["id"]; created_ids.append(wid)
        g = requests.post(f"{API}/wills/{wid}/generate", headers=_h(admin_tok), timeout=120)
        assert g.status_code == 400
        p = requests.get(f"{API}/wills/{wid}/pdf", headers=_h(admin_tok))
        assert p.status_code == 400

    def test_complexity_warnings(self, admin_tok, created_ids):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": "ew", "answers": {"full_name": "TEST_C", "complexity": {"owns_business": True, "trust_needed": True, "property_abroad": False, "bogus": True}}})
        created_ids.append(r.json()["id"])
        cw = r.json()["complexity_warnings"]
        assert len(cw) == 2 and any("business" in c for c in cw) and any("trust" in c for c in cw)


# --- Generate per jurisdiction (LLM) ---
@pytest.mark.parametrize("jur,country", [("ew", None), ("scotland", None), ("ni", None), ("other", "Spain")])
def test_generate_signing_block(admin_tok, created_ids, jur, country):
    r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": jur, "country": country, "answers": BASE_ANSWERS})
    wid = r.json()["id"]; created_ids.append(wid)
    g = requests.post(f"{API}/wills/{wid}/generate", headers=_h(admin_tok), timeout=180)
    assert g.status_code == 200, g.text
    d = g.json()
    assert d["has_draft"] is True and len(d["draft_text"]) > 300
    ft = d["full_text"]
    assert "**" not in d["draft_text"]
    if jur in ("ew", "ni"):
        assert "WITNESS 1" in ft and "WITNESS 2" in ft and "electronically" in ft
    elif jur == "scotland":
        assert "WITNESS 1" not in ft and "\nWITNESS\n" in ft and "every page" in ft
    else:
        assert "Spain" in ft and "notary" in ft and "WITNESS 1" not in ft
    if jur in ("ew", "ni"):
        assert "beneficiary" in ft
    # GET returns full_text
    gg = requests.get(f"{API}/wills/{wid}", headers=_h(admin_tok)).json()
    assert gg["full_text"] == ft
    # PDF
    p = requests.get(f"{API}/wills/{wid}/pdf", headers=_h(admin_tok), timeout=60)
    assert p.status_code == 200 and p.headers["content-type"].startswith("application/pdf") and p.content[:4] == b"%PDF"
    # encrypted draft at rest
    raw = mongo.wills.find_one({"id": wid})
    assert "Anna Example" not in str(raw.get("draft_enc"))


# --- Isolation, tier gating, delete ---
class TestAccess:
    def test_other_user_404(self, admin_tok, other_pro_user, created_ids):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": "ew", "answers": {"full_name": "TEST_Private"}})
        wid = r.json()["id"]; created_ids.append(wid)
        _, tok = other_pro_user
        h = _h(tok)
        assert requests.get(f"{API}/wills", headers=h).status_code == 200
        assert all(x["id"] != wid for x in requests.get(f"{API}/wills", headers=h).json()["wills"])
        assert requests.get(f"{API}/wills/{wid}", headers=h).status_code == 404
        assert requests.post(f"{API}/wills/{wid}/generate", headers=h).status_code == 404
        assert requests.get(f"{API}/wills/{wid}/pdf", headers=h).status_code == 404
        assert requests.post(f"{API}/wills", headers=h, json={"id": wid, "jurisdiction": "ew", "answers": {}}).status_code == 404
        assert requests.delete(f"{API}/wills/{wid}", headers=h).status_code == 404
        assert requests.get(f"{API}/wills/{wid}", headers=_h(admin_tok)).status_code == 200

    def test_free_user_402(self, free_user):
        _, tok = free_user
        h = _h(tok)
        assert requests.get(f"{API}/wills", headers=h).status_code == 402
        assert requests.post(f"{API}/wills", headers=h, json={"jurisdiction": "ew", "answers": {}}).status_code == 402
        assert requests.get(f"{API}/wills/x", headers=h).status_code == 402
        assert requests.post(f"{API}/wills/x/generate", headers=h).status_code == 402
        assert requests.get(f"{API}/wills/x/pdf", headers=h).status_code == 402
        assert requests.delete(f"{API}/wills/x", headers=h).status_code == 404

    def test_unauth_401(self):
        assert requests.get(f"{API}/wills").status_code in (401, 403)

    def test_delete(self, admin_tok):
        r = requests.post(f"{API}/wills", headers=_h(admin_tok), json={"jurisdiction": "ew", "answers": {"full_name": "TEST_Del"}})
        wid = r.json()["id"]
        d = requests.delete(f"{API}/wills/{wid}", headers=_h(admin_tok))
        assert d.status_code == 200 and d.json()["deleted"] is True
        assert requests.get(f"{API}/wills/{wid}", headers=_h(admin_tok)).status_code == 404


# --- GDPR export ---
def test_gdpr_export_includes_wills(other_pro_user):
    _, tok = other_pro_user
    h = _h(tok)
    w = requests.post(f"{API}/wills", headers=h, json={"jurisdiction": "ew", "answers": {"full_name": "TEST_Export Me"}}).json()
    r = requests.get(f"{API}/users/me/export", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    wills = r.json()["wills"]
    e = next(x for x in wills if x["id"] == w["id"])
    assert e["answers"]["full_name"] == "TEST_Export Me" and "draft_text" in e and "answers_enc" not in e


# --- /pdf/inline used by ShareActions ---
def test_pdf_inline(admin_tok):
    r = requests.post(f"{API}/pdf/inline", headers=_h(admin_tok), json={"title": "Lex reply", "body": "Hello world\n\nLine two", "filename": "Lex_reply.pdf"})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
