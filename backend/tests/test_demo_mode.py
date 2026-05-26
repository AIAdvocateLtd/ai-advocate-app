"""
Regression tests for the Sample/Demo mode flow:

  POST /api/auth/demo  →  returns a JWT for the shared demo account with
  fresh sample case data seeded. Designed for App Store reviewers.

Run: pytest /app/backend/tests/test_demo_mode.py -v
"""

import os
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"


def _demo_login():
    r = requests.post(f"{API}/auth/demo")
    assert r.status_code == 200, r.text
    return r.json()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_demo_endpoint_returns_token_and_is_demo_flag():
    data = _demo_login()
    assert "access_token" in data
    assert data["user"]["email"] == "demo@aiadvocate.co.uk"
    assert data["user"]["is_demo"] is True


def test_demo_seed_creates_case_with_items():
    data = _demo_login()
    cases = requests.get(f"{API}/cases", headers=_auth_headers(data["access_token"])).json()["cases"]
    assert len(cases) == 1
    case = cases[0]
    assert "Sarah v. Acme Ltd" in case["name"]
    assert case["category"] == "employment"
    assert case["status"] == "open"


def test_demo_seed_includes_grievance_letter():
    data = _demo_login()
    files = requests.get(f"{API}/legal-files", headers=_auth_headers(data["access_token"])).json()
    letters = [f for f in files if "Grievance" in (f.get("filename") or "")]
    assert len(letters) >= 1, f"Expected grievance letter, got: {[f.get('filename') for f in files]}"


def test_demo_seed_includes_reminders():
    data = _demo_login()
    reminders = requests.get(f"{API}/reminders", headers=_auth_headers(data["access_token"])).json()["reminders"]
    titles = [r["title"] for r in reminders]
    assert any("ACAS" in t for t in titles), f"Missing ACAS reminder: {titles}"
    assert any("ET1" in t or "Tribunal" in t for t in titles), f"Missing tribunal reminder: {titles}"


def test_demo_reseed_wipes_old_data():
    """Calling /auth/demo twice should leave exactly one case (not duplicate)."""
    _demo_login()
    data = _demo_login()
    cases = requests.get(f"{API}/cases", headers=_auth_headers(data["access_token"])).json()["cases"]
    assert len(cases) == 1, f"Expected 1 case after reseed, got {len(cases)}"


def test_demo_endpoint_works_without_auth():
    """No auth header should be required — public entry point."""
    r = requests.post(f"{API}/auth/demo")
    assert r.status_code == 200
