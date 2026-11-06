# Stage 3 (Urgent Lex Repair): login limits, free lifetime allowance, abuse guards, admin fair-use API, brake, regression.
import os, time, uuid, random, threading
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@aiadvocate.co.uk", "AdminLex2026!")
PRO = ("appstore.reviewer@aiadvocate.co.uk", "Review2026!Lex")
TEST = ("test@advocate.app", "Test12345!")

_mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
mdb = _mc[os.environ.get("DB_NAME", "ai_advocate_db")]
CREATED_USER_IDS = []


def rip():
    return f"198.51.{random.randint(1, 254)}.{random.randint(1, 254)}"


def login(email, pw, ip=None):
    h = {"X-Forwarded-For": ip} if ip else {}
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, headers=h, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"] if "token" in r.json() else r.json()["access_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def pro_tok():
    return login(*PRO)


@pytest.fixture(scope="module")
def free_user():
    ip = rip()
    email = f"test_s3_{uuid.uuid4().hex[:8]}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "Test12345!", "full_name": "TEST_S3",
                                                  "device_id": f"TEST_dev_{uuid.uuid4().hex}"},
                      headers={"X-Forwarded-For": ip}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    u = mdb.users.find_one({"email": email}, {"id": 1})
    CREATED_USER_IDS.append(u["id"])
    mdb.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    yield {"email": email, "token": tok, "id": u["id"]}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED_USER_IDS:
        u = mdb.users.find_one({"id": uid}, {"email": 1})
        mdb.users.delete_one({"id": uid})
        mdb.usage.delete_many({"user_id": uid})
        if u:
            mdb.usage.delete_many({"user_id": {"$in": [f"email:{u['email']}", __import__("stage3").email_key(u["email"])]}})
        mdb.s3_events.delete_many({"user_id": uid})
        mdb.s3_consumptions.delete_many({"user_id": uid})
        mdb.chat_sessions.delete_many({"user_id": uid})


# ---------- Login limits ----------
class TestLoginLimits:
    def test_user_login_lockout_then_other_email_ok(self):
        ip = rip()
        email = f"TEST_nouser_{uuid.uuid4().hex[:6]}@advocate.app"
        for i in range(5):
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong"}, headers={"X-Forwarded-For": ip})
            assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials", (i, r.text)
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong"}, headers={"X-Forwarded-For": ip})
        assert r.status_code == 429 and "Too many sign-in attempts" in r.json()["detail"], r.text
        # Wrong password for real account -> same generic message
        r = requests.post(f"{API}/auth/login", json={"email": TEST[0], "password": "nope_wrong"}, headers={"X-Forwarded-For": ip})
        assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"
        # Different, un-locked email succeeds from the same IP
        assert login(*TEST, ip=ip)

    @pytest.mark.parametrize("path", ["/firm/login", "/firm/users/login"])
    def test_firm_login_lockout(self, path):
        ip = rip()
        email = f"TEST_nofirm_{uuid.uuid4().hex[:6]}@advocate.app"
        codes = [requests.post(f"{API}{path}", json={"email": email, "password": "wrong"},
                               headers={"X-Forwarded-For": ip}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes

    def test_reset_password_invalid_token_limit(self):
        ip = rip()
        codes = [requests.post(f"{API}/auth/reset-password", json={"token": f"bad{i}", "new_password": "Whatever123!"},
                               headers={"X-Forwarded-For": ip}).status_code for i in range(11)]
        assert codes[:10] == [400] * 10 and codes[10] == 429, codes


# ---------- Admin API ----------
class TestAdminFairUse:
    def test_get_fair_use(self, admin_tok):
        r = requests.get(f"{API}/admin/fair-use", headers=H(admin_tok))
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("settings", "brake", "estimated_month_gbp", "estimate_note", "flags"):
            assert k in d
        assert d["settings"]["thresholds"]["plus"]["flag"] == 1.5
        assert d["brake"]["brake_at_gbp"] == pytest.approx(d["brake"]["alert_at_gbp"] * 2)
        assert "Estimated AI cost" in d["estimate_note"]

    def test_non_admin_403(self):
        tok = login(*TEST)
        assert requests.get(f"{API}/admin/fair-use", headers=H(tok)).status_code == 403
        assert requests.post(f"{API}/admin/fair-use/brake", json={"action": "pause"}, headers=H(tok)).status_code == 403

    def test_thresholds_and_switch_update_restore(self, admin_tok):
        r = requests.put(f"{API}/admin/fair-use/settings", json={"thresholds": {"plus": {"flag": 2}}, "pass_limits_enabled": False}, headers=H(admin_tok))
        assert r.status_code == 200
        assert r.json()["thresholds"]["plus"]["flag"] == 2.0 and r.json()["thresholds"]["plus"]["cooldown"] == 4.0
        assert r.json()["pass_limits_enabled"] is False
        r = requests.put(f"{API}/admin/fair-use/settings", json={"thresholds": {"plus": {"flag": 1.5}}, "pass_limits_enabled": True}, headers=H(admin_tok))
        assert r.json()["thresholds"]["plus"]["flag"] == 1.5 and r.json()["pass_limits_enabled"] is True

    def test_effective_date_shows_paid_allowances(self, admin_tok, pro_tok):
        r = requests.put(f"{API}/admin/fair-use/settings", json={"paid_limits_effective_at": "2025-01-01T00:00:00+00:00"}, headers=H(admin_tok))
        assert r.status_code == 200
        try:
            time.sleep(1)
            u = requests.get(f"{API}/subscription/usage", headers=H(pro_tok)).json()
            print("pro fair_use with limits active:", u.get("fair_use"))
            assert "msgs" in u["fair_use"]["items"] and u["fair_use"]["items"]["msgs"]["limit"] == 600
        finally:
            r = requests.put(f"{API}/admin/fair-use/settings", json={"paid_limits_effective_at": None}, headers=H(admin_tok))
            assert r.json()["paid_limits_effective_at"] is None
        u = requests.get(f"{API}/subscription/usage", headers=H(pro_tok)).json()
        assert u["fair_use"]["items"] == {}

    def test_exempt_toggle(self, admin_tok, free_user):
        r = requests.post(f"{API}/admin/fair-use/exempt", json={"email": free_user["email"], "exempt": True}, headers=H(admin_tok))
        assert r.status_code == 200
        assert mdb.users.find_one({"id": free_user["id"]})["s3_exempt"] is True
        d = requests.get(f"{API}/admin/fair-use", headers=H(admin_tok)).json()
        assert free_user["email"] in [u["email"] for u in d["exempt_users"]]
        requests.post(f"{API}/admin/fair-use/exempt", json={"email": free_user["email"], "exempt": False}, headers=H(admin_tok))
        assert mdb.users.find_one({"id": free_user["id"]})["s3_exempt"] is False
        r = requests.post(f"{API}/admin/fair-use/exempt", json={"email": "TEST_nobody_x@advocate.app", "exempt": True}, headers=H(admin_tok))
        assert r.status_code == 404


# ---------- Brake ----------
class TestBrake:
    def test_pause_blocks_free_not_pro_then_resume(self, admin_tok, pro_tok, free_user):
        r = requests.post(f"{API}/admin/fair-use/brake", json={"action": "pause"}, headers=H(admin_tok))
        assert r.status_code == 200 and r.json()["paused"] is True and r.json()["reason"] == "manual"
        try:
            time.sleep(1)
            r = requests.post(f"{API}/lex/chat", json={"message": "TEST brake check question about tenancy deposit"}, headers=H(free_user["token"]))
            assert r.status_code == 429 and "paused until midnight" in r.json()["detail"], r.text
            r = requests.post(f"{API}/lex/taster", json={"message": "Can my landlord keep my deposit?", "device_id": f"TEST_{uuid.uuid4().hex}"},
                              headers={"X-Forwarded-For": rip()})
            assert r.status_code == 429 and "paused until midnight" in r.json()["detail"], r.text
            r = requests.post(f"{API}/lex/chat", json={"message": "In one sentence, what is a section 21 notice?"}, headers=H(pro_tok), timeout=120)
            assert r.status_code == 200, r.text[:300]
            print("PRO reply while brake paused:", str(r.json())[:200])
        finally:
            r = requests.post(f"{API}/admin/fair-use/brake", json={"action": "resume"}, headers=H(admin_tok))
            assert r.json()["paused"] is False
        u = requests.get(f"{API}/subscription/usage", headers=H(free_user["token"])).json()
        assert u["fair_use"]["items"]["free_actions"]["used"] == 0, "brake-blocked request must not consume"

    def test_override_and_resume(self, admin_tok):
        r = requests.post(f"{API}/admin/fair-use/brake", json={"action": "override"}, headers=H(admin_tok))
        assert r.json()["manual"] == "override" and r.json()["paused"] is False
        r = requests.post(f"{API}/admin/fair-use/brake", json={"action": "resume"}, headers=H(admin_tok))
        assert r.json()["manual"] is None


# ---------- Free lifetime + abuse guards ----------
class TestFreeLifetime:
    def test_flow(self, free_user):
        h = H(free_user["token"])
        u = requests.get(f"{API}/subscription/usage", headers=h).json()
        assert u["fair_use"]["items"]["free_actions"] == {"used": 0, "limit": 2, "period": "lifetime"}
        # Deep Think paywall still 402
        r = requests.post(f"{API}/lex/chat", json={"message": "deep think test", "deep_think": True}, headers=h)
        assert r.status_code == 402
        msg1 = "What notice must a landlord give in England to end an assured shorthold tenancy?"
        resp = requests.post(f"{API}/lex/chat/stream", json={"message": msg1}, headers=h, stream=True, timeout=180)
        assert resp.status_code == 200, resp.text[:300]
        it = resp.iter_lines()
        first = next(it)
        print("stream first line:", first[:120])
        dup = requests.post(f"{API}/lex/chat/stream", json={"message": msg1}, headers=h, timeout=30)
        print("dup:", dup.status_code, dup.text[:200])
        other = requests.post(f"{API}/lex/chat/stream", json={"message": "Different question about council tax"}, headers=h, timeout=30)
        print("other:", other.status_code, other.text[:200])
        body = b"".join([first] + list(it)).decode(errors="ignore")
        assert '"done"' in body, body[-300:]
        assert dup.status_code == 429 and "already working on that message" in dup.json()["detail"]
        assert other.status_code == 429 and "still answering" in other.json()["detail"]
        time.sleep(1)
        u = requests.get(f"{API}/subscription/usage", headers=h).json()
        assert u["fair_use"]["items"]["free_actions"]["used"] == 1, u
        # lock released -> 2nd message works
        r = requests.post(f"{API}/lex/chat", json={"message": "Briefly, how long do I have to claim unfair dismissal?"}, headers=h, timeout=180)
        assert r.status_code == 200, r.text[:300]
        u = requests.get(f"{API}/subscription/usage", headers=h).json()
        assert u["fair_use"]["items"]["free_actions"]["used"] == 2, u
        r = requests.post(f"{API}/lex/chat", json={"message": "Third question about small claims court fees"}, headers=h, timeout=60)
        assert r.status_code == 429 and "2 free Lex questions" in r.json()["detail"], r.text
        r = requests.post(f"{API}/lex/chat/stream", json={"message": "Fourth question about parking fines appeal"}, headers=h, timeout=60)
        assert r.status_code == 429 and "2 free Lex questions" in r.json()["detail"], r.text
        u = requests.get(f"{API}/subscription/usage", headers=h).json()
        assert u["fair_use"]["items"]["free_actions"]["used"] == 2


# ---------- Regression ----------
class TestRegression:
    def test_admin_endpoints(self, admin_tok):
        for p in ("/admin/llm-spend", "/admin/stats"):
            r = requests.get(f"{API}{p}", headers=H(admin_tok))
            assert r.status_code == 200, (p, r.text[:200])

    def test_plans(self):
        r = requests.get(f"{API}/subscription/tiers")
        assert r.status_code == 200 and r.json()

    def test_final_settings_restored(self, admin_tok):
        s = requests.get(f"{API}/admin/fair-use", headers=H(admin_tok)).json()["settings"]
        for k in ("login_limits_enabled", "abuse_guards_enabled", "free_lifetime_enabled", "pass_limits_enabled",
                  "spend_guard_enabled", "site_brake_enabled"):
            assert s[k] is True, k
        assert s["paid_limits_effective_at"] is None and s["thresholds"]["plus"]["flag"] == 1.5
