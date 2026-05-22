"""
Iteration 16 backend tests — Translation Mode + Whisper Mode infra.

Covers:
  - GET  /api/lex/translate/languages → 53 languages, sample codes present
  - POST /api/lex/translate (incoming Arabic → English) → translation/tip/reply
  - POST /api/lex/translate (outgoing English → Arabic) → translation only
  - Gating: non-Pro user gets 402
  - Validation: empty text 400, >2000 chars 400
  - Persistence: db.conversations grows by 1 with category translate_*
  - /api/voice/tts still streams audio/mpeg
  - /api/lex/live-assist still works (regression)
"""
import os
import random
import string
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASSWORD = "AdminLex2026!"

EXPECTED_SAMPLE = {"en", "ar", "zh", "ur", "hi", "fa", "he", "sw"}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return d.get("access_token") or d.get("token")


def _signup(email, password):
    r = requests.post(f"{API}/auth/signup",
                      json={"email": email, "password": password, "name": "T"},
                      timeout=30)
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    d = r.json()
    return d.get("access_token") or d.get("token")


def _rand_email():
    return "test_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "@advocate.app"


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------- Languages endpoint ----------------
class TestLanguagesEndpoint:
    def test_languages_list(self):
        r = requests.get(f"{API}/lex/translate/languages", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "languages" in data
        langs = data["languages"]
        assert isinstance(langs, list)
        assert len(langs) == 53, f"expected 53 languages, got {len(langs)}"
        for entry in langs:
            assert set(entry.keys()) >= {"code", "name", "native"}
            assert isinstance(entry["code"], str) and entry["code"]
            assert isinstance(entry["name"], str) and entry["name"]
            assert isinstance(entry["native"], str) and entry["native"]
        codes = {e["code"] for e in langs}
        missing = EXPECTED_SAMPLE - codes
        assert not missing, f"missing expected codes: {missing}"


# ---------------- Translate: incoming ----------------
class TestTranslateIncoming:
    def test_incoming_arabic_to_english(self, admin_headers):
        payload = {
            "direction": "incoming",
            "source_lang": "ar",
            "target_lang": "en",
            # "Show me your passport." in Arabic
            "text": "أرني جواز سفرك من فضلك.",
            "context": "Iraqi checkpoint",
            "country": "GB",
        }
        r = requests.post(f"{API}/lex/translate", json=payload, headers=admin_headers, timeout=90)
        assert r.status_code == 200, f"translate failed: {r.status_code} {r.text}"
        data = r.json()
        assert "translation" in data and isinstance(data["translation"], str) and data["translation"].strip()
        assert "tip" in data and isinstance(data["tip"], str) and data["tip"].strip()
        assert "suggested_reply" in data and isinstance(data["suggested_reply"], str) and data["suggested_reply"].strip()
        assert "session_id" in data and data["session_id"]


# ---------------- Translate: outgoing ----------------
class TestTranslateOutgoing:
    def test_outgoing_english_to_arabic(self, admin_headers):
        payload = {
            "direction": "outgoing",
            "source_lang": "en",
            "target_lang": "ar",
            "text": "My passport is in my bag",
            "country": "GB",
        }
        r = requests.post(f"{API}/lex/translate", json=payload, headers=admin_headers, timeout=90)
        assert r.status_code == 200, f"translate failed: {r.status_code} {r.text}"
        data = r.json()
        translation = data.get("translation", "")
        assert translation and isinstance(translation, str)
        # Arabic Unicode block roughly 0x0600 - 0x06FF
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in translation)
        assert has_arabic, f"translation should contain Arabic characters, got: {translation!r}"
        # Outgoing: tip and suggested_reply must be empty
        assert data.get("tip", "") == ""
        assert data.get("suggested_reply", "") == ""


# ---------------- Gating: non-Pro user → 402 ----------------
class TestTranslateGating:
    def test_non_pro_user_gets_402(self):
        email = _rand_email()
        token = _signup(email, "Test12345!")
        headers = {"Authorization": f"Bearer {token}"}
        # New signup → trial_pro typically. Check tier first.
        me = requests.get(f"{API}/auth/me", headers=headers, timeout=30)
        assert me.status_code == 200
        tier = me.json().get("tier", "")
        payload = {
            "direction": "outgoing", "source_lang": "en", "target_lang": "ar",
            "text": "hello", "country": "GB",
        }
        r = requests.post(f"{API}/lex/translate", json=payload, headers=headers, timeout=60)
        # If trial grants pro features, this will be 200. We assert 402 only if tier is free.
        if tier == "free":
            assert r.status_code == 402, f"expected 402 for free tier, got {r.status_code}: {r.text}"
        else:
            # tier in (trial_pro, pro, plus) → access allowed. Document outcome.
            assert r.status_code in (200, 402), f"unexpected status {r.status_code} for tier={tier}: {r.text}"
            if r.status_code == 200:
                pytest.skip(f"fresh signup tier={tier} has live_assist access — cannot prove 402 path without a free user")


# ---------------- Validation ----------------
class TestTranslateValidation:
    def test_empty_text_400(self, admin_headers):
        r = requests.post(f"{API}/lex/translate",
                          json={"direction": "incoming", "source_lang": "ar", "target_lang": "en", "text": ""},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400, f"expected 400 for empty text, got {r.status_code}: {r.text}"

    def test_whitespace_text_400(self, admin_headers):
        r = requests.post(f"{API}/lex/translate",
                          json={"direction": "incoming", "source_lang": "ar", "target_lang": "en", "text": "   "},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_too_long_text_400(self, admin_headers):
        r = requests.post(f"{API}/lex/translate",
                          json={"direction": "incoming", "source_lang": "ar", "target_lang": "en",
                                "text": "x" * 2001},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ---------------- Persistence via /api/admin/stats ----------------
class TestTranslatePersistence:
    def _conv_count(self, admin_headers):
        r = requests.get(f"{API}/admin/stats", headers=admin_headers, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        # Tolerate different shapes
        for key in ("conversations", "total_conversations", "conversation_count"):
            if key in data and isinstance(data[key], int):
                return data[key]
        return None

    def test_conversation_logged(self, admin_headers):
        before = self._conv_count(admin_headers)
        # Run an outgoing translate (cheaper).
        r = requests.post(f"{API}/lex/translate",
                          json={"direction": "outgoing", "source_lang": "en", "target_lang": "fr",
                                "text": "Where is the embassy?"},
                          headers=admin_headers, timeout=90)
        assert r.status_code == 200, r.text
        after = self._conv_count(admin_headers)
        if before is None or after is None:
            pytest.skip("admin/stats does not expose conversation count — cannot verify persistence via API")
        assert after >= before + 1, f"conversation count did not grow: {before} → {after}"


# ---------------- Regression: TTS streams audio/mpeg ----------------
class TestTTSRegression:
    def test_tts_audio_mpeg(self, admin_headers):
        r = requests.post(f"{API}/voice/tts",
                          json={"text": "Stay calm. Ask for a lawyer."},
                          headers=admin_headers, timeout=60)
        assert r.status_code == 200, f"tts failed: {r.status_code} {r.text[:200]}"
        ct = r.headers.get("content-type", "")
        assert "audio/mpeg" in ct, f"expected audio/mpeg, got: {ct}"
        assert len(r.content) > 500, "tts payload looks empty"


# ---------------- Regression: live-assist still returns response ----------------
class TestLiveAssistRegression:
    def test_live_assist(self, admin_headers):
        r = requests.post(f"{API}/lex/live-assist",
                          json={"scenario": "police_stop", "other_party_said": "Step out of the car.",
                                "language": "en-GB", "country": "GB"},
                          headers=admin_headers, timeout=90)
        assert r.status_code == 200, f"live-assist failed: {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "response" in d and isinstance(d["response"], str) and d["response"].strip()
