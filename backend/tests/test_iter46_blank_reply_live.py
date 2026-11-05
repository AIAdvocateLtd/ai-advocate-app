# Iter46: LIVE pre-deployment regression for blank-reply fix (Pro/DeepThink/Plus Lex), Stage1/2 fields,
# admin llm-spend, auth/security, tier gating, letters + document analysis. Uses LIVE AI — budget-capped.
import os, json, re, uuid, copy, time
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@aiadvocate.co.uk", "AdminLex2026!")
FREE = ("test@advocate.app", "Test12345!")
_mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
db = _mc[os.environ.get("DB_NAME", "ai_advocate_db")]
STATE = {"sessions": [], "users": []}
LEX_CALLS = {"n": 0}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


def H(t):
    return {"Authorization": f"Bearer {t}"}


def stream(tok, payload):
    LEX_CALLS["n"] += 1
    r = requests.post(f"{API}/lex/chat/stream", json=payload, headers=H(tok), stream=True, timeout=240)
    assert r.status_code == 200, r.text[:300]
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
    return events


@pytest.fixture(scope="module")
def admin_tok():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def free_tok():
    return login(*FREE)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for sid in STATE["sessions"]:
        db.conversations.delete_many({"session_id": sid})
    for uid in STATE["users"]:
        db.users.delete_one({"id": uid})
    print(f"\nLEX CALLS USED: {LEX_CALLS['n']}")


def clone_user(tier, verified=True):
    src = db.users.find_one({"email": FREE[0]})
    c = copy.deepcopy(src); c.pop("_id", None)
    c["id"] = str(uuid.uuid4())
    c["email"] = f"test_{tier}_{c['id'][:8]}@stage2-fictional-test.co.uk"
    c["tier"] = tier
    c["subscription_status"] = "active" if tier != "free" else c.get("subscription_status")
    c["email_verified"] = verified
    for k in ("stripe_customer_id", "stripe_subscription_id"):
        c.pop(k, None)
    db.users.insert_one(c)
    STATE["users"].append(c["id"])
    return c


# --- Auth & security ---
class TestAuth:
    def test_login_ok_and_wrong_pw(self):
        assert login(*FREE)
        r = requests.post(f"{API}/auth/login", json={"email": FREE[0], "password": "WrongPw999!"}, timeout=30)
        assert r.status_code == 401

    def test_protected_requires_token(self):
        assert requests.get(f"{API}/auth/me", timeout=30).status_code == 401
        assert requests.get(f"{API}/auth/me", headers=H("bad.token.x"), timeout=30).status_code == 401

    def test_unverified_gate(self):
        c = clone_user("free", verified=False)
        tok = login(c["email"], FREE[1])
        r = requests.get(f"{API}/lex/sessions", headers=H(tok), timeout=30)
        assert r.status_code == 403
        assert "email_not_verified" in r.text

    def test_bcrypt_format(self):
        u = db.users.find_one({"email": ADMIN[0]})
        assert (u.get("password_hash") or "").startswith("$2")


# --- Gating & admin ---
class TestGatingAdmin:
    def test_free_deep_think_402(self, free_tok):
        r = requests.post(f"{API}/lex/chat", json={"message": "hi", "deep_think": True}, headers=H(free_tok), timeout=30)
        assert r.status_code == 402
        r = requests.post(f"{API}/lex/chat/stream", json={"message": "hi", "deep_think": True}, headers=H(free_tok), timeout=30)
        assert r.status_code == 402

    def test_non_admin_403(self, free_tok):
        for p in ("/admin/llm-spend", "/admin/lex-lessons"):
            assert requests.get(f"{API}{p}", headers=H(free_tok), timeout=30).status_code == 403, p

    def test_admin_llm_spend(self, admin_tok):
        r = requests.get(f"{API}/admin/llm-spend", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("total_gbp", "calls", "by_model", "cost_basis", "lex_reply_health"):
            assert k in d, k
        assert set(d["lex_reply_health"]) >= {"replies", "blank", "cut_off"}
        print("lex_reply_health", d["lex_reply_health"], "cost_basis", d["cost_basis"])

    def test_admin_lessons(self, admin_tok):
        r = requests.get(f"{API}/admin/lex-lessons", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        rows = d if isinstance(d, list) else (d.get("lessons") or d.get("items") or [])
        print("lessons", len(rows), "needs_review", sum(1 for x in rows if x.get("needs_review")))
        assert len(rows) > 0


def _check_citations(text, cits):
    nums = {int(n) for n in re.findall(r"\[(\d{1,2})\]", text or "")}
    assert all(1 <= n <= len(cits or []) for n in nums), (nums, len(cits or []))


# --- Lex Pro / Deep Think / Plus live ---
class TestLexLive:
    def test_pro_chat_and_memory(self, admin_tok):
        t0 = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        LEX_CALLS["n"] += 1
        r = requests.post(f"{API}/lex/chat", headers=H(admin_tok), timeout=240, json={
            "message": "TEST_ My fictional landlord Mr Quill in Bristol has kept my £950 deposit for 6 weeks after I moved out. What can I do?"})
        assert r.status_code == 200, r.text[:300]
        d = r.json(); STATE["sessions"].append(d["session_id"])
        print("PRO model", d["model"], "research", d.get("research_status"), "juris", d.get("jurisdiction_check"), "len", len(d["response"]))
        print("PRO tail:", d["response"][-300:])
        assert d["response"].strip() and len(d["response"]) > 200
        assert d["model"] == "claude-sonnet-5-5"
        assert "research_status" in d and "jurisdiction_check" in d
        _check_citations(d["response"], d.get("citations"))
        # follow-up memory
        LEX_CALLS["n"] += 1
        r2 = requests.post(f"{API}/lex/chat", headers=H(admin_tok), timeout=240, json={
            "message": "Remind me: what was my landlord's name, which city, and how much was the deposit? Answer in one line.", "session_id": d["session_id"]})
        assert r2.status_code == 200
        t = r2.json()["response"]
        print("MEMORY:", t[:300])
        assert "Quill" in t and "950" in t
        rows = list(db.llm_usage.find({"ts": {"$gte": t0}, "feature": "lex_chat", "model_requested": "claude-sonnet-5-5"}, {"_id": 0}))
        print("usage rows", [(x.get("call_site"), x.get("measured"), x.get("finish_reason"), x.get("reasoning_tokens"), x.get("output_chars")) for x in rows])
        assert rows and all("finish_reason" in x and "reasoning_tokens" in x for x in rows)
        assert any(x.get("measured") is True for x in rows)

    def test_pro_stream(self, admin_tok):
        ev = stream(admin_tok, {"message": "TEST_ Can my fictional employer in Leeds deduct a till shortage from my wages?"})
        meta = next((e for e in ev if e.get("type") == "meta"), {})
        done = next((e for e in ev if e.get("type") == "done"), {})
        errs = [e for e in ev if e.get("type") == "error"]
        if meta.get("session_id"): STATE["sessions"].append(meta["session_id"])
        txt = done.get("full_text") or "".join(e.get("text", "") for e in ev if e.get("type") == "token")
        print("STREAM meta keys", list(meta), "research", meta.get("research_status"), "len", len(txt), "errs", errs)
        print("STREAM tail:", txt[-300:])
        assert not errs and txt.strip() and len(txt) > 200
        _check_citations(txt, meta.get("citations"))

    def test_deep_think_stream(self, admin_tok):
        ev = stream(admin_tok, {"message": "TEST_ Fictional: my Manchester landlord served a Section 21 without giving me the How to Rent guide or protecting my deposit. Is it valid?", "deep_think": True})
        meta = next((e for e in ev if e.get("type") == "meta"), {})
        done = next((e for e in ev if e.get("type") == "done"), {})
        errs = [e for e in ev if e.get("type") == "error"]
        if meta.get("session_id"): STATE["sessions"].append(meta["session_id"])
        txt = done.get("full_text") or ""
        print("DEEP len", len(txt), "errs", errs, "cut" , "cut short" in txt)
        print("DEEP tail:", txt[-300:])
        assert not errs and len(txt.strip()) > 200

    def test_plus_clone(self):
        c = clone_user("plus")
        tok = login(c["email"], FREE[1])
        LEX_CALLS["n"] += 1
        r = requests.post(f"{API}/lex/chat", headers=H(tok), timeout=240, json={"message": "TEST_ How long do I have to bring a small claim for an unpaid fictional invoice in England?"})
        assert r.status_code == 200, r.text[:300]
        d = r.json(); STATE["sessions"].append(d["session_id"])
        print("PLUS model", d["model"], "len", len(d["response"]), "tail:", d["response"][-200:])
        assert d["model"] == "gpt-5.2" and len(d["response"].strip()) > 100


# --- Letters & document analysis (1 call each) ---
class TestLettersDocs:
    def test_letter_generate(self, admin_tok):
        r = requests.post(f"{API}/letters/generate", headers=H(admin_tok), timeout=180, json={
            "template_id": "deposit_return", "your_name": "TEST_ Alex Fictional", "recipient": "Mr Quill (fictional landlord)",
            "facts": "Tenancy ended 1 Oct; £950 deposit not returned; no deductions explained."})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        txt = d.get("content") or d.get("letter") or d.get("text") or json.dumps(d)
        print("LETTER keys", list(d), "len", len(txt))
        assert len(txt) > 200
        if d.get("id"):
            db.legal_files.delete_one({"id": d["id"]})

    def test_document_analyze(self, admin_tok):
        content = (b"FICTIONAL PARKING CHARGE NOTICE\nTEST_ ParkCo Ltd (fictional)\nVehicle: AB12 CDE\nDate: 3 Jan 2026\n"
                   b"Amount due: 100 GBP, reduced to 60 GBP if paid within 14 days.\nAppeal within 28 days to ParkCo.\n")
        import io
        from reportlab.pdfgen import canvas
        buf = io.BytesIO(); cv = canvas.Canvas(buf)
        for i, ln in enumerate(content.decode().splitlines()):
            cv.drawString(60, 780 - i * 18, ln)
        cv.save()
        r = requests.post(f"{API}/document/analyze", headers=H(admin_tok), timeout=180,
                          files={"file": ("notice.pdf", buf.getvalue(), "application/pdf")})
        print("DOC status", r.status_code, r.text[:600])
        assert r.status_code == 200
        d = r.json()
        assert d
        if d.get("id"):
            print("doc id", d["id"])
