"""
Iteration 8 — Extended auto-detect tests for German, Italian, Portuguese, Polish.
Confirms the new score-based detect_language() handles a broader set of languages
correctly (no ` la ` overlap bug between French/Spanish/Italian).
"""
import os
import time
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "ai_advocate_db"


def _signup(prefix="iter8"):
    email = f"TEST_{prefix}_{int(time.time()*1000)}_{os.urandom(2).hex()}@advocate.app"
    r = requests.post(
        f"{BASE}/api/auth/signup",
        json={"email": email, "password": "Test12345!", "full_name": "Iter8 Tester",
              "country": "GB", "language": "en-GB"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    return j["access_token"], email, j["user"]["id"]


async def _force_pro(email):
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    await db.users.update_one(
        {"email": email},
        {"$set": {"tier": "pro", "subscription_status": "active",
                  "trial_end_date": "2020-01-01T00:00:00+00:00"}},
    )
    cli.close()


@pytest.fixture
def pro_user():
    token, email, uid = _signup("pro_lang")
    asyncio.get_event_loop().run_until_complete(_force_pro(email))
    return {"token": token, "email": email}


def _hdr(u):
    return {"Authorization": f"Bearer {u['token']}"}


def _chat(user, msg):
    r = requests.post(
        f"{BASE}/api/lex/chat",
        headers=_hdr(user),
        json={"message": msg, "language": "en-GB", "country": "GB",
              "auto_detect": True, "deep_think": False},
        timeout=60,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    return r.json()


class TestExtraLanguages:
    def test_german_detected(self, pro_user):
        j = _chat(pro_user, "Guten Tag, ich brauche dringend Rechtsberatung wegen meiner Wohnung.")
        assert j["reply_language"] == "de-DE", f"got {j['reply_language']}"

    def test_italian_detected(self, pro_user):
        j = _chat(pro_user, "Buongiorno, vorrei sapere quali sono i miei diritti di inquilino.")
        assert j["reply_language"] == "it-IT", f"got {j['reply_language']}"

    def test_portuguese_detected(self, pro_user):
        j = _chat(pro_user, "Olá, gostaria de saber quais são os meus direitos como inquilino.")
        assert j["reply_language"] == "pt-PT", f"got {j['reply_language']}"

    def test_polish_detected(self, pro_user):
        j = _chat(pro_user, "Dzień dobry, chciałbym zapytać o moje prawa jako najemca mieszkania.")
        assert j["reply_language"] == "pl-PL", f"got {j['reply_language']}"

    def test_spanish_la_does_not_overlap_french(self, pro_user):
        # The original bug: Spanish " la " also appears in French — must NOT mis-detect French as Spanish
        j = _chat(pro_user, "Hola, qué hago si mi casero no me devuelve la fianza?")
        assert j["reply_language"] == "es-ES", f"got {j['reply_language']}"

    def test_french_la_does_not_overlap_spanish(self, pro_user):
        j = _chat(pro_user, "Bonjour, je voudrais savoir quels sont mes droits?")
        assert j["reply_language"] == "fr-FR", f"got {j['reply_language']}"
