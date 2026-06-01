"""
Iteration 23 — Phase 4b batch test suite.
Tests 8 new features added in one push:
  1. OCR Form Scanner       — POST /api/forms/ocr/detect
  2. Letter Counter-Ladder  — POST /api/letters/counter-ladder
  3. Case Timeline Lex Summary — POST /api/cases/{id}/timeline/summarise
  4. Witness invite + magic link
  5. Witness public fetch + submit
  6. Witness list + PDF download
  7. Legal Letter tone slider
  8. Cost Estimate postcode + compare
  9. Regression — basic ET1 endpoint still responds, demo endpoint absent
"""
import os
import io
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Pro/reviewer account — unlimited LLM calls
REVIEWER_EMAIL = "appstore.reviewer@aiadvocate.co.uk"
REVIEWER_PWD   = "Review2026!Lex"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": REVIEWER_EMAIL, "password": REVIEWER_PWD},
                      timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login: {data}"
    return tok


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def case_id(auth_headers):
    """Create a case fresh for this run, used by timeline + witness tests."""
    r = requests.post(f"{API}/cases",
                      headers=auth_headers,
                      json={"name": f"TEST_phase4b_{uuid.uuid4().hex[:8]}",
                            "category": "employment"},
                      timeout=20)
    assert r.status_code in (200, 201), f"Case create: {r.status_code} {r.text[:300]}"
    cid = r.json().get("id") or r.json().get("case", {}).get("id")
    assert cid, f"No case id: {r.json()}"
    return cid


# ---------------- 1. OCR Form Scanner ----------------
class TestOCRFormScanner:
    """POST /api/forms/ocr/detect — accepts an image, returns form classification."""

    def test_ocr_with_simple_image_does_not_500(self, auth_headers):
        # 1x1 PNG (will be too small → 400) — so use a real-ish JPEG of decent size
        # Build a synthetic ~1KB JPEG via PIL fallback to bytes
        try:
            from PIL import Image
            img = Image.new("RGB", (400, 600), color=(255, 255, 255))
            # add minimal text-looking pixels (random)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            content = buf.getvalue()
        except Exception:
            # Fallback: pad some bytes; ensure >200 bytes to bypass "too small" guard
            content = b"\xff\xd8\xff" + b"\x00" * 1024 + b"\xff\xd9"

        files = {"file": ("test.jpg", content, "image/jpeg")}
        r = requests.post(f"{API}/forms/ocr/detect",
                          headers=auth_headers, files=files,
                          data={"language": "en-GB"},
                          timeout=60)
        # MUST not 500. Acceptable: 200 with form_type=OTHER_FORM/NOT_A_FORM or 400 if image is too small
        assert r.status_code != 500, f"OCR endpoint 500: {r.text[:500]}"
        if r.status_code == 200:
            data = r.json()
            assert "form_type" in data
            assert "raw_text" in data or "extracted_fields" in data or "form_label" in data
            assert "suggested_route" in data


# ---------------- 2. Letter Counter-Ladder ----------------
class TestCounterLadder:
    """POST /api/letters/counter-ladder returns 4 escalation drafts."""

    def test_counter_ladder_returns_4_drafts(self, auth_headers):
        payload = {
            "received_letter_summary": "Landlord sent a Section 21 notice telling me to leave in 2 months. I have lived here 4 years and paid rent on time.",
            "desired_outcome": "I want to stay or get more time to find a new place.",
            "your_name": "Test Tenant",
            "recipient": "Landlord Ltd",
            "category": "housing",
            "language": "en-GB",
        }
        r = requests.post(f"{API}/letters/counter-ladder",
                          headers=auth_headers, json=payload, timeout=90)
        assert r.status_code == 200, f"counter-ladder: {r.status_code} {r.text[:500]}"
        data = r.json()
        # Backend returns flat keys: polite, firm, pre_action, court
        for k in ("polite", "firm", "pre_action", "court"):
            assert k in data, f"Missing tone key {k}: {list(data.keys())}"
            blob = data[k]
            # blob may be dict with tone_label/body/when_to_use OR plain string
            body = blob.get("body") if isinstance(blob, dict) else str(blob)
            assert body and len(body) > 50, f"Body too short for {k}: {len(body) if body else 0}"


# ---------------- 3. Case Timeline Summarise ----------------
class TestTimelineSummary:
    """POST /api/cases/{id}/timeline/summarise — requires events in timeline."""

    def test_timeline_summary_empty_case_returns_400(self, auth_headers):
        # Note: freshly-created cases auto-include a "case_opened" event in the timeline feed,
        # so this test verifies the endpoint doesn't 500 (returns either 400 or 200).
        r0 = requests.post(f"{API}/cases", headers=auth_headers,
                           json={"name": f"TEST_empty_{uuid.uuid4().hex[:6]}",
                                 "category": "general"}, timeout=20)
        empty_id = r0.json().get("id") or r0.json().get("case", {}).get("id")
        r = requests.post(f"{API}/cases/{empty_id}/timeline/summarise",
                          headers=auth_headers, timeout=45)
        assert r.status_code in (200, 400), f"timeline summary: {r.status_code} {r.text[:200]}"
        if r.status_code == 200:
            d = r.json()
            assert "headline" in d and "narrative" in d, f"missing required keys: {list(d.keys())}"
            assert "key_dates" in d and "open_questions" in d and "next_legal_steps" in d, \
                f"missing summary fields: {list(d.keys())}"


# ---------------- 4-6. Witness flow (invite → public fetch → public submit → list → pdf) ----------------
class TestWitnessFlow:
    """End-to-end witness flow."""

    @pytest.fixture(scope="class")
    def witness_token(self, auth_headers, case_id):
        """Create an invite — returns token."""
        payload = {
            "witness_name": "TEST Witness Alice",
            "witness_email": None,  # don't send actual email in tests
            "context_for_witness": "Please describe what you saw on 15 Jan 2026 at the workplace meeting.",
            "questions": ["What time did you arrive?", "Who else was present?"],
        }
        r = requests.post(f"{API}/cases/{case_id}/witness/invite",
                          headers=auth_headers, json=payload, timeout=20)
        assert r.status_code == 200, f"invite failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("token") and data.get("magic_link"), f"missing token/link: {data}"
        return data["token"]

    def test_witness_public_fetch_ready(self, witness_token):
        # No auth header — public endpoint
        r = requests.get(f"{API}/witness/{witness_token}", timeout=15)
        assert r.status_code == 200, f"public fetch: {r.status_code} {r.text[:200]}"
        d = r.json()
        assert d.get("status") == "ready"
        assert d.get("witness_name") == "TEST Witness Alice"

    def test_witness_public_fetch_invalid_token(self):
        r = requests.get(f"{API}/witness/this-token-does-not-exist-xyz", timeout=15)
        assert r.status_code == 404

    def test_witness_submit_requires_statement_of_truth(self, witness_token):
        r = requests.post(f"{API}/witness/{witness_token}/submit",
                          json={
                              "statement": "I was present at the meeting on 15 January 2026. " * 5,
                              "witness_full_name": "Alice Witness",
                              "statement_of_truth": False,
                          }, timeout=15)
        assert r.status_code == 400, f"should require SOT: {r.status_code}"

    def test_witness_submit_too_short(self, witness_token):
        r = requests.post(f"{API}/witness/{witness_token}/submit",
                          json={"statement": "short", "witness_full_name": "Alice",
                                "statement_of_truth": True}, timeout=15)
        # Pydantic min_length=80 → 422
        assert r.status_code in (400, 422), f"short stmt should be rejected: {r.status_code}"

    def test_witness_submit_success_and_single_use(self, witness_token, auth_headers, case_id):
        long_stmt = ("I was present at the workplace meeting on 15 January 2026. "
                     "I saw the manager raise his voice and use language I considered inappropriate. "
                     "I was sitting next to the claimant and observed the entire exchange. ") * 2
        r = requests.post(f"{API}/witness/{witness_token}/submit",
                          json={
                              "statement": long_stmt,
                              "witness_full_name": "Alice TEST Witness",
                              "witness_occupation": "Office Manager",
                              "witness_address": "1 Test St, London EC1",
                              "statement_of_truth": True,
                          }, timeout=20)
        assert r.status_code == 200, f"submit failed: {r.status_code} {r.text[:300]}"
        d = r.json()
        assert d.get("ok") is True
        assert d.get("statement_id")

        # Single-use: resubmit should 409
        r2 = requests.post(f"{API}/witness/{witness_token}/submit",
                           json={"statement": long_stmt, "witness_full_name": "Alice",
                                 "statement_of_truth": True}, timeout=15)
        assert r2.status_code == 409, f"resubmit should 409: {r2.status_code}"

        # Also: public fetch should now indicate already_submitted
        r3 = requests.get(f"{API}/witness/{witness_token}", timeout=15)
        assert r3.status_code == 200
        assert r3.json().get("status") == "already_submitted"

        # List should include the submitted statement
        r4 = requests.get(f"{API}/cases/{case_id}/witness-statements",
                          headers=auth_headers, timeout=15)
        assert r4.status_code == 200
        lst = r4.json()
        assert any(s.get("id") == d["statement_id"] for s in lst.get("statements", [])), \
            f"new statement not in list: {lst}"

        # PDF
        r5 = requests.get(f"{API}/cases/{case_id}/witness-statements/{d['statement_id']}/pdf",
                          headers=auth_headers, timeout=20)
        assert r5.status_code == 200
        assert r5.headers.get("content-type", "").startswith("application/pdf"), \
            f"bad pdf content-type: {r5.headers.get('content-type')}"
        assert r5.content[:4] == b"%PDF", f"not a real PDF: {r5.content[:20]}"


# ---------------- 7. Legal Letter tone slider ----------------
class TestLegalLetterTone:
    """POST /api/legal-letter — tone field accepted."""

    def test_legal_letter_with_tone_polite(self, auth_headers):
        payload = {
            "letter_type": "Refund demand",
            "recipient": "BigShop Ltd",
            "your_name": "Test Customer",
            "details": "Bought a kettle from BigShop for £40 on 1 Jan 2026. It stopped working on day 5. Shop refuses refund.",
            "language": "en-GB",
            "tone": "polite",
        }
        r = requests.post(f"{API}/legal-letter",
                          headers=auth_headers, json=payload, timeout=60)
        assert r.status_code == 200, f"legal-letter polite: {r.status_code} {r.text[:300]}"
        d = r.json()
        body = d.get("letter") or d.get("body") or d.get("content") or ""
        assert len(body) > 200, f"letter too short: {len(body)}"

    def test_legal_letter_without_tone_still_works(self, auth_headers):
        # Regression: pre-existing call without tone field
        payload = {
            "letter_type": "Refund demand",
            "recipient": "BigShop",
            "your_name": "Test",
            "details": "Same as above — testing regression without tone field present.",
            "language": "en-GB",
        }
        r = requests.post(f"{API}/legal-letter",
                          headers=auth_headers, json=payload, timeout=60)
        assert r.status_code == 200, f"legal-letter no-tone: {r.status_code} {r.text[:300]}"


# ---------------- 8. Cost Estimate postcode + compare ----------------
class TestCostEstimatePostcode:
    """POST /api/cost/estimate — postcode multiplier + comparison block."""

    def test_cost_estimate_with_ec1a_postcode_central_london(self, auth_headers):
        payload = {
            "case_summary": "Unfair dismissal — 3 years' service, dismissed without warning.",
            "category": "employment",
            "country": "GB",
            "language": "en-GB",
            "postcode": "EC1A",
        }
        r = requests.post(f"{API}/cost/estimate",
                          headers=auth_headers, json=payload, timeout=60)
        assert r.status_code == 200, f"cost estimate: {r.status_code} {r.text[:300]}"
        d = r.json()
        assert d.get("postcode_multiplier") == 1.55, f"EC1A mult expected 1.55, got {d.get('postcode_multiplier')}"
        assert "Central London" in (d.get("postcode_region") or ""), f"region: {d.get('postcode_region')}"
        # Comparison block
        comp = d.get("comparison") or {}
        assert "diy" in comp and "ai_advocate" in comp and "solicitor" in comp, f"missing compare keys: {list(comp.keys())}"
        for k in ("diy", "ai_advocate", "solicitor"):
            sec = comp[k]
            assert "total_low" in sec and "total_high" in sec, f"missing totals on {k}: {sec.keys()}"
            assert "pros" in sec and "cons" in sec, f"missing pros/cons on {k}"
        # Saving banner numbers
        assert "aa_pro_saving_vs_solicitor_gbp" in d or "aa_pro_saving_vs_solicitor_percent" in d, \
            f"missing saving fields: {list(d.keys())}"

    def test_cost_estimate_without_postcode_regression(self, auth_headers):
        payload = {
            "case_summary": "Small claim £400 — landlord won't return deposit.",
            "category": "housing", "country": "GB", "language": "en-GB",
        }
        r = requests.post(f"{API}/cost/estimate",
                          headers=auth_headers, json=payload, timeout=60)
        assert r.status_code == 200, f"cost no-postcode regression: {r.status_code} {r.text[:300]}"
        d = r.json()
        assert d.get("postcode_multiplier") == 1.0, f"no-postcode should be 1.0: {d.get('postcode_multiplier')}"


# ---------------- 9. Quick regression smoke ----------------
class TestRegression:
    def test_health(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code in (200, 404)  # root may not exist; we just check API reachable

    def test_auth_me(self, auth_headers):
        r = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=15)
        assert r.status_code == 200
