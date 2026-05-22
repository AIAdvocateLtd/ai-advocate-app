"""Iter 17 — Embassy directory + Multi-contact SOS + Lawyer Standby + Watch token."""

import os
import re
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASS = "AdminLex2026!"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def free_user():
    """Sign up a fresh user. NOTE: signup auto-grants trial_pro. We then verify the
    Pro gating on lawyer_standby works for users who are NOT pro. If the new signup
    happens to land in 'free' or 'trial_pro' tier we still record token + tier."""
    email = f"test_iter17_{uuid.uuid4().hex[:8]}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "Test12345!", "name": "Iter17"}, timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"signup failed: {r.status_code} {r.text}")
    body = r.json()
    return {"token": body.get("token") or body.get("access_token"),
            "tier": (body.get("user") or {}).get("tier", "unknown"),
            "email": email}


# ---------- Embassy directory ----------

class TestEmbassy:
    def test_lookup_iq(self):
        r = requests.get(f"{API}/embassy/lookup", params={"country": "IQ"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["country"] == "IQ"
        assert "Baghdad" in data["embassy"]["name"]
        assert data["embassy"]["phone"] == "+964 7901 926 280"

    def test_lookup_unknown_country_returns_fcdo_fallback(self):
        r = requests.get(f"{API}/embassy/lookup", params={"country": "ZZ"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is False
        # FCDO 24/7 fallback should be exposed
        text = str(data)
        assert "+44 20 7008 5000" in text, f"FCDO fallback number missing: {data}"

    def test_embassy_all_returns_25(self):
        r = requests.get(f"{API}/embassy/all", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 25
        assert len(data["embassies"]) == 25


# ---------- Emergency Contacts CRUD ----------

class TestEmergencyContacts:
    def test_get_contacts_admin(self, admin_headers):
        r = requests.get(f"{API}/emergency/contacts", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        for k in ("contacts", "lawyer_standby_enabled", "lawyer_standby_radius_km", "sos_message", "watch_token"):
            assert k in body, f"missing key {k}"

    def test_round_trip_persists_all_fields(self, admin_headers):
        payload = {
            "contacts": [
                {"name": "Spouse Jane", "relationship": "Spouse", "phone": "+447700900001",
                 "email": "jane@example.com", "include_in_sos": True, "is_lawyer": False},
                {"name": "Solicitor Mark", "relationship": "Lawyer", "phone": "+447700900002",
                 "email": "mark@law.example", "include_in_sos": True, "is_lawyer": True},
            ],
            "lawyer_standby_enabled": True,
            "lawyer_standby_radius_km": 35.0,
            "sos_message": "Detained abroad — contact UK FCDO + send lawyer.",
        }
        r = requests.post(f"{API}/emergency/contacts", json=payload, headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["saved"] is True
        assert r.json()["contact_count"] == 2

        # GET it back
        g = requests.get(f"{API}/emergency/contacts", headers=admin_headers, timeout=15).json()
        assert len(g["contacts"]) == 2
        assert g["lawyer_standby_enabled"] is True
        assert g["lawyer_standby_radius_km"] == 35.0
        assert "Detained abroad" in g["sos_message"]
        lawyers = [c for c in g["contacts"] if c.get("is_lawyer")]
        assert len(lawyers) == 1
        assert lawyers[0]["name"] == "Solicitor Mark"
        assert lawyers[0]["phone"] == "+447700900002"

    def test_free_tier_blocked_for_lawyer_standby(self, free_user):
        if not free_user["token"]:
            pytest.skip("no free user token")
        # Force-check the gate: send lawyer_standby_enabled=true
        h = {"Authorization": f"Bearer {free_user['token']}", "Content-Type": "application/json"}
        payload = {"contacts": [{"name": "Foo", "phone": "+10000000000"}],
                   "lawyer_standby_enabled": True}
        r = requests.post(f"{API}/emergency/contacts", json=payload, headers=h, timeout=15)
        # If user landed in trial_pro/pro tier, gate won't fire — record as xfail.
        if free_user["tier"] in ("trial_pro", "pro"):
            assert r.status_code in (200, 402), f"unexpected {r.status_code}: {r.text}"
            if r.status_code == 200:
                pytest.skip(f"fresh user tier={free_user['tier']} has live_assist; 402 path unreachable")
        else:
            assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"

    def test_free_tier_contacts_only_saves(self, free_user):
        if not free_user["token"]:
            pytest.skip("no free user token")
        h = {"Authorization": f"Bearer {free_user['token']}", "Content-Type": "application/json"}
        payload = {"contacts": [{"name": "Solo Free", "phone": "+10000000001"}],
                   "lawyer_standby_enabled": False}
        r = requests.post(f"{API}/emergency/contacts", json=payload, headers=h, timeout=15)
        assert r.status_code == 200, r.text


# ---------- Watch token ----------

class TestWatchToken:
    def test_generate_watch_token(self, admin_headers):
        r = requests.post(f"{API}/emergency/watch-token", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        tok = body["watch_token"]
        assert isinstance(tok, str) and len(tok) >= 24
        assert "wt=" in body["trigger_url"]
        # Stash for next test
        pytest.iter17_watch_token = tok


# ---------- Silent SOS ----------

class TestSilentSOS:
    def test_get_silent_sos_with_watch_token(self, admin_headers):
        # Ensure we have a token + contacts
        wt = getattr(pytest, "iter17_watch_token", None)
        if not wt:
            wt = requests.post(f"{API}/emergency/watch-token", headers=admin_headers, timeout=15).json()["watch_token"]
        # Hit GET — NO Authorization header
        r = requests.get(f"{API}/emergency/silent-sos",
                         params={"wt": wt, "lat": 33.31, "lng": 44.36, "src": "watch"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "sos_id" in body
        assert body["notified"] >= 2  # admin saved 2 contacts above
        assert "standby_pinged" in body

    def test_post_silent_sos_with_jwt(self, admin_headers):
        r = requests.post(f"{API}/emergency/silent-sos",
                         json={"latitude": 51.5, "longitude": -0.12, "country": "GB", "source": "phone"},
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "sos_id" in body
        assert body["notified"] >= 2

    def test_sos_history_returns_events(self, admin_headers):
        r = requests.get(f"{API}/emergency/sos-history", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        events = r.json()["events"]
        assert len(events) >= 2
        # Filter to silent-SOS events (legacy /emergency/rights events also live in this collection)
        sos_events = [e for e in events if "source" in e]
        assert len(sos_events) >= 2, f"expected silent-SOS events, got: {events[:3]}"
        sources = {e["source"] for e in sos_events}
        assert "phone" in sources or "watch" in sources
        for e in sos_events[:5]:
            assert "notified_contacts" in e
            assert "duress" in e

    def test_silent_sos_no_auth_rejected(self):
        # POST without JWT and without wt
        r = requests.post(f"{API}/emergency/silent-sos", json={"latitude": 1.0, "longitude": 2.0}, timeout=15)
        assert r.status_code == 401


# ---------- Lawfirms geo ----------

class TestLawfirmsGeo:
    def test_lawfirms_geo_sorts_by_distance(self):
        r = requests.get(f"{API}/lawfirms", params={"latitude": 51.5, "longitude": -0.12, "max_km": 50}, timeout=15)
        assert r.status_code == 200
        firms = r.json()
        # Some firms may not have lat/lng — filter list returned shoudl all have distance_km within max
        with_dist = [f for f in firms if f.get("distance_km") is not None]
        assert len(with_dist) >= 1, "expected at least one geo-located firm within 50km of London"
        for f in with_dist:
            assert f["distance_km"] <= 50
        # Sorted ascending by distance (within sponsored buckets)
        non_sponsored = [f for f in with_dist if not f.get("sponsored")]
        if len(non_sponsored) >= 2:
            dists = [f["distance_km"] for f in non_sponsored]
            assert dists == sorted(dists), f"non-sponsored not sorted by distance: {dists}"
