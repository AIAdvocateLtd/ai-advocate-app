"""
Iteration 29 — Test new fixes:
1. POST /api/pdf/inline with signature_data_url > 200KB returns HTTP 413.
2. PATCH /api/auth/preferences accepts `jurisdiction` field (set + clear via null).
3. End-to-end: country switch GB→US can clear UK jurisdiction via /auth/preferences.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
TEST_EMAIL = "test@advocate.app"
TEST_PASSWORD = "Test12345!"

TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    if j.get("requires_2fa"):
        pytest.skip("test user has 2FA enabled")
    tok = j.get("access_token")
    assert tok
    return tok


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestSignatureSizeCap:
    def test_signature_250kb_returns_413(self, auth_headers):
        # 250 KB payload (well above the 200_000 char cap)
        big = "data:image/png;base64," + ("A" * 250000)
        payload = {
            "title": "Big Sig",
            "body": "Body",
            "filename": "big.pdf",
            "signature_data_url": big,
            "signer_name": "X",
            "signer_date": "2026-01-15",
        }
        r = requests.post(f"{BASE_URL}/api/pdf/inline", json=payload,
                          headers=auth_headers, timeout=30)
        assert r.status_code == 413, f"Expected 413, got {r.status_code}: {r.text[:200]}"
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        detail = (body.get("detail") or "").lower() if isinstance(body, dict) else str(body).lower()
        assert "large" in detail or "size" in detail or "150" in detail or "200" in detail, \
            f"413 detail not mentioning size: {detail}"

    def test_signature_at_tiny_size_still_ok(self, auth_headers):
        # Confirms regression — tiny signature still works
        r = requests.post(f"{BASE_URL}/api/pdf/inline", headers=auth_headers,
                          json={"title": "OK", "body": "Body", "filename": "ok.pdf",
                                "signature_data_url": TINY_PNG,
                                "signer_name": "Y", "signer_date": "2026-01-15"}, timeout=30)
        assert r.status_code == 200, f"tiny sig failed: {r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF"


class TestAuthPreferencesJurisdiction:
    def test_set_jurisdiction_via_preferences(self, auth_headers):
        # Set to scotland
        r = requests.patch(f"{BASE_URL}/api/auth/preferences",
                           json={"jurisdiction": "scotland"}, headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"PATCH set jurisdiction failed: {r.status_code} {r.text[:200]}"
        # Verify via /api/auth/me
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me.status_code == 200
        assert me.json().get("jurisdiction") == "scotland"

    def test_clear_jurisdiction_via_null(self, auth_headers):
        # Pre-condition: set to wales first
        r0 = requests.patch(f"{BASE_URL}/api/auth/preferences",
                            json={"jurisdiction": "wales"}, headers=auth_headers, timeout=15)
        assert r0.status_code == 200
        me0 = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me0.json().get("jurisdiction") == "wales"

        # Clear via null
        r = requests.patch(f"{BASE_URL}/api/auth/preferences",
                           json={"country": "US", "jurisdiction": None},
                           headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"PATCH clear failed: {r.status_code} {r.text[:200]}"
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me.status_code == 200
        j = me.json().get("jurisdiction")
        assert j is None, f"Expected jurisdiction=None, got {j!r}"

    def test_restore_to_gb_england(self, auth_headers):
        # Reset for next runs
        r = requests.patch(f"{BASE_URL}/api/auth/preferences",
                           json={"country": "GB", "jurisdiction": "england"},
                           headers=auth_headers, timeout=15)
        assert r.status_code == 200
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me.json().get("jurisdiction") == "england"
        assert me.json().get("country") == "GB"
