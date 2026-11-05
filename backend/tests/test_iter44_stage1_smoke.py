# Iter44: Stage 1 repair smoke — auth, admin spend, endpoint health (NO paid AI calls)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
ADMIN = {"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


# Auth
def test_login_returns_user(admin):
    r = admin.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert r.status_code == 200
    assert r.json().get("email") == ADMIN["email"]


def test_login_bad_password():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN["email"], "password": "nope_wrong"}, timeout=20)
    assert r.status_code in (400, 401)


# Admin spend report
def test_llm_spend_2h(admin):
    r = admin.get(f"{BASE_URL}/api/admin/llm-spend?hours=2", timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d, dict)
    print("llm-spend keys:", list(d.keys()))


def test_llm_spend_requires_admin():
    r = requests.get(f"{BASE_URL}/api/admin/llm-spend?hours=2", timeout=20)
    assert r.status_code in (401, 403)


# Paid endpoints must validate empty payloads without 500 (no AI cost)
@pytest.mark.parametrize("path", ["/api/letters/generate", "/api/legal-letter",
                                  "/api/lex/chat", "/api/lex/chat/stream"])
def test_paid_endpoints_empty_payload_no_500(admin, path):
    r = admin.post(f"{BASE_URL}{path}", json={}, timeout=30)
    print(path, r.status_code, r.text[:150])
    assert r.status_code < 500


def test_document_analyze_no_file_no_500(admin):
    r = admin.post(f"{BASE_URL}/api/document/analyze", data={"language": "en-GB"}, timeout=30)
    print("doc", r.status_code, r.text[:150])
    assert r.status_code < 500
