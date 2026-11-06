# Stage 3 retest (iter48): XFF spoof-proof client IP, typed fair-use settings, usage_view device counter,
# independent Free brake, datetime-parsed paid_limits_active.
import os, time, uuid, hashlib, random
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

_mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
mdb = _mc[os.environ.get("DB_NAME", "ai_advocate_db")]
CREATED_USER_IDS, EXTRA_USAGE_KEYS, LOGIN_KEYS = [], [], set()


def _h(v):
    return hashlib.sha256((v or "").strip().lower().encode()).hexdigest()[:32]


def spoof():
    return f"203.0.113.{random.randint(1, 254)}"


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json().get("token") or r.json().get("access_token")


def real_ip_hash_for(email):
    """Find the IP hash the server recorded for a failed login of `email` (kind 'user')."""
    e = _h(f"user:{email}")
    row = mdb.login_attempts.find_one({"scope": "acct_ip", "key": {"$regex": f"^{e}:"}})
    return row["key"].split(":", 1)[1] if row else None


def clear_login_rows(emails, ip_hash=None):
    for em in emails:
        for kind in ("user", "firm", "firm_user"):
            e = _h(f"{kind}:{em}")
            mdb.login_attempts.delete_many({"scope": "acct", "key": e})
            mdb.login_attempts.delete_many({"scope": "acct_ip", "key": {"$regex": f"^{e}:"}})
    if ip_hash:
        mdb.login_attempts.delete_many({"scope": {"$in": ["ip", "reset_ip"]}, "key": ip_hash})


@pytest.fixture(scope="module")
def admin_tok():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def pro_tok():
    return login(*PRO)


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_tok):
    # shared preview egress IP: lift the 3-per-network signup cap for the run, restore to 3 after
    requests.put(f"{API}/admin/fair-use/settings", json={"free_signups_per_network_7d": 20}, headers=H(admin_tok))
    yield
    # restore settings
    requests.put(f"{API}/admin/fair-use/settings", json={
        "free_lifetime_enabled": True, "paid_limits_effective_at": None, "free_signups_per_network_7d": 3, "thresholds": {"plus": {"flag": 1.5}}},
        headers=H(admin_tok))
    requests.post(f"{API}/admin/fair-use/brake", json={"action": "resume"}, headers=H(admin_tok))
    for uid in CREATED_USER_IDS:
        u = mdb.users.find_one({"id": uid}, {"email": 1})
        mdb.users.delete_one({"id": uid})
        mdb.usage.delete_many({"user_id": uid})
        if u:
            mdb.usage.delete_many({"user_id": f"email:{u['email']}"})
        mdb.s3_events.delete_many({"user_id": uid})
        mdb.s3_consumptions.delete_many({"user_id": uid})
        mdb.chat_sessions.delete_many({"user_id": uid})
    for k in EXTRA_USAGE_KEYS:
        mdb.usage.delete_many({"user_id": k})


def make_free_user(device_id=None):
    email = f"test_s3r_{uuid.uuid4().hex[:8]}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "Test12345!", "full_name": "TEST_S3R",
                                                  "device_id": device_id or f"TEST_dev_{uuid.uuid4().hex}"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    u = mdb.users.find_one({"email": email}, {"id": 1, "signup_device_id": 1, "signup_network_ip": 1})
    CREATED_USER_IDS.append(u["id"])
    mdb.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    return {"email": email, "token": d.get("token") or d.get("access_token"), "id": u["id"],
            "device": u.get("signup_device_id"), "net_ip": u.get("signup_network_ip")}


# ---------- FIX 1: X-Forwarded-For spoofing ----------
class TestXffSpoof:
    def test_account_ip_lockout_with_rotating_xff(self):
        email = f"TEST_xff_{uuid.uuid4().hex[:6]}@advocate.app"
        spoofs = [spoof() for _ in range(6)]
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong"},
                               headers={"X-Forwarded-For": s}).status_code for s in spoofs]
        ih = real_ip_hash_for(email)
        try:
            assert codes[:5] == [401] * 5 and codes[5] == 429, codes
            assert ih and ih not in {_h(s) for s in spoofs}, "spoofed XFF value was used as client IP"
            print("recorded ip hash:", ih, "== hash(container egress)?", ih == _h(requests.get("https://ifconfig.me", timeout=10).text.strip()))
        finally:
            clear_login_rows([email], ih)

    def test_per_ip_limit_not_bypassed_by_rotating_xff(self):
        emails = [f"TEST_xffip_{i}_{uuid.uuid4().hex[:6]}@advocate.app" for i in range(21)]
        codes = []
        for em in emails:
            codes.append(requests.post(f"{API}/auth/login", json={"email": em, "password": "wrong"},
                                       headers={"X-Forwarded-For": spoof()}).status_code)
        ih = real_ip_hash_for(emails[0])
        try:
            assert codes[:20] == [401] * 20 and codes[20] == 429, codes
            # even a valid account is now blocked from this IP
            r = requests.post(f"{API}/auth/login", json={"email": PRO[0], "password": PRO[1]}, headers={"X-Forwarded-For": spoof()})
            assert r.status_code == 429, r.text[:200]
        finally:
            clear_login_rows(emails, ih)
        assert requests.post(f"{API}/auth/login", json={"email": PRO[0], "password": PRO[1]}).status_code == 200


# ---------- FIX 2: typed settings ----------
class TestSettingsValidation:
    @pytest.mark.parametrize("body", [
        {"thresholds": {"plus": {"flag": "abc"}}},
        {"thresholds": {"plus": {"flag": -1}}},
        {"free_lifetime_actions": -1},
        {"free_lifetime_actions": "abc"},
        {"burst_per_minute": 0},
        {"site_brake_multiplier": 0.5},
        {"thresholds": {"gold": {"flag": 1}}},
        {"paid_limits_effective_at": "abc"},
    ])
    def test_invalid_422(self, admin_tok, body):
        r = requests.put(f"{API}/admin/fair-use/settings", json=body, headers=H(admin_tok))
        assert r.status_code == 422, (body, r.status_code, r.text[:200])

    def test_nulls_ignored(self, admin_tok):
        before = requests.get(f"{API}/admin/fair-use", headers=H(admin_tok)).json()["settings"]
        r = requests.put(f"{API}/admin/fair-use/settings", json={"burst_per_minute": None, "free_lifetime_actions": None,
                                                                 "thresholds": {"plus": {"flag": None}}}, headers=H(admin_tok))
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["burst_per_minute"] == before["burst_per_minute"]
        assert d["free_lifetime_actions"] == before["free_lifetime_actions"]
        assert d["thresholds"]["plus"]["flag"] == before["thresholds"]["plus"]["flag"]
        doc = mdb.app_settings.find_one({"_id": "stage3"})
        assert doc.get("burst_per_minute", 8) is not None and doc.get("free_lifetime_actions", 2) is not None

    @pytest.mark.parametrize("val,expected", [
        ("2099-01-01", "2099-01-01T00:00:00+00:00"),
        ("2099-01-01T10:00:00Z", "2099-01-01T10:00:00+00:00"),
        ("2099-06-01T10:00:00+01:00", "2099-06-01T10:00:00+01:00"),
    ])
    def test_effective_at_normalised_then_null_clears(self, admin_tok, val, expected):
        r = requests.put(f"{API}/admin/fair-use/settings", json={"paid_limits_effective_at": val}, headers=H(admin_tok))
        try:
            assert r.status_code == 200, r.text[:200]
            assert r.json()["paid_limits_effective_at"] == expected, r.json()["paid_limits_effective_at"]
            assert mdb.app_settings.find_one({"_id": "stage3"})["paid_limits_effective_at"] == expected
        finally:
            r = requests.put(f"{API}/admin/fair-use/settings", json={"paid_limits_effective_at": None}, headers=H(admin_tok))
            assert r.json()["paid_limits_effective_at"] is None


# ---------- FIX 5: paid_limits_active datetime parsing ----------
class TestPaidLimitsActive:
    @pytest.mark.parametrize("val,active", [("2020-01-01", True), ("2099-01-01", False),
                                            ("2020-01-01T00:00:00Z", True), ("2099-12-31T23:59:59+05:00", False)])
    def test_effective_dates(self, admin_tok, pro_tok, val, active):
        r = requests.put(f"{API}/admin/fair-use/settings", json={"paid_limits_effective_at": val}, headers=H(admin_tok))
        assert r.status_code == 200
        try:
            items = requests.get(f"{API}/subscription/usage", headers=H(pro_tok)).json()["fair_use"]["items"]
            assert ("msgs" in items) is active, (val, items)
        finally:
            requests.put(f"{API}/admin/fair-use/settings", json={"paid_limits_effective_at": None}, headers=H(admin_tok))


# ---------- FIX 3 + FIX 4 ----------
class TestFreeUsageAndBrake:
    def test_usage_view_uses_device_counter(self):
        dev = f"TEST_dev_{uuid.uuid4().hex}"
        u = make_free_user(dev)
        assert u["device"] == dev, u
        print("signup_network_ip recorded:", u["net_ip"])
        assert not (u["net_ip"] or "").startswith("203.0.113.")
        key = f"device:{dev}"
        EXTRA_USAGE_KEYS.append(key)
        mdb.usage.update_one({"user_id": key, "bucket": "s3-lifetime", "feature": "free_actions"},
                             {"$set": {"count": 2}}, upsert=True)
        fa = requests.get(f"{API}/subscription/usage", headers=H(u["token"])).json()["fair_use"]["items"]["free_actions"]
        assert fa["used"] == 2 and fa["limit"] == 2, fa
        # enforcement agrees (denied before any LLM call)
        r = requests.post(f"{API}/lex/chat", json={"message": "TEST device counter check"}, headers=H(u["token"]), timeout=60)
        assert r.status_code == 429 and "2 free Lex questions" in r.json()["detail"], r.text[:200]

    def test_brake_independent_of_free_lifetime_switch(self, admin_tok):
        u = make_free_user()
        r = requests.put(f"{API}/admin/fair-use/settings", json={"free_lifetime_enabled": False}, headers=H(admin_tok))
        assert r.status_code == 200 and r.json()["free_lifetime_enabled"] is False
        try:
            r = requests.post(f"{API}/admin/fair-use/brake", json={"action": "pause"}, headers=H(admin_tok))
            assert r.json()["paused"] is True
            r = requests.post(f"{API}/lex/chat", json={"message": "TEST brake independence question"}, headers=H(u["token"]), timeout=60)
            assert r.status_code == 429 and "paused" in r.json()["detail"], r.text[:200]
        finally:
            requests.post(f"{API}/admin/fair-use/brake", json={"action": "resume"}, headers=H(admin_tok))
            r = requests.put(f"{API}/admin/fair-use/settings", json={"free_lifetime_enabled": True}, headers=H(admin_tok))
            assert r.json()["free_lifetime_enabled"] is True
