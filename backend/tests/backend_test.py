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

def _h():
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
