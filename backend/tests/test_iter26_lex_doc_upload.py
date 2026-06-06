"""Iter 26 — POST /api/lex/upload + GET /api/lex/upload/{id} + doc_ids injection
into /api/lex/chat. Verifies:
  - Free tier: 1-page PDF (contract) returns 200 + doc_type=contract + remaining_today=0
  - Free tier daily quota (1/day) — 2nd upload returns 402
  - Free tier page cap (5 pages) — 6-page PDF returns 402
  - Unauthenticated POST -> 401/403
  - Cross-user GET -> 404
  - /lex/chat with doc_ids — assistant quotes the £950 rent figure
"""
import io
import os
import uuid
import requests
import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

FREE_EMAIL = "test@advocate.app"
FREE_PW = "Test12345!"


# ---------------- helpers ----------------
def make_tenancy_pdf(pages: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for p in range(pages):
        c.setFont("Helvetica", 12)
        y = 800
        lines = [
            "TENANCY AGREEMENT",
            "",
            "This agreement is made between the Landlord and the Tenant.",
            "The Tenant shall pay rent of £950 per month, payable in advance on the 1st.",
            "The deposit shall be £1,425 held by the DPS.",
            "Governing law: This tenancy agreement is governed by the laws of England.",
            "The Tenant shall not sub-let without written consent.",
            f"This is page {p+1} of {pages}.",
        ]
        for ln in lines:
            c.drawString(72, y, ln)
            y -= 20
        c.showPage()
    c.save()
    return buf.getvalue()


def login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    body = r.json()
    assert "access_token" in body, body
    return body["access_token"]


def reset_free_user_uploads():
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    u = db.users.find_one({"email": FREE_EMAIL})
    assert u, "free test user missing"
    db.lex_uploads.delete_many({"user_id": u["id"]})
    # Make sure tier is free (None==free is OK but explicit makes test deterministic)
    db.users.update_one({"id": u["id"]}, {"$unset": {"doc_pack_remaining": "", "tier": ""}})
    cli.close()


def signup_throwaway() -> tuple[str, str]:
    """Create a brand-new free user for cross-user tests."""
    email = f"test_iter26_{uuid.uuid4().hex[:8]}@advocate.app"
    pw = "Test12345!"
    r = requests.post(f"{BASE_URL}/api/auth/signup",
                      json={"email": email, "password": pw, "name": "Iter26 Bob"},
                      timeout=30)
    assert r.status_code in (200, 201), f"signup failed {r.status_code}: {r.text}"
    body = r.json()
    return email, body["access_token"]


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def free_token():
    reset_free_user_uploads()
    return login(FREE_EMAIL, FREE_PW)


@pytest.fixture(scope="module")
def free_headers(free_token):
    return {"Authorization": f"Bearer {free_token}"}


# ---------------- TC1: happy-path upload ----------------
def test_01_upload_contract_pdf_free_tier(free_headers):
    pdf = make_tenancy_pdf(pages=1)
    files = {"file": ("tenancy_agreement.pdf", pdf, "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/lex/upload",
                      headers=free_headers, files=files, timeout=60)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    body = r.json()
    assert "doc_id" in body
    assert body["pages"] == 1
    assert body["doc_type"] == "contract", body
    assert body["tier_used"] == "free"
    assert body["remaining_today"] == 0
    # Stash for later tests via env
    os.environ["ITER26_DOC_ID"] = body["doc_id"]


# ---------------- TC2: daily quota ----------------
def test_02_daily_quota_blocks_second_upload(free_headers):
    pdf = make_tenancy_pdf(pages=1)
    files = {"file": ("tenancy2.pdf", pdf, "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/lex/upload",
                      headers=free_headers, files=files, timeout=60)
    assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "Daily document quota reached" in detail, detail
    assert "1/day for free" in detail, detail


# ---------------- TC3: page cap ----------------
def test_03_page_cap_blocks_large_pdf():
    # reset so the page-cap check is the failure (not daily-quota)
    reset_free_user_uploads()
    tok = login(FREE_EMAIL, FREE_PW)
    h = {"Authorization": f"Bearer {tok}"}
    pdf = make_tenancy_pdf(pages=6)
    files = {"file": ("big.pdf", pdf, "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/lex/upload",
                      headers=h, files=files, timeout=60)
    assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "above the 5-page limit for the free tier" in detail, detail


# ---------------- TC4: unauthenticated ----------------
def test_04_upload_unauthenticated():
    pdf = make_tenancy_pdf(pages=1)
    files = {"file": ("nope.pdf", pdf, "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/lex/upload", files=files, timeout=30)
    assert r.status_code in (401, 403), f"{r.status_code}: {r.text}"


# ---------------- TC5: cross-user GET ----------------
def test_05_cross_user_get_404():
    # Re-upload as free user (after TC3 reset)
    tok_a = login(FREE_EMAIL, FREE_PW)
    h_a = {"Authorization": f"Bearer {tok_a}"}
    pdf = make_tenancy_pdf(pages=1)
    files = {"file": ("tenancy_a.pdf", pdf, "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/lex/upload",
                      headers=h_a, files=files, timeout=60)
    assert r.status_code == 200, r.text
    doc_id = r.json()["doc_id"]
    os.environ["ITER26_DOC_ID"] = doc_id  # refresh for TC6

    # owner can read
    r_owner = requests.get(f"{BASE_URL}/api/lex/upload/{doc_id}",
                           headers=h_a, timeout=30)
    assert r_owner.status_code == 200

    # other user cannot
    _, tok_b = signup_throwaway()
    h_b = {"Authorization": f"Bearer {tok_b}"}
    r_b = requests.get(f"{BASE_URL}/api/lex/upload/{doc_id}",
                       headers=h_b, timeout=30)
    assert r_b.status_code == 404, f"{r_b.status_code}: {r_b.text}"


# ---------------- TC6: doc injection into /lex/chat ----------------
def test_06_chat_uses_attached_doc_context():
    doc_id = os.environ.get("ITER26_DOC_ID")
    assert doc_id, "TC5 must have set ITER26_DOC_ID"
    tok = login(FREE_EMAIL, FREE_PW)
    h = {"Authorization": f"Bearer {tok}"}
    payload = {
        "message": "How much rent does the tenant pay in the attached document? Quote the exact figure.",
        "history": [],
        "doc_ids": [doc_id],
    }
    r = requests.post(f"{BASE_URL}/api/lex/chat",
                      headers=h, json=payload, timeout=120)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
    body = r.json()
    reply = (body.get("response") or body.get("reply") or body.get("message") or "").lower()
    assert "950" in reply, f"Reply did not quote rent figure £950. Reply: {reply[:600]}"


# ---------------- teardown ----------------
def teardown_module(_):
    reset_free_user_uploads()
