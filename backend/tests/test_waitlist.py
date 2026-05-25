"""
Regression tests for the pre-launch marketing landing + waitlist.

Run: pytest /app/backend/tests/test_waitlist.py -v
"""
import os
import time
import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"


def test_waitlist_join_success():
    email = f"wl_{int(time.time())}@advocate.app"
    r = requests.post(f"{API}/waitlist/join", json={"email": email, "country": "GB", "source": "pytest"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["already_registered"] is False
    assert body["joined_at"]


def test_waitlist_idempotent():
    email = f"wl_idem_{int(time.time())}@advocate.app"
    r1 = requests.post(f"{API}/waitlist/join", json={"email": email, "source": "ig"})
    assert r1.status_code == 200
    assert r1.json()["already_registered"] is False
    # Second join with same email should NOT duplicate
    r2 = requests.post(f"{API}/waitlist/join", json={"email": email, "source": "twitter"})
    assert r2.status_code == 200
    assert r2.json()["already_registered"] is True


def test_waitlist_disposable_email_blocked():
    email = f"farmer_{int(time.time())}@mailinator.com"
    r = requests.post(f"{API}/waitlist/join", json={"email": email, "source": "ig"})
    assert r.status_code == 400
    assert "disposable" in r.text.lower() or "temporary" in r.text.lower()


def test_admin_waitlist_requires_admin():
    """A non-admin user must not be able to read the waitlist."""
    # Create a regular user
    r = requests.post(f"{API}/auth/signup", json={
        "email": f"regular_{int(time.time())}@advocate.app",
        "password": "Test12345!", "full_name": "Reg", "language": "en-GB",
        "country": "GB", "device_id": f"d-{time.time()}",
    })
    token = r.json()["access_token"]
    # Try to access admin endpoint
    r2 = requests.get(f"{API}/admin/waitlist", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 403


def test_landing_page_reachable():
    """The static landing HTML must be served at /welcome.html."""
    base = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
    r = requests.get(f"{base}/welcome.html")
    assert r.status_code == 200
    assert "AI Advocate" in r.text
    assert "Join the waitlist" in r.text.lower() or "waitlist" in r.text.lower()
