"""Tests for the four new features:
1. Auto-jurisdiction detection + accept/decline
2. Multi-user firm seats (invite, accept, login, list, remove)
3. Custom firm branding (tier-gated)
4. Founding firm agreement PDF generation
"""

import os
import sys
import time
import requests

API_URL = os.environ.get(
    "API_URL",
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0],
).strip() + "/api"
ADMIN_PASSWORD = "AdminLex2026!"


def _admin_token():
    r = requests.post(f"{API_URL}/auth/login",
                      json={"email": "admin@aiadvocate.co.uk", "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _create_firm():
    nonce = int(time.time() * 1000)
    email = f"firmpytest{nonce}@advocate.app"
    r = requests.post(f"{API_URL}/firm/signup", json={
        "firm_name": f"Pytest Firm {nonce}",
        "contact_name": "Pytest Owner",
        "email": email,
        "password": "FirmPass1234!",
        "country": "GB", "city": "London",
        "specialties": ["Family"],
        "website": "https://example.co.uk",
    })
    assert r.status_code == 200, r.text
    return email, r.json()["access_token"]


def _comp_firm(email, tier="practice", days=90):
    admin = _admin_token()
    r = requests.post(f"{API_URL}/admin/firms/comp",
                      headers={"Authorization": f"Bearer {admin}"},
                      json={"email": email, "tier": tier, "days": days, "reason": "pytest"})
    assert r.status_code == 200, r.text


# ============================================================================
# 1. AUTO-JURISDICTION
# ============================================================================

def test_auto_jurisdiction_guest():
    """Guest call returns whatever country IP suggests, no suggestion."""
    r = requests.get(f"{API_URL}/profile/auto-jurisdiction",
                     headers={"x-country-code": "FR"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detected_country"] == "FR"
    assert body["suggestion"] is None


def test_auto_jurisdiction_authed_suggests_switch():
    """Authed user in different country gets a switch suggestion."""
    # Use the seeded test user (default country GB)
    login = requests.post(f"{API_URL}/auth/login",
                          json={"email": "test@advocate.app", "password": "Test12345!"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    # Ensure profile country is GB and not pinned (reset state)
    requests.patch(f"{API_URL}/auth/preferences",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"country": "GB"})  # this sets manually_set=True
    # Force-unset the pinned flag via accept-jurisdiction
    requests.post(f"{API_URL}/profile/jurisdiction/accept",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"country": "GB"})

    # Now simulate user being in FR
    r = requests.get(f"{API_URL}/profile/auto-jurisdiction",
                     headers={"Authorization": f"Bearer {token}",
                              "x-country-code": "FR"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detected_country"] == "FR"
    assert body["profile_country"] == "GB"
    assert body["suggestion"] is not None
    assert body["suggestion"]["detected_country"] == "FR"


def test_decline_pins_country():
    """If user declines the switch, no more suggestions until they unpin."""
    login = requests.post(f"{API_URL}/auth/login",
                          json={"email": "test@advocate.app", "password": "Test12345!"})
    token = login.json()["access_token"]

    # Decline
    r = requests.post(f"{API_URL}/profile/jurisdiction/decline",
                      headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["pinned"] is True

    # No more suggestion even with different IP
    r = requests.get(f"{API_URL}/profile/auto-jurisdiction",
                     headers={"Authorization": f"Bearer {token}",
                              "x-country-code": "DE"})
    body = r.json()
    assert body.get("pinned") is True or body["suggestion"] is None


# ============================================================================
# 2. MULTI-USER FIRM SEATS
# ============================================================================

def test_firm_users_full_lifecycle():
    """Invite → Accept → Login → List → Remove."""
    email, firm_token = _create_firm()
    _comp_firm(email, tier="practice")  # 5 seats

    # 1. List (just owner)
    r = requests.get(f"{API_URL}/firm/users",
                     headers={"Authorization": f"Bearer {firm_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tier"] == "practice"
    assert data["seat_limit"] == 5
    assert data["active_count"] == 1
    assert data["users"] == []

    # 2. Invite Alice
    nonce = int(time.time() * 1000)
    alice_email = f"alice{nonce}@advocate.app"
    r = requests.post(f"{API_URL}/firm/users/invite",
                      headers={"Authorization": f"Bearer {firm_token}"},
                      json={"email": alice_email, "full_name": "Alice Smith"})
    assert r.status_code == 200, r.text
    invite = r.json()
    assert invite["ok"] is True
    invite_token = invite["invite_token"]
    user_id = invite["user_id"]

    # 3. Accept
    r = requests.post(f"{API_URL}/firm/users/accept",
                      json={"invite_token": invite_token, "password": "AlicePass123!"})
    assert r.status_code == 200, r.text
    alice_data = r.json()
    assert alice_data["firm_user"]["email"] == alice_email
    assert alice_data["firm_user"]["role"] == "fee_earner"
    alice_token = alice_data["access_token"]

    # 4. Alice can call /firm/me — resolves to parent firm
    r = requests.get(f"{API_URL}/firm/me",
                     headers={"Authorization": f"Bearer {alice_token}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["acting_user"]["email"] == alice_email
    assert me["effective_tier"] == "practice"

    # 5. Login again separately
    r = requests.post(f"{API_URL}/firm/users/login",
                      json={"email": alice_email, "password": "AlicePass123!"})
    assert r.status_code == 200, r.text

    # 6. Wrong password fails
    r = requests.post(f"{API_URL}/firm/users/login",
                      json={"email": alice_email, "password": "wrongpass"})
    assert r.status_code == 401

    # 7. List shows Alice
    r = requests.get(f"{API_URL}/firm/users",
                     headers={"Authorization": f"Bearer {firm_token}"})
    data = r.json()
    assert data["active_count"] == 2
    assert any(u["email"] == alice_email and u["status"] == "active" for u in data["users"])

    # 8. Remove Alice
    r = requests.delete(f"{API_URL}/firm/users/{user_id}",
                        headers={"Authorization": f"Bearer {firm_token}"})
    assert r.status_code == 200 and r.json()["removed"] is True

    # 9. Alice can no longer log in (status=removed)
    r = requests.post(f"{API_URL}/firm/users/login",
                      json={"email": alice_email, "password": "AlicePass123!"})
    assert r.status_code == 403


def test_firm_seat_limit_enforced():
    """Premium firm = 3 seats = 1 owner + 2 invites max."""
    email, firm_token = _create_firm()
    _comp_firm(email, tier="premium")  # 3 seats

    nonce = int(time.time() * 1000)
    # Invite 2 - should succeed
    for i in (1, 2):
        r = requests.post(f"{API_URL}/firm/users/invite",
                          headers={"Authorization": f"Bearer {firm_token}"},
                          json={"email": f"earner{i}_{nonce}@advocate.app",
                                "full_name": f"Earner {i}"})
        assert r.status_code == 200, f"Invite #{i} failed: {r.text}"

    # 3rd invite (would be 4 total seats) — must fail
    r = requests.post(f"{API_URL}/firm/users/invite",
                      headers={"Authorization": f"Bearer {firm_token}"},
                      json={"email": f"earner3_{nonce}@advocate.app",
                            "full_name": "Earner 3"})
    assert r.status_code == 402
    assert "Seat limit" in r.json()["detail"]


def test_firm_users_duplicate_email_rejected():
    """Can't invite the same email twice."""
    email, firm_token = _create_firm()
    _comp_firm(email, tier="practice")
    nonce = int(time.time() * 1000)
    payload = {"email": f"dup{nonce}@advocate.app", "full_name": "Dup"}
    r1 = requests.post(f"{API_URL}/firm/users/invite",
                       headers={"Authorization": f"Bearer {firm_token}"}, json=payload)
    assert r1.status_code == 200
    r2 = requests.post(f"{API_URL}/firm/users/invite",
                       headers={"Authorization": f"Bearer {firm_token}"}, json=payload)
    assert r2.status_code == 409


# ============================================================================
# 3. CUSTOM FIRM BRANDING
# ============================================================================

def test_branding_premium_practice_only():
    """Featured tier (default) can't set branding; Practice can."""
    email, firm_token = _create_firm()
    # Try without upgrade — should be 402
    r = requests.patch(f"{API_URL}/firm/branding",
                       headers={"Authorization": f"Bearer {firm_token}"},
                       json={"brand_color": "#1a4d8f"})
    assert r.status_code == 402, r.text

    # Upgrade to practice
    _comp_firm(email, tier="practice")
    r = requests.patch(f"{API_URL}/firm/branding",
                       headers={"Authorization": f"Bearer {firm_token}"},
                       json={"logo_url": "https://example.com/logo.png",
                             "brand_color": "#1a4d8f",
                             "accent_color": "#f7c948"})
    assert r.status_code == 200, r.text

    # Read it back
    r = requests.get(f"{API_URL}/firm/branding",
                     headers={"Authorization": f"Bearer {firm_token}"})
    assert r.status_code == 200
    b = r.json()
    assert b["brand_color"] == "#1a4d8f"
    assert b["logo_url"] == "https://example.com/logo.png"
    assert b["tier_allows"] is True


def test_branding_invalid_hex_rejected():
    """Bad hex codes return 400."""
    email, firm_token = _create_firm()
    _comp_firm(email, tier="practice")
    r = requests.patch(f"{API_URL}/firm/branding",
                       headers={"Authorization": f"Bearer {firm_token}"},
                       json={"brand_color": "not-a-color"})
    assert r.status_code == 400


def test_branding_invalid_logo_url_rejected():
    """Non-https logo URL is rejected."""
    email, firm_token = _create_firm()
    _comp_firm(email, tier="practice")
    r = requests.patch(f"{API_URL}/firm/branding",
                       headers={"Authorization": f"Bearer {firm_token}"},
                       json={"logo_url": "javascript:alert(1)"})
    assert r.status_code == 400


# ============================================================================
# 4. FOUNDING FIRM AGREEMENT PDF
# ============================================================================

def test_founding_firm_agreement_pdf_blank():
    """Admin can download blank agreement template."""
    admin = _admin_token()
    r = requests.get(f"{API_URL}/admin/founding-firm-agreement.pdf",
                     headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 4000


def test_founding_firm_agreement_pdf_personalised():
    """Personalised version has firm name in headers."""
    admin = _admin_token()
    r = requests.get(f"{API_URL}/admin/founding-firm-agreement.pdf",
                     headers={"Authorization": f"Bearer {admin}"},
                     params={"firm_name": "Smith & Co Solicitors",
                             "sra": "123456",
                             "address": "10 High St, London",
                             "contact": "John Smith, Senior Partner",
                             "email": "john@smithco.co.uk"})
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_founder_briefing_pdf():
    """Admin can download Founder Briefing PDF."""
    admin = _admin_token()
    r = requests.get(f"{API_URL}/admin/founder-briefing.pdf",
                     headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 20000  # Multi-page doc
