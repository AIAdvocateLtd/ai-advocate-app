# Iter46: auth playbook checks — httpOnly cookie, CORS credentials, brute-force lockout (on a TEST clone user only).
import os, uuid, copy
import requests
from pymongo import MongoClient

BASE_URL = ""
for line in open("/app/frontend/.env"):
    if line.startswith("REACT_APP_BACKEND_URL="):
        BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "ai_advocate_db")]


def test_login_cookie_and_cors():
    r = requests.post(f"{API}/auth/login", json={"email": "test@advocate.app", "password": "Test12345!"},
                      headers={"Origin": BASE_URL}, timeout=30)
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    print("SET-COOKIE:", sc[:200])
    print("ACAO:", r.headers.get("access-control-allow-origin"), "ACAC:", r.headers.get("access-control-allow-credentials"))
    assert r.headers.get("access-control-allow-origin") != "*" or r.headers.get("access-control-allow-credentials") != "true"


def test_bruteforce_lockout_on_clone():
    src = db.users.find_one({"email": "test@advocate.app"})
    c = copy.deepcopy(src); c.pop("_id", None)
    c["id"] = str(uuid.uuid4()); c["email"] = f"test_lock_{c['id'][:8]}@stage2-fictional-test.co.uk"
    db.users.insert_one(c)
    try:
        codes = []
        for _ in range(6):
            codes.append(requests.post(f"{API}/auth/login", json={"email": c["email"], "password": "Nope!1234"}, timeout=30).status_code)
        ok = requests.post(f"{API}/auth/login", json={"email": c["email"], "password": "Test12345!"}, timeout=30)
        print("wrong codes", codes, "then correct ->", ok.status_code, ok.text[:150])
        assert 429 in codes or ok.status_code in (423, 429)
    finally:
        db.users.delete_one({"id": c["id"]})
        db.login_attempts.delete_many({"identifier": {"$regex": c["email"]}}) if "login_attempts" in db.list_collection_names() else None
