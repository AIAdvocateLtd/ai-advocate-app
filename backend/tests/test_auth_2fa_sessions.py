"""Two-step sign-in (email + authenticator), session revocation, admin rules, Google hotfix. Synthetic users only.
Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_auth_2fa_sessions.py -q"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import pyotp
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import account_security as acct  # noqa: E402

LOOP = asyncio.new_event_loop()
run = LOOP.run_until_complete
PW = "Synthetic-Pass-123!"
SENT = []


async def _capture(email, code):
    SENT.append((email, code))


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://testserver")


async def call(method, path, token=None, **kw):
    async with client() as c:
        h = {"Authorization": f"Bearer {token}"} if token else {}
        return await c.request(method, "/api" + path, headers=h, **kw)


def make_user(**extra):
    uid = str(uuid.uuid4())
    email = f"synthetic-2fa-{uid[:8]}@synthetic-test.co.uk"
    run(server.db.users.insert_one({"id": uid, "email": email, "password_hash": server.hash_pw(PW), "full_name": "Synthetic",
                                    "email_verified": True, "subscription_status": "free", "created_at": "2026-11-19", **extra}))
    return {"id": uid, "email": email}


def login(u, password=PW):
    return run(call("POST", "/auth/login", json={"email": u["email"], "password": password}))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    asyncio.set_event_loop(LOOP)
    monkeypatch.setattr(server, "_send_login_code", _capture)
    SENT.clear()
    yield
    run(server.db.users.delete_many({"email": {"$regex": "^synthetic-2fa-"}}))
    run(server.db.auth_codes.delete_many({"_id": {"$regex": ":(login|reauth)$"}, "user_id": {"$exists": True},
                                          "sends": {"$exists": True}}))


def test_google_email_only_signin_rejected_and_apple_hidden():
    u = make_user()
    r = run(call("POST", "/auth/google", json={"email": u["email"], "google_id": "attacker"}))
    assert r.status_code == 400 and "access_token" not in r.text
    assert run(call("GET", "/auth/providers")).json()["apple_enabled"] is False


def test_sign_out_other_devices_and_all():
    u = make_user()
    t1 = login(u).json()["access_token"]
    t2 = login(u).json()["access_token"]
    r = run(call("POST", "/auth/sessions/revoke", t1, json={"keep_current": True}))
    t3 = r.json()["access_token"]
    assert run(call("GET", "/auth/me", t2)).status_code == 401
    assert run(call("GET", "/auth/me", t1)).status_code == 401
    assert run(call("GET", "/auth/me", t3)).status_code == 200
    run(call("POST", "/auth/sessions/revoke", t3, json={"keep_current": False}))
    assert run(call("GET", "/auth/me", t3)).status_code == 401
    assert login(u).status_code == 200


def test_tokens_without_version_still_valid():
    u = make_user()
    old = server.jwt.encode({"sub": u["id"], "email": u["email"], "exp": datetime.now(timezone.utc) + timedelta(days=1)},
                            server.JWT_SECRET, algorithm="HS256")
    assert run(call("GET", "/auth/me", old)).status_code == 200


def test_password_reset_revokes_existing_sessions():
    u = make_user()
    t = login(u).json()["access_token"]
    tok = uuid.uuid4().hex
    run(server.db.password_reset_tokens.insert_one({"token": tok, "account_kind": "user", "account_id": u["id"], "used_at": None,
                                                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}))
    r = run(call("POST", "/auth/reset-password", json={"token": tok, "new_password": "Another-Pass-456!"}))
    assert r.status_code == 200
    assert run(call("GET", "/auth/me", t)).status_code == 401
    assert run(call("GET", "/auth/me", r.json()["access_token"])).status_code == 200
    run(server.db.password_reset_tokens.delete_many({"token": tok}))


def test_email_codes_flow():
    u = make_user()
    t = login(u).json()["access_token"]
    assert run(call("POST", "/auth/2fa/email/enable", t, json={"password": "wrong"})).status_code == 400
    r = run(call("POST", "/auth/2fa/email/enable", t, json={"password": PW}))
    assert r.status_code == 200 and run(call("GET", "/auth/me", t)).status_code == 401
    ch = login(u).json()
    assert ch["requires_2fa"] and ch["method"] == "email" and ch["code_sent"] and "access_token" not in ch
    assert "***" in ch["email"]
    code = SENT[-1][1]
    assert run(call("GET", "/auth/me", ch["tmp_token"])).status_code == 401  # pre-2FA token is not a session
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": "000000" if code != "000000" else "111111"})).status_code == 401
    ok = run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": code}))
    assert ok.status_code == 200 and run(call("GET", "/auth/me", ok.json()["access_token"])).status_code == 200
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": code})).status_code == 401  # single use


def test_email_code_replaced_on_resend_expires_and_throttled():
    u = make_user(email_2fa_enabled=True)
    ch = login(u).json()
    first = SENT[-1][1]
    assert run(call("POST", "/auth/2fa/email/resend", json={"tmp_token": ch["tmp_token"]})).status_code == 429
    run(server.db.auth_codes.update_one({"_id": f"{u['id']}:login"}, {"$set": {"sends": [datetime.now(timezone.utc) - timedelta(minutes=2)]}}))
    assert run(call("POST", "/auth/2fa/email/resend", json={"tmp_token": ch["tmp_token"]})).status_code == 200
    second = SENT[-1][1]
    if first != second:
        assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": first})).status_code == 401
    run(server.db.auth_codes.update_one({"_id": f"{u['id']}:login"}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}}))
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": second})).status_code == 401


def test_wrong_code_attempts_capped_per_account():
    u = make_user(email_2fa_enabled=True)
    codes = []
    for _ in range(11):
        ch = login(u).json()
        codes.append(run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": "999999x"})).status_code)
        run(server.db.auth_codes.delete_many({"_id": f"{u['id']}:login"}))
    assert 429 in codes
    run(server.db.login_attempts.delete_many({"scope": "mfa_acct", "key": u["id"]}))


def test_authenticator_flow_encrypted_replay_and_recovery():
    u = make_user()
    t = login(u).json()["access_token"]
    assert run(call("POST", "/auth/2fa/setup", t, json={})).status_code == 400
    setup = run(call("POST", "/auth/2fa/setup", t, json={"password": PW})).json()
    secret = setup["secret"]
    doc = run(server.db.users.find_one({"id": u["id"]}))
    assert doc["totp_secret_pending"].startswith("enc:") and secret not in doc["totp_secret_pending"]
    v = run(call("POST", "/auth/2fa/verify", t, json={"code": pyotp.TOTP(secret).now()})).json()
    assert v["enabled"] and len(v["backup_codes"]) == 10
    assert run(server.db.users.find_one({"id": u["id"]}))["totp_secret"].startswith("enc:")
    ch = login(u).json()
    assert ch["method"] == "totp" and not SENT
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": pyotp.TOTP(secret).now()})).status_code == 401  # setup code reused
    run(server.db.users.update_one({"id": u["id"]}, {"$set": {"totp_last_step": 0}}))
    code = pyotp.TOTP(secret).now()
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch["tmp_token"], "code": code})).status_code == 200
    ch2 = login(u).json()
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch2["tmp_token"], "code": code})).status_code == 401  # replay
    rc = v["backup_codes"][0]
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch2["tmp_token"], "code": rc})).status_code == 200
    ch3 = login(u).json()
    assert run(call("POST", "/auth/2fa/login", json={"tmp_token": ch3["tmp_token"], "code": rc})).status_code == 401  # used once
    st = run(call("GET", "/auth/security/status", v["access_token"])).json()
    assert st["method"] == "totp" and st["recovery_codes_left"] == 9
    assert run(call("POST", "/auth/2fa/email/enable", v["access_token"], json={"password": PW})).status_code == 400
    run(server.db.login_attempts.delete_many({"scope": "mfa_acct", "key": u["id"]}))


def test_social_login_and_admin_rules():
    u = make_user(totp_enabled=True, totp_secret=acct.enc_secret(pyotp.random_base32()))
    user = run(server.db.users.find_one({"id": u["id"]}, {"_id": 0}))
    resp = run(server._social_login_response(user))
    assert b'"requires_2fa":true' in resp.body and b"access_token" not in resp.body
    admin_like = {"email": "x@synthetic-test.co.uk", "is_owner": True, "email_2fa_enabled": True}
    assert acct.mfa_method(admin_like) is None  # email codes never satisfy an admin
    assert acct.mfa_method({**admin_like, "totp_enabled": True}) == "totp"


def test_admin_enforcement_gate_and_lockout_guard():
    from fastapi import HTTPException
    prev = run(server.db.app_settings.find_one({"_id": "security"}))
    try:
        run(server.db.app_settings.update_one({"_id": "security"}, {"$set": {"admin_totp_required": True}}, upsert=True))
        with pytest.raises(HTTPException) as e:
            run(server._admin_mfa_gate({"id": "a", "email": "admin@aiadvocate.co.uk"}))
        assert e.value.status_code == 403
        run(server._admin_mfa_gate({"id": "a", "email": "admin@aiadvocate.co.uk", "totp_enabled": True}))
    finally:
        if prev:
            run(server.db.app_settings.replace_one({"_id": "security"}, prev))
        else:
            run(server.db.app_settings.delete_one({"_id": "security"}))
    adm = run(server.db.users.find_one({"email": "admin@aiadvocate.co.uk"}, {"_id": 0, "id": 1, "email": 1, "token_version": 1}))
    if adm:
        tok = server.make_token(adm["id"], adm["email"], adm.get("token_version") or 0)
        r = run(call("POST", "/admin/security/admin-totp-required", tok, json={"enabled": True, "code": "123456"}))
        assert r.status_code == 400  # cannot switch on without own authenticator


def test_engagement_rejects_pre_2fa_token():
    u = make_user(email_2fa_enabled=True)
    ch = login(u).json()
    r = run(call("PATCH", "/engagements/nonexistent/close", ch["tmp_token"]))
    assert r.status_code == 401
