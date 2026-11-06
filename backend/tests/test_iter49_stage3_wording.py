# Stage 3 fair-use WORDING regression (iteration 49). No AI calls.
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

BANNED = re.compile(r"unlimited lex|unlimited chat|5 lex chats|lex chat \(3|unlimited ask lex|5 free chats", re.I)


@pytest.fixture(scope="module")
def tiers():
    r = requests.get(f"{API}/subscription/tiers", timeout=30)
    assert r.status_code == 200
    return {t["id"]: t for t in r.json()["tiers"]}


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{API}/auth/login", json={"email": "test@advocate.app", "password": "Test12345!"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    return r.json().get("token") or r.json().get("access_token")


# Tiers endpoint wording
class TestTiers:
    def test_free_first_highlight(self, tiers):
        assert tiers["free"]["highlights"][0] == "2 free Lex questions (lifetime — chat, letter or document check)"

    def test_plus_highlights(self, tiers):
        h = tiers["plus"]["highlights"]
        for s in ["300 Lex messages / month (fair use: up to 40 a day)", "20 letters / month", "Premium AI (GPT-5.2)",
                  "15 evidence & document analyses / month"]:
            assert s in h, s

    def test_pro_highlights(self, tiers):
        h = tiers["pro"]["highlights"]
        assert "600 Lex messages / month (fair use: up to 80 a day)" in h
        assert "50 letters + 25 document analyses / month" in h
        assert any("6 sessions / month" in x for x in h)

    def test_yearly_live_assist(self, tiers):
        assert "Live Assist — 6 sessions / month (up to 5 a day)" in tiers["yearly"]["highlights"]

    def test_no_banned_strings(self, tiers):
        for t in tiers.values():
            for x in t["highlights"]:
                assert not BANNED.search(x), x

    def test_prices_unchanged(self, tiers):
        assert tiers["plus"]["price_gbp"] == 19.99
        assert tiers["pro"]["price_gbp"] == 34.99
        assert tiers["yearly"]["price_gbp"] == 319.99


# Top-up packs taglines (auth required)
class TestTopups:
    def test_requires_auth(self):
        r = requests.get(f"{API}/topups/packs", timeout=30)
        assert r.status_code in (401, 403)

    def test_taglines(self, user_token):
        r = requests.get(f"{API}/topups/packs", headers={"Authorization": f"Bearer {user_token}"}, timeout=30)
        assert r.status_code == 200
        packs = {p["id"]: p for p in r.json()["packs"]}
        assert packs["day_pass"]["tagline"] == "50 Lex messages, 2 letters + 5 evidence photos for 24h."
        assert packs["weekend_pass"]["tagline"] == "Plus for 72 hours: 120 Lex messages, 5 letters, 5 analyses."
        assert packs["crisis_pack"]["tagline"].startswith("Pro for 24h: 80 Lex messages incl. 5 Deep Think")
        lp = packs["letter_pack"]
        assert "+ up to 100 Lex messages · 30-day use-by." in lp["tagline"]
        for p in packs.values():
            assert not BANNED.search(p.get("tagline", ""))


# Static terms.html Fair use section ordering
class TestTermsHtml:
    def test_6c_between_6b_and_7(self):
        r = requests.get(f"{BASE_URL}/terms.html", timeout=30)
        assert r.status_code == 200
        t = r.text
        i6b, i6c, i7 = t.find("<h2>6b."), t.find("<h2>6c. Fair use</h2>"), t.find("<h2>7. Misuse</h2>")
        assert -1 < i6b < i6c < i7
        for h in ["1. Not legal advice", "6a. One-time Top-up packs", "8. Termination", "16. Abuse prevention"]:
            assert h in t
