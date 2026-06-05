"""Iteration 25 backend tests:
- POST /api/privacy/delete-analytics-data (auth-required, audit + flag persistence)
- GET  /api/admin/stripe-price-audit (admin-only, 11 env vars audited)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to reading from frontend env file if not already in env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

USER_EMAIL  = "test@advocate.app"
USER_PASS   = "Test12345!"
ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASS  = "AdminLex2026!"

EXPECTED_ENV_VARS = [
    "STRIPE_PRICE_PLUS",
    "STRIPE_PRICE_PRO",
    "STRIPE_PRICE_YEARLY_PRO",
    "STRIPE_PRICE_FIRM_FEATURED",
    "STRIPE_PRICE_FIRM_PREMIUM",
    "STRIPE_PRICE_FIRM_PRACTICE",
    "STRIPE_PRICE_TOPUP_DAY_PASS",
    "STRIPE_PRICE_TOPUP_LETTER_PACK",
    "STRIPE_PRICE_TOPUP_WEEKEND_PASS",
    "STRIPE_PRICE_TOPUP_CRISIS_PACK",
    "STRIPE_PRICE_SANITY_CHECK",
]


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _login(s, email, password):
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def user_token(s):
    return _login(s, USER_EMAIL, USER_PASS)


@pytest.fixture(scope="module")
def admin_token(s):
    return _login(s, ADMIN_EMAIL, ADMIN_PASS)


# ============ Privacy: delete-analytics-data ============

class TestPrivacyDeleteAnalytics:
    def test_unauth_rejected(self, s):
        r = s.post(f"{BASE_URL}/api/privacy/delete-analytics-data", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403 without token, got {r.status_code}"

    def test_authed_returns_expected_shape(self, s, user_token):
        r = s.post(
            f"{BASE_URL}/api/privacy/delete-analytics-data",
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=30,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text}"
        body = r.json()
        # shape
        assert "posthog" in body and isinstance(body["posthog"], dict)
        assert "sentry"  in body and isinstance(body["sentry"], dict)
        assert "requested_at" in body and isinstance(body["requested_at"], str)
        # posthog inner shape (skipped is expected because POSTHOG_PERSONAL_API_KEY isn't set)
        ph = body["posthog"]
        assert "attempted" in ph
        assert "status"    in ph
        # sentry inner shape
        sn = body["sentry"]
        assert sn.get("status") == "logged"

    def test_idempotent_second_call(self, s, user_token):
        # calling again should still 200
        r = s.post(
            f"{BASE_URL}/api/privacy/delete-analytics-data",
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=30,
        )
        assert r.status_code == 200


# ============ Admin: stripe-price-audit ============

class TestStripePriceAudit:
    def test_unauth_rejected(self, s):
        r = s.get(f"{BASE_URL}/api/admin/stripe-price-audit", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_non_admin_rejected(self, s, user_token):
        r = s.get(
            f"{BASE_URL}/api/admin/stripe-price-audit",
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=20,
        )
        assert r.status_code == 403, f"expected 403 for non-admin, got {r.status_code} {r.text}"

    def test_admin_returns_full_audit(self, s, admin_token):
        r = s.get(
            f"{BASE_URL}/api/admin/stripe-price-audit",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        assert r.status_code == 200, f"admin audit failed: {r.status_code} {r.text}"
        body = r.json()
        assert "rows" in body and isinstance(body["rows"], list)
        assert "summary" in body and isinstance(body["summary"], dict)

        rows = body["rows"]
        assert len(rows) == 11, f"expected 11 rows got {len(rows)}: {[r.get('env_var') for r in rows]}"

        got_envs = [r.get("env_var") for r in rows]
        for ev in EXPECTED_ENV_VARS:
            assert ev in got_envs, f"missing expected env var {ev} from audit"

        summary = body["summary"]
        # Per request: ok:11, mismatch:0, missing:0, error:0
        assert summary.get("ok") == 11, f"expected ok=11, got summary={summary}"
        assert summary.get("mismatch") == 0, f"expected mismatch=0, got summary={summary}"
        assert summary.get("missing") == 0, f"expected missing=0, got summary={summary}"
        assert summary.get("error") == 0, f"expected error=0, got summary={summary}"

        # spot-check structure of one row
        sample = rows[0]
        for k in ("env_var", "expected_label", "expected_gbp", "expected_interval", "price_id", "status"):
            assert k in sample, f"row missing key {k}: {sample}"
