# Conveyancing Companion: CRUD, ownership, auth, Lex suggest + free-tier limit
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
FREE = ("test@advocate.app", "Test12345!")
ADMIN = ("admin@aiadvocate.co.uk", "AdminLex2026!")


def _env(key):
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": creds[0], "password": creds[1]})
    if r.status_code != 200:
        pytest.skip(f"login failed {creds[0]}: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def free_h():
    return _login(FREE)


@pytest.fixture(scope="module")
def admin_h():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def created(free_h):
    ids = []
    yield ids
    for i in ids:
        requests.delete(f"{BASE_URL}/api/conveyancing/{i}", headers=free_h)


SUG = {"form": "TA6", "section": "Boundaries", "question": "Who owns or maintains each boundary?",
       "facts": "I have always maintained the left fence. Right side hedge is the neighbour's."}


# Auth
class TestAuth:
    def test_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/conveyancing").status_code == 401
        assert requests.post(f"{BASE_URL}/api/conveyancing", json={"journey": "sell"}).status_code == 401
        assert requests.post(f"{BASE_URL}/api/conveyancing/suggest", json=SUG).status_code == 401


# CRUD
class TestCrud:
    def test_list_free_shape(self, free_h):
        mdb.users.update_one({"email": FREE[0]}, {"$unset": {"conv_suggest_count": ""}})
        r = requests.get(f"{BASE_URL}/api/conveyancing", headers=free_h)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["items"], list)
        assert d["suggestions_left"] == 3

    def test_list_admin_unlimited(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/conveyancing", headers=admin_h)
        assert r.status_code == 200 and r.json()["suggestions_left"] is None

    def test_invalid_journey(self, free_h):
        r = requests.post(f"{BASE_URL}/api/conveyancing", json={"journey": "rent"}, headers=free_h)
        assert r.status_code == 422

    def test_create_patch_get_delete(self, free_h, created, admin_h):
        r = requests.post(f"{BASE_URL}/api/conveyancing", json={"journey": "sell", "address": " TEST_1 High St "}, headers=free_h)
        assert r.status_code == 200
        m = r.json()
        created.append(m["id"])
        assert m["journey"] == "sell" and m["address"] == "TEST_1 High St" and m["stages_done"] == []
        assert "_id" not in m
        p = {"stages_done": ["agent", "offer"], "notes": {"agent": "TEST note"},
             "form_answers": {"TA6-boundaries": {"facts": "f", "answer": "a"}}, "address": "TEST_2 Low St"}
        r = requests.patch(f"{BASE_URL}/api/conveyancing/{m['id']}", json=p, headers=free_h)
        assert r.status_code == 200
        u = r.json()
        assert u["stages_done"] == ["agent", "offer"] and u["notes"]["agent"] == "TEST note"
        assert u["form_answers"]["TA6-boundaries"]["answer"] == "a" and u["address"] == "TEST_2 Low St"
        items = requests.get(f"{BASE_URL}/api/conveyancing", headers=free_h).json()["items"]
        got = [i for i in items if i["id"] == m["id"]][0]
        assert got["stages_done"] == ["agent", "offer"] and got["address"] == "TEST_2 Low St"
        # Ownership: other user gets 404
        assert requests.patch(f"{BASE_URL}/api/conveyancing/{m['id']}", json={"address": "x"}, headers=admin_h).status_code == 404
        assert requests.delete(f"{BASE_URL}/api/conveyancing/{m['id']}", headers=admin_h).status_code == 404
        assert m["id"] not in [i["id"] for i in requests.get(f"{BASE_URL}/api/conveyancing", headers=admin_h).json()["items"]]
        # Delete
        r = requests.delete(f"{BASE_URL}/api/conveyancing/{m['id']}", headers=free_h)
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert requests.delete(f"{BASE_URL}/api/conveyancing/{m['id']}", headers=free_h).status_code == 404
        created.remove(m["id"])

    def test_create_buy(self, free_h, created):
        r = requests.post(f"{BASE_URL}/api/conveyancing", json={"journey": "buy"}, headers=free_h)
        assert r.status_code == 200 and r.json()["journey"] == "buy"
        created.append(r.json()["id"])


# Lex suggest (real LLM, 2-3 calls total)
class TestSuggest:
    def test_validation(self, free_h):
        r = requests.post(f"{BASE_URL}/api/conveyancing/suggest", json={**SUG, "facts": "a"}, headers=free_h)
        assert r.status_code == 422
        r = requests.post(f"{BASE_URL}/api/conveyancing/suggest", json={**SUG, "form": "TA99"}, headers=free_h)
        assert r.status_code == 422

    def test_free_first_call(self, free_h):
        mdb.users.update_one({"email": FREE[0]}, {"$unset": {"conv_suggest_count": ""}})
        r = requests.post(f"{BASE_URL}/api/conveyancing/suggest", json=SUG, headers=free_h, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["suggestions_left"] == 2
        assert "**Suggested wording**" in d["suggestion"] and "**Check before you submit**" in d["suggestion"]

    def test_free_third_then_402(self, free_h):
        mdb.users.update_one({"email": FREE[0]}, {"$set": {"conv_suggest_count": 2}})
        r = requests.post(f"{BASE_URL}/api/conveyancing/suggest", json=SUG, headers=free_h, timeout=90)
        assert r.status_code == 200 and r.json()["suggestions_left"] == 0
        r = requests.post(f"{BASE_URL}/api/conveyancing/suggest", json=SUG, headers=free_h, timeout=90)
        assert r.status_code == 402
        assert "Upgrade" in r.json()["detail"]
        assert requests.get(f"{BASE_URL}/api/conveyancing", headers=free_h).json()["suggestions_left"] == 0
        cnt = mdb.users.find_one({"email": FREE[0]})["conv_suggest_count"]
        assert cnt == 3

    def test_admin_unlimited(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/conveyancing/suggest", json=SUG, headers=admin_h, timeout=90)
        assert r.status_code == 200 and r.json()["suggestions_left"] is None
        assert "**Suggested wording**" in r.json()["suggestion"]
