"""
Backend regression tests for the admin "case-insensitive email lookup" bug fix.

Bug context:
  Signup stores email as-typed (e.g. 'KLKL@hotmail.com'). The admin
  delete/comp/revoke/restore/purge endpoints previously did an exact
  case-sensitive match on the lowercased email, so they returned 404 for
  any user who signed up with mixed-case email.

Fix:
  /api/admin/users/{delete,comp,uncomp(revoke),restore,purge} all use
  a case-insensitive regex on the email field.

These tests verify:
  1. Admin can delete a mixed-case user via either casing.
  2. Comp / Revoke / Restore / Purge are also case-insensitive.
  3. Protected-account guard still blocks delete of admin@aiadvocate.co.uk.
  4. Non-existent users still return 404 (regex doesn't over-match).
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASSWORD = "AdminLex2026!"


def _unique_mixed_case_email() -> str:
    """Generate a unique mixed-case test email so re-runs don't collide."""
    token = uuid.uuid4().hex[:8]
    return f"MixedCaseTest_{token}@Example.com"  # note capitals preserved


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    token = r.json().get("access_token") or r.json().get("token")
    assert token, f"No access token in admin login response: {r.json()}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _create_mixed_case_user() -> str:
    """Create a user via /api/auth/signup with a mixed-case email.
    Returns the original (mixed-case) email actually stored in the DB."""
    email = _unique_mixed_case_email()
    payload = {
        "email": email,
        "password": "Test12345!",
        "full_name": "Mixed Case Test User",
        "language": "en",
        "country": "GB",
        "jurisdiction": "england",
        "device_id": f"test-device-{uuid.uuid4().hex[:8]}",
        "terms_accepted": True,
    }
    r = requests.post(f"{BASE_URL}/api/auth/signup", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Signup failed: {r.status_code} {r.text}"
    return email


# ── Tests ────────────────────────────────────────────────────────────────────

class TestAdminCaseInsensitiveEmail:

    def test_delete_with_lowercase_email_succeeds(self, admin_headers):
        """Core bug repro: user stored as 'MixedCaseTest_xxx@Example.com',
        delete request sends lowercase — must return 200."""
        mixed_email = _create_mixed_case_user()
        r = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email.lower(), "reason": "test"},
            timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("deleted") is True
        # cleanup: purge so list stays clean
        requests.post(
            f"{BASE_URL}/api/admin/users/purge",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )

    def test_delete_with_mixedcase_email_succeeds(self, admin_headers):
        mixed_email = _create_mixed_case_user()
        r = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email, "reason": "test"},
            timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("deleted") is True
        requests.post(
            f"{BASE_URL}/api/admin/users/purge",
            headers=admin_headers,
            json={"email": mixed_email}, timeout=30,
        )

    def test_comp_case_insensitive(self, admin_headers):
        mixed_email = _create_mixed_case_user()
        r = requests.post(
            f"{BASE_URL}/api/admin/users/comp",
            headers=admin_headers,
            json={"email": mixed_email.lower(), "days": 30, "reason": "test comp"},
            timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        # If pending=true, then the lookup didn't find the user → bug not fixed for comp.
        assert body.get("pending") is not True, \
            f"comp endpoint did NOT find mixed-case user — created pending grant instead: {body}"
        assert body.get("comp_pro_until"), f"comp_pro_until missing: {body}"
        # cleanup
        requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        requests.post(
            f"{BASE_URL}/api/admin/users/purge",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )

    def test_revoke_case_insensitive(self, admin_headers):
        """admin_users_uncomp (the 'revoke' endpoint) — must find mixed-case user via lowercase."""
        mixed_email = _create_mixed_case_user()
        # First comp them so revoke has something to act on
        requests.post(
            f"{BASE_URL}/api/admin/users/comp",
            headers=admin_headers,
            json={"email": mixed_email.lower(), "days": 30},
            timeout=30,
        )
        r = requests.post(
            f"{BASE_URL}/api/admin/users/uncomp",
            headers=admin_headers,
            json={"email": mixed_email.lower(), "keep": True, "reason": "test revoke"},
            timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("revoked") is True
        # cleanup
        requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        requests.post(
            f"{BASE_URL}/api/admin/users/purge",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )

    def test_restore_case_insensitive(self, admin_headers):
        mixed_email = _create_mixed_case_user()
        # Soft-delete first
        d = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        assert d.status_code == 200, f"Pre-step delete failed: {d.status_code} {d.text}"
        # Restore using lowercase
        r = requests.post(
            f"{BASE_URL}/api/admin/users/restore",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("restored") is True
        # cleanup
        requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        requests.post(
            f"{BASE_URL}/api/admin/users/purge",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )

    def test_purge_case_insensitive_and_removed_from_recent(self, admin_headers):
        mixed_email = _create_mixed_case_user()
        # Soft delete
        d = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        assert d.status_code == 200
        # Purge with lowercase
        r = requests.post(
            f"{BASE_URL}/api/admin/users/purge",
            headers=admin_headers,
            json={"email": mixed_email.lower()}, timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        # Verify gone from /admin/users/recent (paginate generously)
        rec = requests.get(
            f"{BASE_URL}/api/admin/users/recent?limit=500&include_test=true",
            headers=admin_headers, timeout=30,
        )
        assert rec.status_code == 200
        emails = [u.get("email", "").lower() for u in rec.json().get("users", [])]
        assert mixed_email.lower() not in emails, \
            f"Purged user still appears in recent users list"

    def test_protected_account_guard_still_works(self, admin_headers):
        """Case-insensitive regex must NOT weaken protected-account guard."""
        r = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": "admin@aiadvocate.co.uk"}, timeout=30,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "protected" in r.text.lower()

    def test_protected_account_guard_against_mixed_case_input(self, admin_headers):
        """Even with mixed-case input, the protected-account guard should fire
        because the endpoint lowercases before comparing."""
        r = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": "Admin@AiAdvocate.co.uk"}, timeout=30,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"

    def test_nonexistent_user_returns_404(self, admin_headers):
        """Regex must not over-match — totally bogus emails should still 404."""
        bogus = f"doesnotexist_{uuid.uuid4().hex}@nowhere.test"
        r = requests.post(
            f"{BASE_URL}/api/admin/users/delete",
            headers=admin_headers,
            json={"email": bogus}, timeout=30,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        assert "not found" in r.text.lower()
