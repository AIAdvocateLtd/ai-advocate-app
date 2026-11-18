"""Public-URL API tests for /api/admin/law-updates (read + refused decisions only; never writes tracker data)."""
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}
USER = {"email": "test@advocate.app", "password": "Test12345!"}


def _token(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    d = r.json()
    return d.get("token") or d.get("access_token")


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_token(ADMIN)}"}


@pytest.fixture(scope="module")
def user_h():
    return {"Authorization": f"Bearer {_token(USER)}"}


# auth
def test_list_requires_auth():
    assert requests.get(f"{BASE_URL}/api/admin/law-updates", timeout=20).status_code in (401, 403)


def test_list_forbidden_for_non_admin(user_h):
    assert requests.get(f"{BASE_URL}/api/admin/law-updates", headers=user_h, timeout=20).status_code == 403


def test_decision_requires_auth():
    r = requests.post(f"{BASE_URL}/api/admin/law-updates/x/decision", json={"decision": "reject"}, timeout=20)
    assert r.status_code in (401, 403)


# admin list
def test_list_returns_array(admin_h):
    r = requests.get(f"{BASE_URL}/api/admin/law-updates", headers=admin_h, timeout=20)
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_list_status_filter(admin_h):
    r = requests.get(f"{BASE_URL}/api/admin/law-updates?status=awaiting_review", headers=admin_h, timeout=20)
    assert r.status_code == 200 and all(p["status"] == "awaiting_review" for p in r.json())


# decisions refused
def test_unknown_id_400(admin_h):
    r = requests.post(f"{BASE_URL}/api/admin/law-updates/TEST-NOPE/decision", headers=admin_h,
                      json={"decision": "approve", "reviewer_name": "J", "regulator": "SRA", "registration_number": "1"}, timeout=20)
    assert r.status_code == 400 and r.json()["detail"] == "No such update."


def test_unknown_decision_400(admin_h):
    r = requests.post(f"{BASE_URL}/api/admin/law-updates/TEST-NOPE/decision", headers=admin_h, json={"decision": "zap"}, timeout=20)
    assert r.status_code == 400 and r.json()["detail"] == "Unknown decision."


def test_missing_decision_422(admin_h):
    r = requests.post(f"{BASE_URL}/api/admin/law-updates/TEST-NOPE/decision", headers=admin_h, json={}, timeout=20)
    assert r.status_code == 422


def test_writes_still_off(admin_h):
    r = requests.get(f"{BASE_URL}/api/admin/law-watch/status", headers=admin_h, timeout=20)
    assert r.status_code == 200 and r.json()["enabled"] is False
