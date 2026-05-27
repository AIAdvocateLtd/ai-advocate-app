"""
Regression tests for the Admin Suggestions Inbox:

  GET    /api/admin/suggestions
  PATCH  /api/admin/suggestions/{id}
  DELETE /api/admin/suggestions/{id}

All three require admin auth (require_admin dep). The inbox reads from
db.feature_requests, which is populated by /feedback/suggest.

Run: pytest /app/backend/tests/test_admin_suggestions.py -v
"""

import os
import time
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"

ADMIN_EMAIL = os.environ.get("AA_TEST_ADMIN_EMAIL", "admin@aiadvocate.co.uk")
ADMIN_PASSWORD = os.environ.get("AA_TEST_ADMIN_PASSWORD", "AdminLex2026!")


def _admin_token() -> str:
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _signup_user() -> str:
    email = f"sugg_{int(time.time()*1000)}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": "Test12345!", "full_name": "Sugg Test",
        "language": "en-GB", "country": "GB", "device_id": f"sugg-{time.time()}",
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _create_suggestion(user_token: str, text: str) -> None:
    r = requests.post(
        f"{API}/feedback/suggest",
        json={"text": text},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200, r.text


def test_admin_list_requires_admin():
    """Non-admin users get 403."""
    user_tok = _signup_user()
    r = requests.get(f"{API}/admin/suggestions", headers={"Authorization": f"Bearer {user_tok}"})
    assert r.status_code == 403


def test_admin_list_returns_suggestions():
    user_tok = _signup_user()
    marker = f"unique-marker-{int(time.time()*1000)}"
    _create_suggestion(user_tok, f"Test suggestion {marker}")

    admin_tok = _admin_token()
    r = requests.get(f"{API}/admin/suggestions", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r.status_code == 200
    data = r.json()
    assert "suggestions" in data
    assert "open_count" in data
    # Our newly-created suggestion should be in the list
    assert any(marker in s["text"] for s in data["suggestions"])


def test_admin_mark_resolved_then_reopen():
    user_tok = _signup_user()
    marker = f"resolvable-{int(time.time()*1000)}"
    _create_suggestion(user_tok, f"Resolvable {marker}")

    admin_tok = _admin_token()
    items = requests.get(f"{API}/admin/suggestions",
                         headers={"Authorization": f"Bearer {admin_tok}"}).json()["suggestions"]
    target = next(s for s in items if marker in s["text"])

    # Mark resolved
    r = requests.patch(
        f"{API}/admin/suggestions/{target['id']}",
        json={"resolved": True, "admin_note": "fixed"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert r.status_code == 200

    # Verify it's in the resolved list
    resolved = requests.get(f"{API}/admin/suggestions?status=resolved",
                            headers={"Authorization": f"Bearer {admin_tok}"}).json()["suggestions"]
    assert any(s["id"] == target["id"] for s in resolved)

    # Reopen
    r = requests.patch(
        f"{API}/admin/suggestions/{target['id']}",
        json={"resolved": False},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert r.status_code == 200

    # Verify back in open list
    open_items = requests.get(f"{API}/admin/suggestions?status=open",
                              headers={"Authorization": f"Bearer {admin_tok}"}).json()["suggestions"]
    assert any(s["id"] == target["id"] for s in open_items)


def test_admin_delete_suggestion():
    user_tok = _signup_user()
    marker = f"deletable-{int(time.time()*1000)}"
    _create_suggestion(user_tok, f"Deletable {marker}")

    admin_tok = _admin_token()
    items = requests.get(f"{API}/admin/suggestions",
                         headers={"Authorization": f"Bearer {admin_tok}"}).json()["suggestions"]
    target = next(s for s in items if marker in s["text"])

    r = requests.delete(
        f"{API}/admin/suggestions/{target['id']}",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert r.status_code == 200

    # Verify it's gone
    items_after = requests.get(f"{API}/admin/suggestions",
                               headers={"Authorization": f"Bearer {admin_tok}"}).json()["suggestions"]
    assert not any(s["id"] == target["id"] for s in items_after)


def test_admin_delete_404_for_missing_id():
    admin_tok = _admin_token()
    r = requests.delete(
        f"{API}/admin/suggestions/does-not-exist-id",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert r.status_code == 404
