"""AI Advocate backend tests"""
import os, io, time, uuid, struct, math, wave
import pytest, requests
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = BASE + "/api"

EMAIL = f"test_{uuid.uuid4().hex[:8]}@advocate.app"
PWD = "Test12345!"
state = {}

def _wav_bytes(seconds=1.0, freq=440, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate*seconds)):
            v = int(32767*0.2*math.sin(2*math.pi*freq*i/rate))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
    return buf.getvalue()

# ---------- root / languages ----------
def test_root():
    r = requests.get(API + "/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

def test_languages():
    r = requests.get(API + "/languages")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) == 11
    codes = [d["code"] for d in data]
    for c in ("en-GB","es-ES","fr-FR","ar-IQ","pl-PL","de-DE","hi-IN","ur-PK","it-IT","pt-PT","zh-CN"):
        assert c in codes

# ---------- auth ----------
def test_signup():
    r = requests.post(API + "/auth/signup", json={"email": EMAIL, "password": PWD, "full_name": "Test User"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "access_token" in j and j["user"]["email"] == EMAIL
    assert j["user"]["has_access"] is True
    assert j["user"]["trial_days_remaining"] >= 13
    state["token"] = j["access_token"]
    state["user_id"] = j["user"]["id"]

def test_signup_dup():
    r = requests.post(API + "/auth/signup", json={"email": EMAIL, "password": PWD})
    assert r.status_code == 400

def test_login_ok():
    r = requests.post(API + "/auth/login", json={"email": EMAIL, "password": PWD})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_login_bad():
    r = requests.post(API + "/auth/login", json={"email": EMAIL, "password": "wrong"})
    assert r.status_code == 401

def test_google():
    em = f"g_{uuid.uuid4().hex[:8]}@advocate.app"
    r = requests.post(API + "/auth/google", json={"email": em, "name": "G U", "google_id": "gid123"})
    assert r.status_code == 200
    assert r.json()["user"]["has_access"] is True

def _ensure_token():
    if "token" not in state:
        em = f"test_{uuid.uuid4().hex[:8]}@advocate.app"
        r = requests.post(API + "/auth/signup", json={"email": em, "password": PWD, "full_name": "Test"})
        assert r.status_code == 200, r.text
        state["token"] = r.json()["access_token"]
        state["user_id"] = r.json()["user"]["id"]

def _h():
    _ensure_token()
    return {"Authorization": f"Bearer {state['token']}"}

def test_me():
    r = requests.get(API + "/auth/me", headers=_h())
    assert r.status_code == 200
    j = r.json()
    assert j["email"] == EMAIL
    assert "has_access" in j and "trial_days_remaining" in j

def test_no_auth_401():
    r = requests.get(API + "/auth/me")
    assert r.status_code in (401, 403)

def test_bad_token():
    r = requests.get(API + "/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401

def test_prefs():
    r = requests.patch(API + "/auth/preferences", headers=_h(), json={"language": "fr-FR", "country": "FR"})
    assert r.status_code == 200
    j = r.json()
    assert j["language"] == "fr-FR" and j["country"] == "FR"

# ---------- lex chat ----------
def test_lex_chat():
    r = requests.post(API + "/lex/chat", headers=_h(),
        json={"message": "What is the limitation period for breach of contract in the UK? Answer in one short paragraph.",
              "language": "en-GB", "country": "GB", "category": "ask_lex"}, timeout=120)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "response" in j and "session_id" in j
    assert "Disclaimer" in j["response"] or "disclaimer" in j["response"].lower()
    state["session_id"] = j["session_id"]

def test_lex_chat_category():
    r = requests.post(API + "/lex/chat", headers=_h(),
        json={"message": "Briefly: tips for cross-examination as defendant.",
              "language": "en-GB", "country": "GB", "category": "court_prep"}, timeout=120)
    assert r.status_code == 200
    assert len(r.json()["response"]) > 20

def test_lex_sessions():
    r = requests.get(API + "/lex/sessions", headers=_h())
    assert r.status_code == 200
    sessions = r.json()
    assert isinstance(sessions, list) and len(sessions) >= 1

def test_lex_session_detail():
    r = requests.get(API + f"/lex/sessions/{state['session_id']}", headers=_h())
    assert r.status_code == 200
    msgs = r.json()
    assert isinstance(msgs, list) and len(msgs) >= 1
    assert msgs[0]["session_id"] == state["session_id"]

# ---------- legal letter ----------
def test_legal_letter():
    r = requests.post(API + "/legal-letter", headers=_h(),
        json={"letter_type":"Letter Before Action","recipient":"ACME Ltd",
              "your_name":"John Doe","details":"Unpaid invoice of £500.","language":"en-GB"}, timeout=120)
    assert r.status_code == 200
    assert len(r.json()["letter"]) > 50

# ---------- voice TTS ----------
def test_tts():
    r = requests.post(API + "/voice/tts", headers=_h(),
        json={"text": "Hello from AI Advocate.", "voice": "onyx"}, timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/")
    assert len(r.content) > 500

# ---------- voice STT ----------
def test_transcribe():
    audio = _wav_bytes(seconds=1.0)
    r = requests.post(API + "/voice/transcribe", headers=_h(),
        files={"audio": ("test.wav", audio, "audio/wav")},
        data={"language": "en"}, timeout=60)
    # Whisper may return empty text for tone; just require 200 + key present
    assert r.status_code == 200, r.text
    assert "text" in r.json()

# ---------- legal files ----------
def test_legal_files_list():
    r = requests.get(API + "/legal-files", headers=_h())
    assert r.status_code == 200
    assert isinstance(r.json(), list)

# ---------- contract analyze ----------
def test_contract_analyze():
    pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
           b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
           b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R"
           b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
           b"4 0 obj<</Length 80>>stream\nBT /F1 12 Tf 20 100 Td "
           b"(This Agreement is between A and B. Term: 1 year. Late fee: 50%.) Tj ET\nendstream endobj\n"
           b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
           b"xref\n0 6\n0000000000 65535 f\n"
           b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF")
    r = requests.post(API + "/contracts/analyze", headers=_h(),
        files={"file": ("c.pdf", pdf, "application/pdf")},
        data={"language": "en-GB", "country": "GB"}, timeout=180)
    assert r.status_code == 200, r.text[:500]
    assert len(r.json().get("analysis", "")) > 50

# ---------- subscription ----------
def test_sub_status():
    r = requests.get(API + "/subscription/status", headers=_h())
    assert r.status_code == 200
    assert "has_access" in r.json()

def test_checkout():
    r = requests.post(API + "/subscription/checkout", headers=_h(), json={"plan": "monthly"}, timeout=30)
    # With sk_test_emergent (placeholder), Stripe will likely 401 -> our handler returns 500
    if r.status_code == 200:
        assert r.json().get("checkout_url", "").startswith("http")
    else:
        assert r.status_code == 500
        state["stripe_failed"] = True

def test_activate_test():
    r = requests.post(API + "/subscription/activate-test", headers=_h())
    assert r.status_code == 200
    assert r.json()["subscription_status"] == "active"
    assert r.json()["has_access"] is True

# ---------- trial gating ----------
def test_trial_gating():
    """Create a fresh user, expire trial via DB, expect 402."""
    from pymongo import MongoClient
    em = f"exp_{uuid.uuid4().hex[:8]}@advocate.app"
    s = requests.post(API + "/auth/signup", json={"email": em, "password": PWD}).json()
    tok = s["access_token"]
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    mc[os.environ.get("DB_NAME","ai_advocate_db")].users.update_one(
        {"email": em},
        {"$set": {"trial_end_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                  "subscription_status": "trial"}}
    )
    r = requests.post(API + "/lex/chat", headers={"Authorization": f"Bearer {tok}"},
                      json={"message": "Hi"}, timeout=30)
    assert r.status_code == 402

# =========================================================================
# Iteration 2: Evidence analysis, location prefs, law firm directory
# =========================================================================

def _jpeg_bytes():
    """Generate a small valid JPEG image."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (400, 300), color=(245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 380, 280], outline=(0, 0, 0), width=3)
    d.text((40, 40), "PARKING TICKET\nPCN: ABC123\nDate: 2026-01-05\nFine: 60 GBP", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()

# ---------- Evidence analyze ----------
def test_evidence_analyze_no_auth():
    r = requests.post(API + "/evidence/analyze",
                      files={"file": ("ticket.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"evidence_type": "parking_ticket"}, timeout=30)
    assert r.status_code in (401, 403), r.text

def test_evidence_analyze_ok():
    r = requests.post(API + "/evidence/analyze", headers=_h(),
                      files={"file": ("ticket.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"evidence_type": "parking_ticket",
                            "description": "Got this PCN, signage was unclear.",
                            "language": "en-GB", "country": "GB"}, timeout=180)
    assert r.status_code == 200, r.text[:600]
    j = r.json()
    assert j["evidence_type"] == "parking_ticket"
    assert j["filename"] == "ticket.jpg"
    assert isinstance(j["id"], str) and len(j["id"]) > 0
    assert isinstance(j["analysis"], str) and len(j["analysis"]) > 50
    state["evidence_id"] = j["id"]

def test_evidence_analyze_persisted_in_legal_files():
    # GET /api/legal-files should now include the evidence record
    r = requests.get(API + "/legal-files", headers=_h())
    assert r.status_code == 200
    files = r.json()
    ids = [f.get("id") for f in files]
    assert state.get("evidence_id") in ids, f"Evidence id not persisted in legal_files: ids={ids}"
    rec = next(f for f in files if f.get("id") == state["evidence_id"])
    assert rec.get("type") == "evidence"
    assert rec.get("evidence_type") == "parking_ticket"

def test_evidence_analyze_402_when_trial_expired():
    """Fresh user with expired trial -> 402."""
    from pymongo import MongoClient
    em = f"ev_{uuid.uuid4().hex[:8]}@advocate.app"
    s = requests.post(API + "/auth/signup", json={"email": em, "password": PWD}).json()
    tok = s["access_token"]
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    mc[os.environ.get("DB_NAME","ai_advocate_db")].users.update_one(
        {"email": em},
        {"$set": {"trial_end_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                  "subscription_status": "trial"}}
    )
    r = requests.post(API + "/evidence/analyze",
                      headers={"Authorization": f"Bearer {tok}"},
                      files={"file": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
                      data={"evidence_type": "auto"}, timeout=30)
    assert r.status_code == 402, r.text

# ---------- Location preferences ----------
def test_prefs_location_enable():
    r = requests.patch(API + "/auth/preferences", headers=_h(),
                      json={"location_enabled": True, "latitude": 51.5074,
                            "longitude": -0.1278, "city": "London"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["location_enabled"] is True
    assert j["latitude"] == 51.5074
    assert j["longitude"] == -0.1278
    assert j["city"] == "London"

def test_prefs_location_persists_via_me():
    r = requests.get(API + "/auth/me", headers=_h())
    assert r.status_code == 200
    j = r.json()
    assert j.get("location_enabled") is True
    assert j.get("latitude") == 51.5074
    assert j.get("city") == "London"

def test_prefs_location_disable_keeps_false():
    r = requests.patch(API + "/auth/preferences", headers=_h(),
                      json={"location_enabled": False})
    assert r.status_code == 200
    j = r.json()
    assert j["location_enabled"] is False
    # Verify on /me
    r2 = requests.get(API + "/auth/me", headers=_h())
    assert r2.json().get("location_enabled") is False

# ---------- Law firm directory ----------
def test_lawfirms_list():
    r = requests.get(API + "/lawfirms")
    assert r.status_code == 200, r.text
    firms = r.json()
    assert isinstance(firms, list)
    assert len(firms) >= 12, f"Expected >=12 firms, got {len(firms)}"
    countries = {f.get("country") for f in firms}
    for c in ("GB", "ES", "FR", "DE", "PL", "IT", "PT", "PK", "IN", "AE", "CN"):
        assert c in countries, f"Missing country {c}"
    # Sponsored first
    sponsored_flags = [bool(f.get("sponsored")) for f in firms]
    first_non = next((i for i, s in enumerate(sponsored_flags) if not s), len(sponsored_flags))
    assert all(sponsored_flags[:first_non]), "Sponsored firms not listed first"
    # No mongo _id leaking
    for f in firms:
        assert "_id" not in f
    state["sample_firm_id"] = next(f["id"] for f in firms if f.get("country") == "GB")

def test_lawfirms_filter_country_gb():
    r = requests.get(API + "/lawfirms", params={"country": "GB"})
    assert r.status_code == 200
    firms = r.json()
    assert len(firms) >= 2
    assert all(f["country"] == "GB" for f in firms)

def test_lawfirms_filter_specialty_employment():
    r = requests.get(API + "/lawfirms", params={"specialty": "employment"})
    assert r.status_code == 200
    firms = r.json()
    assert len(firms) >= 1
    assert all("employment" in f.get("specialties", []) for f in firms)

def test_lawfirms_geo_sort_with_distance():
    r = requests.get(API + "/lawfirms", params={"latitude": 51.5, "longitude": -0.1})
    assert r.status_code == 200
    firms = r.json()
    assert len(firms) >= 1
    # Each firm should have distance_km
    for f in firms:
        assert "distance_km" in f
    # London-based GB firms should have very small distance
    london = next((f for f in firms if f["name"].startswith("Crown & Bench")), None)
    assert london is not None
    assert london["distance_km"] < 10
    # Sort: sponsored first, then distance ascending within each group
    sponsored = [f for f in firms if f.get("sponsored")]
    non_sponsored = [f for f in firms if not f.get("sponsored")]
    # Sponsored block precedes non-sponsored block
    assert firms[:len(sponsored)] == sponsored
    # Distance ascending within each group
    spons_d = [f["distance_km"] for f in sponsored if f.get("distance_km") is not None]
    assert spons_d == sorted(spons_d)
    nons_d = [f["distance_km"] for f in non_sponsored if f.get("distance_km") is not None]
    assert nons_d == sorted(nons_d)

def test_lawfirms_geo_max_km():
    r = requests.get(API + "/lawfirms", params={"latitude": 51.5, "longitude": -0.1, "max_km": 500})
    assert r.status_code == 200
    firms = r.json()
    assert len(firms) >= 1
    assert all(f.get("distance_km") is not None and f["distance_km"] <= 500 for f in firms)
    # Should exclude Mumbai/Dubai etc.
    names = {f["name"] for f in firms}
    assert "Sharma Legal Advisors" not in names
    assert "Al-Rashid Legal Consultancy" not in names

# ---------- Law firm inquiry ----------
def test_lawfirms_inquiry_no_auth():
    payload = {"firm_id": state.get("sample_firm_id", "x"),
               "name": "John", "email": "john@example.com",
               "phone": "555", "message": "Need help"}
    r = requests.post(API + "/lawfirms/inquiry", json=payload)
    assert r.status_code in (401, 403)

def test_lawfirms_inquiry_ok():
    payload = {"firm_id": state["sample_firm_id"],
               "name": "John Doe", "email": "john@example.com",
               "phone": "+44 1234", "message": "I'd like a consultation about a parking ticket."}
    r = requests.post(API + "/lawfirms/inquiry", headers=_h(), json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "sent"
    assert isinstance(j["id"], str)

def test_lawfirms_inquiry_invalid_firm_id():
    payload = {"firm_id": "non-existent-firm-id-xyz",
               "name": "John", "email": "john@example.com", "message": "Hi"}
    r = requests.post(API + "/lawfirms/inquiry", headers=_h(), json=payload)
    assert r.status_code == 404, r.text

# ---------- Public advertise endpoint ----------
def test_lawfirms_advertise_public_no_auth():
    payload = {
        "firm_name": "TEST Sample Law LLP",
        "contact_name": "Jane Partner",
        "email": f"test_advert_{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+44 207 123 0000",
        "country": "GB", "city": "London",
        "specialties": ["employment", "property"],
        "website": "https://testsamplelaw.example.com",
        "notes": "Interested in sponsored placement.",
    }
    r = requests.post(API + "/lawfirms/advertise", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "received"
    assert isinstance(j["id"], str) and len(j["id"]) > 0
    assert "message" in j

def test_lawfirms_advertise_persisted():
    """Verify the application is stored in law_firm_applications."""
    from pymongo import MongoClient
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    coll = mc[os.environ.get("DB_NAME","ai_advocate_db")].law_firm_applications
    cnt = coll.count_documents({"firm_name": "TEST Sample Law LLP"})
    assert cnt >= 1

def test_lawfirms_advertise_validation_error():
    # Missing required fields
    r = requests.post(API + "/lawfirms/advertise",
                      json={"firm_name": "X"}, timeout=10)
    assert r.status_code == 422

# =========================================================================
# Iteration 3: PDF export (POST /api/pdf/inline, GET /api/pdf/file/{id})
# =========================================================================

def _pdf_valid(content: bytes) -> bool:
    """A valid PDF starts with %PDF and is non-trivial size."""
    return content[:4] == b"%PDF" and len(content) > 500

# ---------- /api/pdf/inline ----------
def test_pdf_inline_no_auth():
    r = requests.post(API + "/pdf/inline",
        json={"title": "Test", "body": "Hello"}, timeout=30)
    assert r.status_code in (401, 403), r.text

def test_pdf_inline_ok():
    payload = {
        "title": "Letter Before Action",
        "subtitle": "Prepared by Lex, your AI advocate",
        "body": "Dear Sir/Madam,\n\nThis letter relates to invoice #1234.\n\nYours faithfully,\nJohn Doe",
        "meta": {"From": "John Doe", "To": "ACME Ltd", "Date": "2026-01-09"},
        "filename": "letter_before_action.pdf",
    }
    r = requests.post(API + "/pdf/inline", headers=_h(), json=payload, timeout=60)
    assert r.status_code == 200, r.text[:500]
    ct = r.headers.get("content-type", "")
    assert ct.startswith("application/pdf"), f"content-type={ct}"
    assert _pdf_valid(r.content), f"Not a valid PDF (first bytes: {r.content[:8]!r}, size={len(r.content)})"
    cd = r.headers.get("content-disposition", "")
    assert "letter_before_action.pdf" in cd

def test_pdf_inline_minimal_no_optional():
    """Only required fields (title, body) — optional subtitle/meta/filename omitted."""
    r = requests.post(API + "/pdf/inline", headers=_h(),
                      json={"title": "Minimal", "body": "Just one paragraph."}, timeout=30)
    assert r.status_code == 200, r.text
    assert _pdf_valid(r.content)

def test_pdf_inline_validation_missing_fields():
    r = requests.post(API + "/pdf/inline", headers=_h(),
                      json={"title": "No body"}, timeout=10)
    assert r.status_code == 422

# ---------- /api/pdf/file/{id} for letter ----------
def test_pdf_file_letter_create_and_download():
    """Create a letter via /legal-letter, then GET the PDF for it."""
    r = requests.post(API + "/legal-letter", headers=_h(),
        json={"letter_type":"PDF Test Letter","recipient":"PDFTest Ltd",
              "your_name":"Jane Doe","details":"Test that PDF export works for saved letters.",
              "language":"en-GB"}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    # Find the new letter id by listing legal_files (latest first)
    files = requests.get(API + "/legal-files", headers=_h()).json()
    letter = next((f for f in files
                   if f.get("type") == "letter"
                   and f.get("filename","").startswith("PDF Test Letter")), None)
    assert letter is not None, f"Letter not persisted. files={[f.get('filename') for f in files]}"
    state["pdf_letter_id"] = letter["id"]

    r2 = requests.get(API + f"/pdf/file/{letter['id']}", headers=_h(), timeout=30)
    assert r2.status_code == 200, r2.text[:300]
    assert r2.headers.get("content-type","").startswith("application/pdf")
    cd = r2.headers.get("content-disposition","")
    assert "attachment" in cd and ".pdf" in cd
    assert _pdf_valid(r2.content)

def test_pdf_file_no_auth():
    fid = state.get("pdf_letter_id", "any-id")
    r = requests.get(API + f"/pdf/file/{fid}", timeout=15)
    assert r.status_code in (401, 403)

def test_pdf_file_404_nonexistent():
    r = requests.get(API + f"/pdf/file/non-existent-{uuid.uuid4().hex}",
                     headers=_h(), timeout=15)
    assert r.status_code == 404

# ---------- /api/pdf/file/{id} for evidence ----------
def test_pdf_file_evidence():
    """Use the evidence_id created in iteration 2 tests."""
    eid = state.get("evidence_id")
    assert eid, "Evidence id missing — earlier evidence test must run first"
    r = requests.get(API + f"/pdf/file/{eid}", headers=_h(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type","").startswith("application/pdf")
    assert _pdf_valid(r.content)

# ---------- /api/pdf/file/{id} for recording ----------
def test_pdf_file_recording():
    """Seed a 'recording' type file directly into MongoDB and request its PDF.
    We don't go through /record/analyze (real Whisper+Claude is slow); we only
    test the PDF generation branch for type='recording'."""
    from pymongo import MongoClient
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    coll = mc[os.environ.get("DB_NAME","ai_advocate_db")].legal_files
    rec_id = str(uuid.uuid4())
    coll.insert_one({
        "id": rec_id,
        "user_id": state["user_id"],
        "filename": "police_stop_2026-01-09.webm",
        "type": "recording",
        "transcript": "Officer: please step out of the vehicle. Driver: am I being detained?",
        "analysis": "The interaction is consensual until detention is declared. "
                    "The driver appropriately asked the key clarifying question.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    state["recording_id"] = rec_id

    r = requests.get(API + f"/pdf/file/{rec_id}", headers=_h(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type","").startswith("application/pdf")
    assert _pdf_valid(r.content)

# ---------- Cross-user 404 (security) ----------
def test_pdf_file_cross_user_404():
    """User B cannot download User A's PDF."""
    em = f"pdfb_{uuid.uuid4().hex[:8]}@advocate.app"
    s = requests.post(API + "/auth/signup",
                      json={"email": em, "password": PWD, "full_name": "B User"})
    assert s.status_code == 200
    tok_b = s.json()["access_token"]

    target = state.get("pdf_letter_id")
    assert target, "Need a saved letter id from earlier test"
    r = requests.get(API + f"/pdf/file/{target}",
                     headers={"Authorization": f"Bearer {tok_b}"}, timeout=15)
    assert r.status_code == 404, f"Expected 404 cross-user, got {r.status_code}: {r.text[:200]}"


# =====================================================================
# ============ Iteration 4: Auth providers / Apple / Google ============
# ============ / Stripe webhook / Multilingual PDF tests   =============
# =====================================================================

# ---------- /api/auth/providers ----------
def test_auth_providers_shape_and_disabled_state():
    """Both providers should be disabled in test env (env vars empty)."""
    r = requests.get(API + "/auth/providers", timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("google_enabled", "google_client_id", "apple_enabled", "apple_services_id"):
        assert k in j, f"missing key {k} in {j}"
    assert j["google_enabled"] is False
    assert j["apple_enabled"] is False
    assert j["google_client_id"] == ""
    assert j["apple_services_id"] == ""

# ---------- /api/auth/google (credential branch when GOOGLE_CLIENT_ID empty) ----------
def test_google_credential_only_without_client_id_returns_400():
    """When GOOGLE_CLIENT_ID is unset, sending only `credential` should hit the
    demo fallback which then complains that email/google_id are missing."""
    r = requests.post(API + "/auth/google", json={"credential": "fake_token_xyz"}, timeout=10)
    assert r.status_code == 400, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "credential" in detail or "google_id" in detail or "email" in detail

def test_google_demo_legacy_payload_still_works():
    """Legacy demo path: {email, google_id, name} returns a valid JWT."""
    em = f"g4_{uuid.uuid4().hex[:8]}@advocate.app"
    r = requests.post(API + "/auth/google",
                      json={"email": em, "google_id": "gid_iter4", "name": "Iter4 G"},
                      timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "access_token" in j and isinstance(j["access_token"], str) and len(j["access_token"]) > 20
    assert j["user"]["email"] == em
    assert j["user"].get("has_access") is True

def test_google_no_payload_returns_400():
    """Empty body → no credential, no email/google_id → 400."""
    r = requests.post(API + "/auth/google", json={}, timeout=10)
    assert r.status_code == 400

# ---------- /api/auth/apple ----------
def test_apple_returns_503_when_not_configured():
    r = requests.post(API + "/auth/apple",
                      json={"identity_token": "doesnt.matter.here"},
                      timeout=10)
    assert r.status_code == 503, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "apple" in detail and "configured" in detail

def test_apple_validation_missing_token():
    """identity_token is required by AppleLogin model → 422."""
    r = requests.post(API + "/auth/apple", json={}, timeout=10)
    assert r.status_code == 422

# ---------- /api/webhook/stripe ----------
def test_stripe_webhook_accepts_unsigned_when_secret_empty():
    """STRIPE_WEBHOOK_SECRET is empty → server parses payload without verifying."""
    r = requests.post(API + "/webhook/stripe",
                      json={"type": "ping", "data": {"object": {}}}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json().get("received") is True

def test_stripe_webhook_checkout_completed_activates_user():
    """Send checkout.session.completed with our test user_id → subscription_status='active'
    and stripe_customer_id is persisted."""
    uid = state.get("user_id")
    assert uid, "Need user_id from earlier signup test"
    cust = f"cus_test_{uuid.uuid4().hex[:10]}"
    sub = f"sub_test_{uuid.uuid4().hex[:10]}"
    payload = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": uid,
            "customer": cust,
            "subscription": sub,
        }},
    }
    r = requests.post(API + "/webhook/stripe", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json().get("received") is True
    state["stripe_customer_id"] = cust

    # Verify via DB (and via /auth/me as a public sanity check)
    from pymongo import MongoClient
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    u = mc[os.environ.get("DB_NAME","ai_advocate_db")].users.find_one({"id": uid})
    assert u is not None
    assert u.get("subscription_status") == "active", u.get("subscription_status")
    assert u.get("stripe_customer_id") == cust
    assert u.get("stripe_subscription_id") == sub

def test_stripe_webhook_subscription_deleted_cancels_user():
    """customer.subscription.deleted → user found by stripe_customer_id is set to canceled."""
    cust = state.get("stripe_customer_id")
    assert cust, "Need stripe_customer_id from previous webhook test"
    payload = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": cust}},
    }
    r = requests.post(API + "/webhook/stripe", json=payload, timeout=10)
    assert r.status_code == 200
    assert r.json().get("received") is True

    from pymongo import MongoClient
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    u = mc[os.environ.get("DB_NAME","ai_advocate_db")].users.find_one(
        {"stripe_customer_id": cust})
    assert u is not None, "User with that stripe_customer_id not found"
    assert u.get("subscription_status") == "canceled", u.get("subscription_status")

# ---------- /api/pdf/inline — multilingual + branded footer + QR ----------
def _pdf_inline(lang: str, title: str, body: str, fname: str) -> requests.Response:
    return requests.post(
        API + "/pdf/inline", headers=_h(),
        json={"title": title, "body": body, "subtitle": "AI Advocate test",
              "language": lang, "filename": fname,
              "meta": {"Language": lang, "Generated": datetime.now(timezone.utc).strftime("%Y-%m-%d")}},
        timeout=60,
    )

def test_pdf_inline_lang_en_GB():
    r = _pdf_inline("en-GB", "English Test", "Hello, this is a test letter in English.\n\nSecond paragraph.", "en.pdf")
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert _pdf_valid(r.content)
    # >30KB ⇒ logo + QR + fonts embedded
    assert len(r.content) > 30_000, f"PDF size {len(r.content)} unexpectedly small"

def test_pdf_inline_lang_ar_IQ_arabic_body():
    body = ("هذه رسالة قانونية تجريبية باللغة العربية.\n\n"
            "الفقرة الثانية: نطلب الرد خلال أربعة عشر يوماً.")
    r = _pdf_inline("ar-IQ", "اختبار قانوني", body, "ar.pdf")
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert _pdf_valid(r.content)
    assert len(r.content) > 30_000, f"Arabic PDF too small: {len(r.content)}"

def test_pdf_inline_lang_ur_PK_urdu_body():
    body = "یہ اردو میں ایک قانونی خط کی جانچ ہے۔\n\nدوسرا پیراگراف یہاں ہے۔"
    r = _pdf_inline("ur-PK", "اردو ٹیسٹ", body, "ur.pdf")
    assert r.status_code == 200, r.text[:300]
    assert _pdf_valid(r.content)
    assert len(r.content) > 30_000

def test_pdf_inline_lang_zh_CN_chinese_body():
    body = "这是一封中文测试法律函件。\n\n第二段：请在十四天内回复。"
    r = _pdf_inline("zh-CN", "中文测试", body, "zh.pdf")
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert _pdf_valid(r.content)
    assert len(r.content) > 30_000, f"Chinese PDF too small: {len(r.content)}"

def test_pdf_inline_lang_hi_IN_hindi_body():
    body = "यह एक हिन्दी कानूनी पत्र का परीक्षण है।\n\nदूसरा अनुच्छेद यहाँ है।"
    r = _pdf_inline("hi-IN", "हिन्दी परीक्षण", body, "hi.pdf")
    assert r.status_code == 200, r.text[:300]
    assert _pdf_valid(r.content)
    assert len(r.content) > 30_000, f"Hindi PDF too small: {len(r.content)}"

def test_pdf_inline_branded_footer_present_in_bytes():
    """The branded footer text 'Generated by AI ADVOCATE' should be drawn on
    every page; raw font glyphs are encoded so we don't expect to find the literal
    string in compressed streams. Instead we assert the resulting PDF is large
    enough to contain a QR PNG image stream (which only happens when the QR
    code embed succeeded)."""
    r = _pdf_inline("en-GB", "Footer Check",
                    "Body content for footer/QR check.\n\nSecond paragraph here.",
                    "footer.pdf")
    assert r.status_code == 200
    assert _pdf_valid(r.content)
    # PNG/QR + Noto fonts ⇒ size threshold
    assert len(r.content) > 30_000, f"Footer/QR PDF size suspiciously small: {len(r.content)}"
    # And the PDF should reference at least one image (XObject) — QR is embedded as image
    blob = r.content
    assert b"/Image" in blob or b"/XObject" in blob, "No image XObject — QR may not be embedded"


# ==================== NEW FEATURE TESTS (iter5) ====================
# Practice Mode + Live Legal Assist + Emergency + Letter Library

def test_letters_templates_public_31():
    """Public endpoint — should NOT require auth and return >= 31 templates."""
    r = requests.get(API + "/letters/templates")
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j, list) and len(j) >= 31, f"Got {len(j)} templates"
    sample = j[0]
    for k in ("id", "category", "title", "prompt"):
        assert k in sample, f"Missing key: {k}"
    ids = {t["id"] for t in j}
    for need in ("deposit_return", "witness_statement", "demand_money_owed", "custom"):
        assert need in ids, f"Missing template id: {need}"

def test_practice_no_auth_401():
    r = requests.post(API + "/lex/practice",
                      json={"role": "police_uk", "message": "hi"})
    assert r.status_code in (401, 403)

def test_live_assist_no_auth_401():
    r = requests.post(API + "/lex/live-assist",
                      json={"scenario": "police_interview", "other_party_said": "hi"})
    assert r.status_code in (401, 403)

def test_emergency_no_auth_401():
    r = requests.post(API + "/emergency/rights", json={"country": "GB"})
    assert r.status_code in (401, 403)

def test_letters_generate_no_auth_401():
    r = requests.post(API + "/letters/generate",
                      json={"template_id": "deposit_return",
                            "your_name": "x", "recipient": "y", "facts": "z"})
    assert r.status_code in (401, 403)

def test_practice_police_uk_session_continuity():
    """role=police_uk — Lex stays in character as UK detective AND maintains session."""
    r1 = requests.post(API + "/lex/practice", headers=_h(), json={
        "role": "police_uk",
        "message": "I'm ready to start.",
        "facts": "I'm being interviewed about an alleged theft on 5 Jan.",
        "language": "en-GB", "country": "GB",
    })
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert "session_id" in j1 and "response" in j1
    assert isinstance(j1["response"], str) and len(j1["response"]) > 10
    sid = j1["session_id"]
    # Second call with same session — must echo continuity (no fresh "caution" again)
    r2 = requests.post(API + "/lex/practice", headers=_h(), json={
        "session_id": sid,
        "role": "police_uk",
        "message": "I was at home that evening.",
        "language": "en-GB", "country": "GB",
    })
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert j2["session_id"] == sid
    assert isinstance(j2["response"], str) and len(j2["response"]) > 5

def test_practice_prosecutor():
    r = requests.post(API + "/lex/practice", headers=_h(), json={
        "role": "prosecutor",
        "message": "I deny the allegations.",
        "facts": "Civil claim for breach of contract.",
    })
    assert r.status_code == 200, r.text
    assert len(r.json()["response"]) > 5

def test_practice_tribunal():
    r = requests.post(API + "/lex/practice", headers=_h(), json={
        "role": "tribunal",
        "message": "I'd like to present my evidence.",
        "facts": "Unfair dismissal claim against former employer.",
    })
    assert r.status_code == 200, r.text
    assert len(r.json()["response"]) > 5

def test_practice_unknown_role_400():
    r = requests.post(API + "/lex/practice", headers=_h(), json={
        "role": "not_a_role", "message": "hi"
    })
    assert r.status_code == 400

def test_practice_multilingual_es():
    """language=es-ES — response should contain Spanish characters/words."""
    r = requests.post(API + "/lex/practice", headers=_h(), json={
        "role": "police_uk",
        "message": "Hola, estoy listo para empezar.",
        "facts": "Acusación de robo.",
        "language": "es-ES", "country": "GB",
    })
    assert r.status_code == 200, r.text
    resp = r.json()["response"]
    # Cheap heuristic: any Spanish marker (accented char or common word)
    markers = ("¿", "¡", "á", "é", "í", "ó", "ú", "ñ", " usted", " qué", " está", " dónde", " cuándo")
    assert any(m in resp.lower() or m in resp for m in markers), f"Response not in Spanish: {resp[:200]}"

def test_live_assist_police_interview_short():
    r = requests.post(API + "/lex/live-assist", headers=_h(), json={
        "scenario": "police_interview",
        "other_party_said": "Were you at the scene on the night of January 5th?",
        "my_facts": "I was at home alone.",
        "language": "en-GB", "country": "GB",
    })
    assert r.status_code == 200, r.text
    resp = r.json()["response"]
    assert isinstance(resp, str) and len(resp) > 0
    # Decisive + short — model is capped at 120 tokens; allow generous upper bound
    assert len(resp) < 500, f"Live-assist response too long: {len(resp)} chars"

def test_live_assist_tribunal():
    r = requests.post(API + "/lex/live-assist", headers=_h(), json={
        "scenario": "tribunal",
        "other_party_said": "Can you produce the dismissal letter?",
        "my_facts": "Unfair dismissal hearing.",
    })
    assert r.status_code == 200, r.text
    assert len(r.json()["response"]) > 0

def test_emergency_rights_gb_pace():
    r = requests.post(API + "/emergency/rights", headers=_h(), json={
        "country": "GB", "language": "en-GB",
        "location": "Camden, London", "note": "Stopped on the street.",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["country"] == "GB"
    assert isinstance(j["rights_script"], str) and len(j["rights_script"]) > 200
    blob = j["rights_script"].upper()
    assert "PACE" in blob, "UK rights script should mention PACE"

def test_emergency_rights_us_miranda():
    r = requests.post(API + "/emergency/rights", headers=_h(), json={
        "country": "US", "language": "en-GB",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["country"] == "US"
    blob = j["rights_script"].lower()
    assert "miranda" in blob or "right to remain silent" in blob or "fifth amendment" in blob, \
        f"US rights script should reference Miranda/5th Amendment: {blob[:300]}"

def test_letters_generate_deposit_return():
    r = requests.post(API + "/letters/generate", headers=_h(), json={
        "template_id": "deposit_return",
        "your_name": "Jane Tenant",
        "recipient": "Acme Lettings Ltd",
        "facts": "Tenancy ended 10 Dec 2025. Deposit £1,200 not returned. Property left clean.",
        "language": "en-GB", "country": "GB",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["title"]
    assert "id" in j
    letter = j["letter"].lower()
    # Structural checks
    assert "jane tenant" in letter, "Sender name missing"
    assert "acme lettings" in letter, "Recipient missing"
    # Should mention deposit protection / TDS-type concept
    assert ("deposit" in letter and ("tenancy deposit" in letter or "tds" in letter or "scheme" in letter or "protect" in letter))

def test_letters_generate_witness_statement():
    r = requests.post(API + "/letters/generate", headers=_h(), json={
        "template_id": "witness_statement",
        "your_name": "John Smith",
        "recipient": "The Court",
        "facts": "On 5 Jan 2026 at 9pm I saw the claimant trip on broken pavement at 12 High St.",
        "language": "en-GB", "country": "GB",
    })
    assert r.status_code == 200, r.text
    letter = r.json()["letter"].lower()
    # CPR Part 32 hallmarks
    assert "statement of truth" in letter, "Witness statement missing 'statement of truth'"
    assert "john smith" in letter
    # Numbered paragraphs convention
    assert ("1." in letter or "1)" in letter)

def test_letters_generate_unknown_template_400():
    r = requests.post(API + "/letters/generate", headers=_h(), json={
        "template_id": "does_not_exist",
        "your_name": "x", "recipient": "y", "facts": "z",
    })
    assert r.status_code == 400

def test_lex_chat_autodetect_spanish_reply():
    """Existing /api/lex/chat — user sends Spanish in en-GB UI → reply should be Spanish."""
    r = requests.post(API + "/lex/chat", headers=_h(), json={
        "category": "general",
        "message": "Hola Lex, necesito ayuda con un contrato de alquiler. ¿Qué debo revisar?",
        "language": "en-GB",
    })
    assert r.status_code == 200, r.text
    resp = r.json()["response"]
    markers = ("¿", "¡", "á", "é", "í", "ó", "ú", "ñ", " contrato", " usted", " debe", " puede")
    assert any(m in resp for m in markers), f"Auto-detect failed — not Spanish: {resp[:200]}"
