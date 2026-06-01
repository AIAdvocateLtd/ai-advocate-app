"""ET1 Employment Tribunal Auto-Fill — backend integration tests (Phase 4a)."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

PRIMARY_EMAIL = "test@advocate.app"
PRIMARY_PASSWORD = "Test12345!"

SECOND_EMAIL = "appstore.reviewer@aiadvocate.co.uk"
SECOND_PASSWORD = "Review2026!Lex"

NARRATIVE = (
    "I was dismissed on 15 March 2026 after returning from 9 months maternity leave. "
    "My role went to a male colleague who joined 3 months before my leave started. "
    "I was told there was a redundancy but my exact role still exists. I have not used ACAS yet."
)


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def token_primary() -> str:
    return _login(PRIMARY_EMAIL, PRIMARY_PASSWORD)


@pytest.fixture(scope="module")
def token_second() -> str:
    return _login(SECOND_EMAIL, SECOND_PASSWORD)


@pytest.fixture(scope="module")
def headers_primary(token_primary):
    return {"Authorization": f"Bearer {token_primary}"}


@pytest.fixture(scope="module")
def headers_second(token_second):
    return {"Authorization": f"Bearer {token_second}"}


@pytest.fixture(scope="module")
def et1_draft(headers_primary):
    """Generate one ET1 draft and reuse it across tests (LLM call is expensive)."""
    payload = {
        "full_name": "TEST_Jane Doe",
        "postcode": "SW1A 1AA",
        "email": "TEST_jane@example.com",
        "employer_name": "Acme Ltd",
        "job_title": "Senior Analyst",
        "employment_start_date": "01/02/2020",
        "employment_end_date": "15/03/2026",
        "extra_context": NARRATIVE,
        "language": "en-GB",
    }
    last_err = None
    for attempt in range(2):
        r = requests.post(f"{API}/forms/et1/draft", json=payload, headers=headers_primary, timeout=120)
        if r.status_code == 200:
            return r.json()
        last_err = (r.status_code, r.text[:500])
        time.sleep(2)
    pytest.fail(f"ET1 draft creation failed after retries: {last_err}")


# ---------- TESTS ----------

class TestET1Draft:
    def test_draft_create_returns_structured_response(self, et1_draft):
        d = et1_draft
        assert "draft_id" in d and isinstance(d["draft_id"], str) and len(d["draft_id"]) > 8
        assert d.get("form") == "ET1"
        assert "data" in d and isinstance(d["data"], dict)
        data = d["data"]
        # Required top-level structured fields
        assert "claim_types" in data and isinstance(data["claim_types"], list) and len(data["claim_types"]) > 0
        assert "narrative" in data and isinstance(data["narrative"], dict)
        assert "what_happened" in data["narrative"]
        assert "remedy_sought" in data and isinstance(data["remedy_sought"], dict)
        assert "warnings_for_claimant" in data and isinstance(data["warnings_for_claimant"], list)
        # Top-level URLs / disclaimers wired
        assert "official_form_url" in d
        assert "acas_url" in d
        assert "disclaimer" in d

    def test_draft_claim_types_relevant_to_maternity_dismissal(self, et1_draft):
        cts = [c.lower() for c in et1_draft["data"]["claim_types"]]
        # Expect at least one of these for the maternity narrative
        assert any(k in " ".join(cts) for k in [
            "unfair_dismissal", "discrimination", "pregnancy", "maternity", "automatic_unfair"
        ]), f"Unexpected claim types: {cts}"

    def test_get_draft_for_owner(self, et1_draft, headers_primary):
        did = et1_draft["draft_id"]
        r = requests.get(f"{API}/forms/et1/{did}", headers=headers_primary, timeout=30)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["id"] == did
        assert rec["form"] == "ET1"
        assert "data" in rec and isinstance(rec["data"], dict)
        assert "_id" not in rec  # mongo objectId must be excluded

    def test_get_draft_other_user_forbidden(self, et1_draft, headers_second):
        did = et1_draft["draft_id"]
        r = requests.get(f"{API}/forms/et1/{did}", headers=headers_second, timeout=30)
        assert r.status_code == 404, f"Expected 404 for cross-user access, got {r.status_code}"

    def test_get_draft_unauth(self, et1_draft):
        did = et1_draft["draft_id"]
        r = requests.get(f"{API}/forms/et1/{did}", timeout=30)
        assert r.status_code in (401, 403)

    def test_update_draft_persists(self, et1_draft, headers_primary):
        did = et1_draft["draft_id"]
        new_data = dict(et1_draft["data"])
        new_data["narrative"] = dict(new_data.get("narrative", {}))
        marker = f"TEST_MARKER_{uuid.uuid4().hex[:8]}"
        new_data["narrative"]["what_happened"] = marker + " ::: updated"
        r = requests.put(
            f"{API}/forms/et1/{did}",
            json={"data": new_data},
            headers=headers_primary,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # Verify by GET
        g = requests.get(f"{API}/forms/et1/{did}", headers=headers_primary, timeout=30)
        assert g.status_code == 200
        got = g.json()["data"]
        assert got["narrative"]["what_happened"].startswith(marker)

    def test_update_draft_other_user_forbidden(self, et1_draft, headers_second):
        did = et1_draft["draft_id"]
        r = requests.put(
            f"{API}/forms/et1/{did}",
            json={"data": {"x": 1}},
            headers=headers_second,
            timeout=30,
        )
        assert r.status_code == 404

    def test_pdf_download_returns_pdf(self, et1_draft, headers_primary):
        did = et1_draft["draft_id"]
        r = requests.get(f"{API}/forms/et1/{did}/pdf", headers=headers_primary, timeout=60)
        assert r.status_code == 200, r.text[:300]
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower(), f"Expected pdf content-type, got {ct}"
        body = r.content
        assert len(body) > 1000, f"PDF too small ({len(body)} bytes)"
        assert body[:4] == b"%PDF", "Body does not start with %PDF magic bytes"

    def test_pdf_other_user_forbidden(self, et1_draft, headers_second):
        did = et1_draft["draft_id"]
        r = requests.get(f"{API}/forms/et1/{did}/pdf", headers=headers_second, timeout=30)
        assert r.status_code == 404

    def test_get_missing_draft_404(self, headers_primary):
        r = requests.get(f"{API}/forms/et1/does-not-exist-{uuid.uuid4().hex}", headers=headers_primary, timeout=20)
        assert r.status_code == 404

    def test_draft_requires_auth(self):
        r = requests.post(f"{API}/forms/et1/draft", json={"extra_context": NARRATIVE}, timeout=30)
        assert r.status_code in (401, 403)
