"""
Iteration 7 — Validates Lex tier-based brain routing, auto-detect language,
Deep Think gating, and Emergency-rights TTS gating.
"""
import os
import time
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL must be set"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "ai_advocate_db"

SONNET = "claude-sonnet-4-5-20250929"
HAIKU = "claude-haiku-4-5-20251001"


def _signup(prefix="iter7"):
    """Create a fresh user, return (token, email, user_id)."""
    email = f"TEST_{prefix}_{int(time.time()*1000)}_{os.urandom(2).hex()}@advocate.app"
    r = requests.post(
        f"{BASE}/api/auth/signup",
        json={"email": email, "password": "Test12345!", "full_name": "Iter7 Tester",
              "country": "GB", "language": "en-GB"},
        timeout=20,
    )
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    j = r.json()
    return j["access_token"], email, j["user"]["id"]


async def _force_tier(email, tier):
    """Directly mutate mongo to force a tier (expire trial for free)."""
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    update = {"tier": tier}
    if tier == "free":
        update["subscription_status"] = "free"
        update["trial_end_date"] = "2020-01-01T00:00:00+00:00"
    elif tier in ("plus", "pro", "yearly"):
        # Paid subscriber → subscription_status must be 'active' for user_to_public to honor tier
        update["subscription_status"] = "active"
        update["trial_end_date"] = "2020-01-01T00:00:00+00:00"
    await db.users.update_one({"email": email}, {"$set": update})
    cli.close()


@pytest.fixture
def free_user():
    token, email, uid = _signup("free")
    asyncio.get_event_loop().run_until_complete(_force_tier(email, "free"))
    return {"token": token, "email": email, "uid": uid}


@pytest.fixture
def plus_user():
    token, email, uid = _signup("plus")
    asyncio.get_event_loop().run_until_complete(_force_tier(email, "plus"))
    return {"token": token, "email": email, "uid": uid}


@pytest.fixture
def pro_user():
    token, email, uid = _signup("pro")
    asyncio.get_event_loop().run_until_complete(_force_tier(email, "pro"))
    return {"token": token, "email": email, "uid": uid}


@pytest.fixture
def trial_user():
    # Fresh signup → trial_pro by default per server logic
    token, email, uid = _signup("trial")
    return {"token": token, "email": email, "uid": uid}


def _hdr(u):
    return {"Authorization": f"Bearer {u['token']}"}


# ---------- TIER-BASED MODEL ROUTING ----------
class TestTierRouting:
    def test_free_user_uses_haiku_or_falls_back(self, free_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(free_user),
            json={"message": "Hello, what is GDPR?", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, f"free chat failed: {r.status_code} {r.text}"
        j = r.json()
        assert "model" in j, "response missing 'model' field"
        assert j["model"] in (HAIKU, SONNET), f"unexpected model: {j['model']}"
        assert j.get("reply_language") == "en-GB"
        assert isinstance(j.get("response"), str) and len(j["response"]) > 0

    def test_plus_user_uses_sonnet(self, plus_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(plus_user),
            json={"message": "What is GDPR?", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["model"] == SONNET

    def test_pro_user_uses_sonnet(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "What is GDPR?", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["model"] == SONNET

    def test_trial_user_uses_sonnet(self, trial_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(trial_user),
            json={"message": "What is GDPR?", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["model"] == SONNET


# ---------- DEEP THINK GATING ----------
class TestDeepThink:
    def test_free_user_deep_think_blocked_402(self, free_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(free_user),
            json={"message": "Explain Article 8 ECHR", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": True},
            timeout=20,
        )
        assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text}"
        assert "Deep Think" in r.json().get("detail", "")

    def test_plus_user_deep_think_blocked_402(self, plus_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(plus_user),
            json={"message": "Explain Article 8 ECHR", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": True},
            timeout=60,
        )
        assert r.status_code == 402, r.text

    def test_pro_user_deep_think_ok(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "Explain Article 8 ECHR briefly", "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": True},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        assert r.json()["model"] == SONNET


# ---------- AUTO-DETECT LANGUAGE ----------
class TestAutoDetect:
    def test_spanish_in_english_ui_detects_es(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "Hola, ¿qué es la ley GDPR? Soy usuario nuevo.",
                  "language": "en-GB", "country": "GB",
                  "auto_detect": True, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["reply_language"] == "es-ES", f"expected es-ES, got {j['reply_language']}"

    def test_french_in_english_ui_detects_fr(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "Bonjour, je voudrais savoir, qu'est-ce que c'est la loi?",
                  "language": "en-GB", "country": "GB",
                  "auto_detect": True, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["reply_language"] == "fr-FR"

    def test_arabic_detected(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "مرحبا، ما هو القانون في المملكة المتحدة؟",
                  "language": "en-GB", "country": "GB",
                  "auto_detect": True, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["reply_language"] == "ar-IQ"

    def test_hindi_devanagari_detected(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "नमस्ते, कानून क्या है?",
                  "language": "en-GB", "country": "GB",
                  "auto_detect": True, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["reply_language"] == "hi-IN"

    def test_chinese_cjk_detected(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "你好，请问什么是法律？",
                  "language": "en-GB", "country": "GB",
                  "auto_detect": True, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["reply_language"] == "zh-CN"

    def test_auto_detect_off_preserves_ui_language(self, pro_user):
        r = requests.post(
            f"{BASE}/api/lex/chat",
            headers=_hdr(pro_user),
            json={"message": "Hola, ¿qué tal?",
                  "language": "en-GB", "country": "GB",
                  "auto_detect": False, "deep_think": False},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json()["reply_language"] == "en-GB"


# ---------- TTS GATING ----------
class TestTTS:
    def test_short_tts_free_user_ok(self, free_user):
        r = requests.post(
            f"{BASE}/api/voice/tts",
            headers=_hdr(free_user),
            json={"text": "You have the right to remain silent.", "voice": "alloy"},
            timeout=60,
        )
        assert r.status_code == 200, f"short TTS for free user failed: {r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("audio/")
        assert len(r.content) > 500

    def test_long_tts_free_user_blocked_402(self, free_user):
        long_text = "This is a long form text. " * 80  # ~2080 chars
        assert len(long_text) > 1500
        r = requests.post(
            f"{BASE}/api/voice/tts",
            headers=_hdr(free_user),
            json={"text": long_text, "voice": "alloy"},
            timeout=20,
        )
        assert r.status_code == 402, f"expected 402 for long TTS on free, got {r.status_code}"


# ---------- EMERGENCY RIGHTS sanity ----------
class TestEmergencyRights:
    def test_emergency_rights_free_user_ok(self, free_user):
        r = requests.post(
            f"{BASE}/api/emergency/rights",
            headers=_hdr(free_user),
            json={"language": "en-GB", "country": "GB"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        j = r.json()
        # Endpoint should return some kind of rights text
        assert isinstance(j, dict)
        # accept any of these keys for text
        text = j.get("rights_script") or j.get("rights") or j.get("text") or j.get("response") or ""
        assert isinstance(text, str) and len(text) > 50, f"rights body too short: {j}"
