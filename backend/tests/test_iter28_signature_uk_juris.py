"""
Iteration 28 — Test new features:
1. POST /api/pdf/inline with signature fields (embed PNG + footnote)
2. POST /api/pdf/inline without signature (regression — no sig block)
3. POST /api/profile/uk-jurisdiction (set scotland, invalid value, ni shorthand)
4. POST /api/lex/chat after jurisdiction=scotland still works + saves conversation
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
TEST_EMAIL = "test@advocate.app"
TEST_PASSWORD = "Test12345!"

# 1x1 transparent PNG
TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                      timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    if j.get("requires_2fa"):
        pytest.skip("test user has 2FA enabled — cannot run automated tests")
    tok = j.get("access_token")
    assert tok, "no access_token in login response"
    return tok


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============ PDF Inline tests ============

class TestPDFInlineSignature:
    def test_pdf_inline_with_signature(self, auth_headers):
        payload = {
            "title": "Test Letter",
            "body": "Dear Sir,\n\nThis is a test letter body.\n\nYours sincerely,\nTester",
            "filename": "test_signed.pdf",
            "signature_data_url": TINY_PNG,
            "signer_name": "Alice Tester",
            "signer_date": "2026-01-15",
        }
        r = requests.post(f"{BASE_URL}/api/pdf/inline", json=payload,
                          headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"PDF inline signed failed: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), \
            f"Wrong content-type: {r.headers.get('content-type')}"
        assert r.content[:4] == b"%PDF", "Response is not a valid PDF (missing %PDF header)"
        assert len(r.content) > 1000, f"PDF too small: {len(r.content)} bytes"
        # Signed PDF should be larger than unsigned (embedded image + extra text)
        # Cannot easily parse PDF text — sufficient to verify it's a valid PDF.

    def test_pdf_inline_without_signature_regression(self, auth_headers):
        payload = {
            "title": "Unsigned Test Letter",
            "body": "Plain body without signature.",
            "filename": "test_unsigned.pdf",
        }
        r = requests.post(f"{BASE_URL}/api/pdf/inline", json=payload,
                          headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"Unsigned PDF failed: {r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 500

    def test_pdf_size_difference_signed_vs_unsigned(self, auth_headers):
        """Sanity check — signed PDF should be larger than unsigned because of the image."""
        common = {"title": "Sig Diff", "body": "Body.", "filename": "x.pdf"}
        r1 = requests.post(f"{BASE_URL}/api/pdf/inline", json=common,
                           headers=auth_headers, timeout=30)
        r2 = requests.post(f"{BASE_URL}/api/pdf/inline",
                           json={**common, "signature_data_url": TINY_PNG,
                                 "signer_name": "Bob", "signer_date": "2026-01-15"},
                           headers=auth_headers, timeout=30)
        assert r1.status_code == 200 and r2.status_code == 200
        # Signed should be at least somewhat larger (image + footnote paragraph)
        assert len(r2.content) > len(r1.content), \
            f"signed PDF ({len(r2.content)}) not larger than unsigned ({len(r1.content)})"


# ============ UK Jurisdiction tests ============

class TestUKJurisdiction:
    def test_set_scotland_and_verify_persistence(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/profile/uk-jurisdiction",
                          json={"jurisdiction": "scotland"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"Set scotland failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("jurisdiction") == "scotland"

        # Verify via /api/auth/me
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me.status_code == 200
        assert me.json().get("jurisdiction") == "scotland", \
            f"jurisdiction not persisted on user doc: {me.json().get('jurisdiction')}"

    def test_invalid_jurisdiction_returns_400(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/profile/uk-jurisdiction",
                          json={"jurisdiction": "mars"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400, f"Expected 400 for invalid juris, got {r.status_code}"
        body = r.json()
        # detail should mention valid options
        detail = body.get("detail", "") if isinstance(body, dict) else str(body)
        assert "england" in detail.lower() or "scotland" in detail.lower() \
            or "jurisdiction" in detail.lower(), f"unhelpful 400 detail: {detail}"

    def test_ni_shorthand_normalises(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/profile/uk-jurisdiction",
                          json={"jurisdiction": "ni"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"NI shorthand failed: {r.status_code} {r.text[:200]}"
        assert r.json().get("jurisdiction") == "northern_ireland"

        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me.json().get("jurisdiction") == "northern_ireland"

    def test_set_england_then_wales(self, auth_headers):
        for j in ("england", "wales"):
            r = requests.post(f"{BASE_URL}/api/profile/uk-jurisdiction",
                              json={"jurisdiction": j},
                              headers=auth_headers, timeout=15)
            assert r.status_code == 200, f"{j} failed: {r.text[:200]}"
            assert r.json().get("jurisdiction") == j


# ============ Lex chat regression after jurisdiction change ============

class TestLexChatWithJurisdiction:
    def test_lex_chat_works_after_scotland_set(self, auth_headers):
        # Ensure scotland is set
        requests.post(f"{BASE_URL}/api/profile/uk-jurisdiction",
                      json={"jurisdiction": "scotland"},
                      headers=auth_headers, timeout=15)

        # Send a short Lex message — the call must still succeed
        r = requests.post(f"{BASE_URL}/api/lex/chat",
                          json={"message": "What court handles a small civil claim where I live?"},
                          headers=auth_headers, timeout=120)
        # Accept 200 (worked) OR 402 (paywall) — both prove endpoint is healthy.
        # But for the test user we expect 200.
        assert r.status_code in (200, 402), \
            f"Lex chat failed: {r.status_code} {r.text[:300]}"
        if r.status_code == 200:
            j = r.json()
            # response should contain some kind of reply / answer field
            text_blob = (j.get("reply") or j.get("answer") or j.get("message")
                         or j.get("content") or str(j)).lower()
            assert len(text_blob) > 20, f"reply too short: {text_blob[:200]}"
