"""
Iteration 15 backend tests:
  - Admin/owner override → tier='pro', is_owner=True, has_access=True
  - Admin can use deep_think + court_prep category (was Plus+ only)
  - Non-admin signup → tier in (trial_pro, free) and NOT is_owner
  - POST /api/voice/transcribe still works (multipart audio field)
  - POST /api/lex/live-assist still works
"""
import os
import io
import wave
import struct
import random
import string
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASSWORD = "AdminLex2026!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token")


def _signup(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/signup",
        json={"email": email, "password": password, "name": "Test User"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token")


def _rand_email() -> str:
    return "test_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "@advocate.app"


def _make_wav_bytes(seconds: float = 1.0, sr: int = 16000) -> bytes:
    """Tiny mono 16-bit silent WAV — Whisper accepts and returns empty text."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        n = int(sr * seconds)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


# -------------- ADMIN / OWNER --------------

class TestAdminOwner:
    def test_admin_login_returns_owner_pro(self):
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "no access_token returned"

        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me.get("tier") == "pro", f"expected tier=pro, got {me.get('tier')}"
        assert me.get("is_owner") is True, f"expected is_owner=True, got {me.get('is_owner')}"
        assert me.get("has_access") is True

    def test_admin_can_deep_think(self):
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        r = requests.post(
            f"{API}/lex/chat",
            json={"message": "Briefly: what is adverse possession in UK law?", "deep_think": True},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        # Owner should NOT get 402 (payment) for deep_think
        assert r.status_code != 402, f"admin blocked from deep_think with 402: {r.text}"
        assert r.status_code == 200, f"deep_think failed: {r.status_code} {r.text}"
        body = r.json()
        assert any(k in body for k in ("reply", "message", "answer", "response")), f"no reply field: {body.keys()}"

    def test_admin_can_court_prep_category(self):
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        r = requests.post(
            f"{API}/lex/chat",
            json={"message": "Help me prep for a small claims hearing.", "category": "court_prep"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        assert r.status_code != 402, f"admin blocked from court_prep with 402: {r.text}"
        assert r.status_code == 200, f"court_prep failed: {r.status_code} {r.text}"


# -------------- NON-ADMIN --------------

class TestNonAdminTier:
    def test_signup_user_is_not_owner_and_not_pro(self):
        email = _rand_email()
        token = _signup(email, "Test12345!")
        assert token
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text
        me = r.json()
        # Should be trial_pro (during trial) or free — but NEVER 'pro' via owner override
        assert me.get("tier") in ("trial_pro", "free"), f"unexpected tier: {me.get('tier')}"
        assert not me.get("is_owner"), f"non-admin should not have is_owner=True: {me}"


# -------------- VOICE TRANSCRIBE --------------

class TestVoiceEndpoints:
    def test_voice_transcribe_accepts_audio_multipart(self):
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        wav = _make_wav_bytes(seconds=1.0)
        files = {"audio": ("chunk.wav", wav, "audio/wav")}
        r = requests.post(
            f"{API}/voice/transcribe",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        # Whisper can return empty text for silence but the endpoint must accept the file and 200
        assert r.status_code == 200, f"/voice/transcribe failed: {r.status_code} {r.text}"
        body = r.json()
        # Accept 'text' or 'transcript' or 'transcription'
        assert any(k in body for k in ("text", "transcript", "transcription")), f"no transcript field: {body}"

    def test_lex_live_assist_returns_advice(self):
        token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        r = requests.post(
            f"{API}/lex/live-assist",
            json={
                "scenario": "small_claims_hearing",
                "other_party_said": "You didn't pay rent for three months — why?",
                "transcript": "The judge just asked me why I didn't pay rent for three months.",
                "facts": "Tenant in private rented flat, withheld rent due to mould.",
                "context": "small_claims_hearing",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        assert r.status_code == 200, f"/lex/live-assist failed: {r.status_code} {r.text}"
        body = r.json()
        # Accept several response shapes — advice/reply/say_this/message
        assert any(k in body for k in ("advice", "reply", "say_this", "message", "answer", "response")), f"no advice field: {body}"
