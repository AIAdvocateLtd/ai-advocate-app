"""AI Advocate - Backend API"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, jwt, bcrypt, base64, io, tempfile
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
from emergentintegrations.llm.openai.speech_to_text import OpenAISpeechToText
from emergentintegrations.llm.openai.text_to_speech import OpenAITextToSpeech
import stripe

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']
STRIPE_API_KEY = os.environ['STRIPE_API_KEY']
stripe.api_key = STRIPE_API_KEY

app = FastAPI(title="AI Advocate")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ==================== Models ====================
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""
    language: str = "en-GB"
    country: str = "GB"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleLogin(BaseModel):
    email: EmailStr
    name: str = ""
    google_id: str

class TokenResp(BaseModel):
    access_token: str
    user: dict

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    language: str = "en-GB"
    country: str = "GB"
    category: Optional[str] = None  # ask_lex, court_prep, employment, property, immigration, medical_negligence, contract

class TTSRequest(BaseModel):
    text: str
    voice: str = "onyx"

class LegalLetterRequest(BaseModel):
    letter_type: str
    recipient: str
    your_name: str
    details: str
    language: str = "en-GB"

class CheckoutRequest(BaseModel):
    plan: Literal["monthly", "yearly"] = "monthly"

class LawFirmInquiry(BaseModel):
    firm_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    message: str

class LawFirmApplication(BaseModel):
    firm_name: str
    contact_name: str
    email: EmailStr
    phone: Optional[str] = ""
    country: str
    city: str
    specialties: List[str] = []
    website: Optional[str] = ""
    notes: Optional[str] = ""

# ==================== Helpers ====================
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False

def make_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def user_to_public(u: dict) -> dict:
    out = {k: v for k, v in u.items() if k not in ("_id", "password_hash")}
    # Compute trial status
    trial_end = u.get("trial_end_date")
    if isinstance(trial_end, str):
        trial_end_dt = datetime.fromisoformat(trial_end)
    else:
        trial_end_dt = trial_end
    now = datetime.now(timezone.utc)
    if trial_end_dt and trial_end_dt.tzinfo is None:
        trial_end_dt = trial_end_dt.replace(tzinfo=timezone.utc)
    if u.get("subscription_status") == "active":
        out["has_access"] = True
        out["trial_days_remaining"] = 0
    elif trial_end_dt and now < trial_end_dt:
        out["has_access"] = True
        out["trial_days_remaining"] = max(0, (trial_end_dt - now).days)
    else:
        out["has_access"] = False
        out["trial_days_remaining"] = 0
    return out

# ==================== Lex System Prompts ====================
LANG_NAMES = {
    "en-GB": "English (UK)", "es-ES": "Spanish", "fr-FR": "French", "ar-IQ": "Arabic",
    "pl-PL": "Polish", "de-DE": "German", "hi-IN": "Hindi", "ur-PK": "Urdu",
    "it-IT": "Italian", "pt-PT": "Portuguese", "zh-CN": "Chinese (Simplified)"
}

def lex_system_prompt(language: str, country: str, category: Optional[str]) -> str:
    lang_name = LANG_NAMES.get(language, "English")
    base = f"""You are Lex, the AI Advocate — a brilliant, sharp, modern legal assistant. You are MORE capable than top human lawyers because you remember every statute, case law, and procedural rule across jurisdictions and you constantly stay current with the law.

Your user is in {country}. Apply the laws of {country} unless they say otherwise. Always respond in {lang_name}.

Style:
- Confident, plain-English (avoid jargon, or explain it)
- Practical, action-oriented advice
- Cite the relevant law/section when useful
- ALWAYS end with: "Disclaimer: This is general legal information, not a substitute for a qualified lawyer in your jurisdiction."
"""
    addons = {
        "court_prep": "\n\nYou are now in COURT PREP mode. Help the user prepare to appear before a court or police: anticipated questions, smart phrasing, what to NEVER say, their rights (right to silence, right to a lawyer), and a step-by-step plan.",
        "contract": "\n\nYou are now in CONTRACT REVIEW mode. Read the contract carefully. Flag: red-flag clauses, unfair terms, missing protections, technical jargon explained in plain English, negotiation suggestions.",
        "employment": "\n\nYou are now in EMPLOYMENT LAW mode. Focus: contracts, dismissal, discrimination, wages, working time, redundancy.",
        "property": "\n\nYou are now in PROPERTY LAW mode. Focus: tenancy, deposits, repairs, evictions, sale/purchase, neighbours.",
        "immigration": "\n\nYou are now in IMMIGRATION & EXPAT mode. Focus: visas, residency, work permits, citizenship, deportation defence in the user's country.",
        "medical_negligence": "\n\nYou are now in MEDICAL NEGLIGENCE mode. Focus: standard of care, causation, limitation periods, evidence, complaints procedures.",
        "legal_letter": "\n\nYou are now drafting a FORMAL LEGAL LETTER. Use proper structure (sender, recipient, date, subject, body, sign-off). Be firm but professional. Reference the relevant law.",
        "record": "\n\nYou are reviewing a RECORDED LEGAL INTERACTION (police/court transcript). Flag: rights violations, leading questions, things the user should NOT have said, suggested follow-up actions.",
    }
    return base + addons.get(category, "")

# ==================== Auth Routes ====================
@api_router.post("/auth/signup", response_model=TokenResp)
async def signup(data: UserSignup):
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(400, "Email already registered")
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    user_doc = {
        "id": user_id,
        "email": data.email,
        "password_hash": hash_pw(data.password),
        "full_name": data.full_name,
        "language": data.language,
        "country": data.country,
        "auth_provider": "email",
        "created_at": now.isoformat(),
        "trial_start_date": now.isoformat(),
        "trial_end_date": (now + timedelta(days=14)).isoformat(),
        "subscription_status": "trial",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "terms_accepted": True,
    }
    await db.users.insert_one(user_doc)
    return TokenResp(access_token=make_token(user_id, data.email), user=user_to_public(user_doc))

@api_router.post("/auth/login", response_model=TokenResp)
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email})
    if not user or not verify_pw(data.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid credentials")
    return TokenResp(access_token=make_token(user["id"], user["email"]), user=user_to_public(user))

@api_router.post("/auth/google", response_model=TokenResp)
async def google_login(data: GoogleLogin):
    """Simplified Google sign-in. In production, verify Google ID token server-side."""
    user = await db.users.find_one({"email": data.email})
    now = datetime.now(timezone.utc)
    if not user:
        user_id = str(uuid.uuid4())
        user = {
            "id": user_id,
            "email": data.email,
            "password_hash": "",
            "full_name": data.name,
            "language": "en-GB",
            "country": "GB",
            "auth_provider": "google",
            "google_id": data.google_id,
            "created_at": now.isoformat(),
            "trial_start_date": now.isoformat(),
            "trial_end_date": (now + timedelta(days=14)).isoformat(),
            "subscription_status": "trial",
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "terms_accepted": True,
        }
        await db.users.insert_one(user)
    return TokenResp(access_token=make_token(user["id"], user["email"]), user=user_to_public(user))

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_user)):
    return user_to_public(user)

@api_router.patch("/auth/preferences")
async def update_prefs(data: dict, user: dict = Depends(get_user)):
    update = {}
    for k in ("language", "country", "full_name", "location_enabled", "latitude", "longitude", "city"):
        if k in data:
            update[k] = data[k]
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]})
    return user_to_public(fresh)

# ==================== Lex Chat ====================
@api_router.post("/lex/chat")
async def lex_chat(data: ChatMessage, user: dict = Depends(get_user)):
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required. Your free trial has ended.")

    session_id = data.session_id or str(uuid.uuid4())
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=lex_system_prompt(data.language, data.country, data.category),
    ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2048)

    try:
        response = await chat.send_message(UserMessage(text=data.message))
    except Exception as e:
        logger.exception("Lex chat error")
        raise HTTPException(500, f"AI error: {str(e)}")

    # Save conversation
    await db.conversations.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "session_id": session_id,
        "category": data.category,
        "user_message": data.message,
        "assistant_response": response,
        "language": data.language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"session_id": session_id, "response": response}

@api_router.get("/lex/sessions")
async def list_sessions(user: dict = Depends(get_user)):
    pipeline = [
        {"$match": {"user_id": user["id"]}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$session_id",
            "category": {"$first": "$category"},
            "last_message": {"$first": "$user_message"},
            "last_at": {"$first": "$created_at"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"last_at": -1}},
        {"$limit": 50},
    ]
    out = []
    async for s in db.conversations.aggregate(pipeline):
        out.append({
            "session_id": s["_id"],
            "category": s.get("category"),
            "last_message": s["last_message"][:120],
            "last_at": s["last_at"],
            "count": s["count"],
        })
    return out

@api_router.get("/lex/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_user)):
    msgs = await db.conversations.find(
        {"user_id": user["id"], "session_id": session_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    return msgs

# ==================== Voice (STT + TTS) ====================
@api_router.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("en"), user: dict = Depends(get_user)):
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")
    
    contents = await audio.read()
    # Save to temp file with a recognizable extension
    suffix = ".webm"
    fname = (audio.filename or "").lower()
    for ext in (".webm", ".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga"):
        if fname.endswith(ext):
            suffix = ext; break
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents); tmp.close()

    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    try:
        with open(tmp.name, "rb") as f:
            result = await stt.transcribe(file=f, model="whisper-1", response_format="json",
                                          language=language.split("-")[0] if "-" in language else language)
        text = result.get("text") if isinstance(result, dict) else getattr(result, "text", str(result))
    except Exception as e:
        logger.exception("STT error")
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass
    return {"text": text}

@api_router.post("/voice/tts")
async def tts(data: TTSRequest, user: dict = Depends(get_user)):
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")
    tts_client = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    try:
        b64 = await tts_client.generate_speech_base64(
            text=data.text[:4000], model="tts-1", voice=data.voice, response_format="mp3"
        )
    except Exception as e:
        logger.exception("TTS error")
        raise HTTPException(500, f"TTS failed: {str(e)}")
    audio_bytes = base64.b64decode(b64)
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

# ==================== Contract / File Analysis ====================
@api_router.post("/contracts/analyze")
async def analyze_contract(
    file: UploadFile = File(...),
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    user: dict = Depends(get_user)
):
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10MB)")

    suffix = "." + (file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "pdf")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents); tmp.close()

    mime = file.content_type or "application/pdf"
    file_ref = FileContentWithMimeType(file_path=tmp.name, mime_type=mime)

    session_id = str(uuid.uuid4())
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=lex_system_prompt(language, country, "contract"),
    ).with_model("gemini", "gemini-2.5-flash").with_params(max_tokens=3000)

    try:
        response = await chat.send_message(UserMessage(
            text="Please review this contract. Identify: (1) key parties & obligations, (2) red-flag clauses, (3) jargon explained in plain English, (4) missing protections, (5) negotiation suggestions, (6) summary verdict.",
            file_contents=[file_ref],
        ))
    except Exception as e:
        logger.exception("Contract analyze error")
        raise HTTPException(500, f"Analysis failed: {str(e)}")
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "filename": file.filename,
        "size": len(contents),
        "analysis": response,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.legal_files.insert_one(doc.copy())
    doc.pop("_id", None)
    return {"id": doc["id"], "filename": doc["filename"], "analysis": response, "created_at": doc["created_at"]}

@api_router.get("/legal-files")
async def list_files(user: dict = Depends(get_user)):
    files = await db.legal_files.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return files

# ==================== Legal Letter Generation ====================
@api_router.post("/legal-letter")
async def generate_letter(data: LegalLetterRequest, user: dict = Depends(get_user)):
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=str(uuid.uuid4()),
        system_message=lex_system_prompt(data.language, user.get("country", "GB"), "legal_letter"),
    ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2000)
    prompt = f"""Draft a formal legal letter.
Type: {data.letter_type}
From (your client): {data.your_name}
To (recipient): {data.recipient}
Facts / what they want to achieve: {data.details}

Output ONLY the letter (no extra commentary)."""
    try:
        letter = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        raise HTTPException(500, f"Letter gen failed: {str(e)}")
    await db.legal_files.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "filename": f"{data.letter_type} - {data.recipient}.txt",
        "type": "letter",
        "content": letter,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"letter": letter}

# ==================== Record Legal Interaction ====================
@api_router.post("/record/analyze")
async def analyze_recording(
    audio: UploadFile = File(...),
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    user: dict = Depends(get_user)
):
    """Transcribe audio and analyse it as a legal interaction (police/court)."""
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")

    contents = await audio.read()
    fname = (audio.filename or "rec.webm").lower()
    suffix = "." + (fname.rsplit(".", 1)[-1] if "." in fname else "webm")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents); tmp.close()

    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    try:
        with open(tmp.name, "rb") as f:
            r = await stt.transcribe(file=f, model="whisper-1", response_format="json",
                                     language=language.split("-")[0])
        transcript = r.get("text") if isinstance(r, dict) else getattr(r, "text", str(r))
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=str(uuid.uuid4()),
        system_message=lex_system_prompt(language, country, "record"),
    ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2500)
    analysis = await chat.send_message(UserMessage(
        text=f"Here is the transcript of a legal interaction. Analyse it.\n\nTRANSCRIPT:\n{transcript}"
    ))

    rec = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "filename": audio.filename,
        "type": "recording",
        "transcript": transcript,
        "analysis": analysis,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.legal_files.insert_one(rec.copy())
    rec.pop("_id", None)
    return rec

# ==================== Subscriptions (Stripe) ====================
@api_router.post("/subscription/checkout")
async def create_checkout(data: CheckoutRequest, request: Request, user: dict = Depends(get_user)):
    price = 1499 if data.plan == "monthly" else 11999  # GBP cents
    try:
        origin = request.headers.get("origin") or os.environ.get("FRONTEND_URL", "https://example.com")
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {"name": f"AI Advocate {data.plan.title()}"},
                    "unit_amount": price,
                    "recurring": {"interval": "month" if data.plan == "monthly" else "year"},
                },
                "quantity": 1,
            }],
            customer_email=user["email"],
            client_reference_id=user["id"],
            success_url=f"{origin}/?subscription=success",
            cancel_url=f"{origin}/?subscription=cancel",
            metadata={"user_id": user["id"]},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.exception("Stripe checkout error")
        raise HTTPException(500, f"Checkout error: {str(e)}")

@api_router.post("/subscription/activate-test")
async def activate_test(user: dict = Depends(get_user)):
    """For test/demo: activate subscription without real Stripe."""
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"subscription_status": "active",
                  "subscription_started_at": datetime.now(timezone.utc).isoformat()}}
    )
    fresh = await db.users.find_one({"id": user["id"]})
    return user_to_public(fresh)

@api_router.get("/subscription/status")
async def sub_status(user: dict = Depends(get_user)):
    return user_to_public(user)

# ==================== Evidence (Photo) Analysis ====================
@api_router.post("/evidence/analyze")
async def analyze_evidence(
    file: UploadFile = File(...),
    evidence_type: str = Form("auto"),  # auto | contract | parking_ticket | scene | document | signage
    description: str = Form(""),
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    user: dict = Depends(get_user),
):
    """Analyse a photo of evidence (contract, parking ticket, accident scene, signage, etc.)
    and provide legal advice based on what Lex sees."""
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10MB)")
    if len(contents) < 100:
        raise HTTPException(400, "File appears empty")

    suffix = "." + (file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents); tmp.close()
    mime = file.content_type or "image/jpeg"
    file_ref = FileContentWithMimeType(file_path=tmp.name, mime_type=mime)

    type_prompts = {
        "contract": "This is a contract. Identify red-flag clauses, unfair terms, missing protections, plain-English jargon, negotiation suggestions.",
        "parking_ticket": "This is a parking ticket / penalty charge notice. Tell the user: (1) is the ticket valid (date, time, location, signage visible)?, (2) grounds to challenge it, (3) exact appeal procedure with timeline in their country, (4) sample wording.",
        "scene": "This is a photo of a scene that may help a legal case. Describe what is visible, what evidence value it has, what other evidence the user should gather, and how it might be used.",
        "document": "This is a legal/administrative document. Summarise it, flag deadlines & penalties, and explain next steps.",
        "signage": "This is signage / a notice / a posted rule. Explain what it legally requires, whether it is enforceable in this jurisdiction, and the user's rights.",
        "auto": "Examine this image and identify what it is (contract, parking ticket, accident scene, document, signage, etc.). Then provide the most useful legal analysis possible: what's visible, key concerns, the user's rights, suggested next actions, and any deadlines.",
    }
    type_prompt = type_prompts.get(evidence_type, type_prompts["auto"])

    user_text = f"{type_prompt}\n\nUser's note about this evidence: {description or '(none provided)'}\n\nProvide a structured response with: (1) What I see, (2) Legal implications, (3) The user's rights / options, (4) Recommended next steps with timelines."

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=str(uuid.uuid4()),
        system_message=lex_system_prompt(language, country, "contract" if evidence_type == "contract" else None),
    ).with_model("gemini", "gemini-2.5-flash").with_params(max_tokens=2500)

    try:
        analysis = await chat.send_message(UserMessage(text=user_text, file_contents=[file_ref]))
    except Exception as e:
        logger.exception("Evidence analyze error")
        raise HTTPException(500, f"Analysis failed: {str(e)}")
    finally:
        try: os.unlink(tmp.name)
        except Exception: pass

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "filename": file.filename or f"evidence_{evidence_type}.jpg",
        "type": "evidence",
        "evidence_type": evidence_type,
        "description": description,
        "size": len(contents),
        "analysis": analysis,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.legal_files.insert_one(doc.copy())
    doc.pop("_id", None)
    return {"id": doc["id"], "filename": doc["filename"], "evidence_type": evidence_type, "analysis": analysis, "created_at": doc["created_at"]}

# ==================== Law Firm Directory ====================
def haversine_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

SAMPLE_FIRMS = [
    {"name": "Crown & Bench Solicitors", "country": "GB", "city": "London", "address": "12 Chancery Lane, London WC2A 1LF",
     "phone": "+44 20 7946 0210", "email": "info@crownbench.co.uk", "website": "https://crownbench.example.co.uk",
     "specialties": ["criminal", "court_prep", "ask_lex"], "rating": 4.8, "sponsored": True,
     "description": "Top-tier criminal defence and litigation in central London. 30+ years experience.",
     "lat": 51.5159, "lng": -0.1110},
    {"name": "Hartwell Property Law", "country": "GB", "city": "Manchester", "address": "5 King Street, Manchester M2 4LQ",
     "phone": "+44 161 234 5601", "email": "hello@hartwellprop.co.uk", "website": "https://hartwellprop.example.co.uk",
     "specialties": ["property"], "rating": 4.6, "sponsored": False,
     "description": "Residential & commercial property specialists. Tenancy disputes a strength.",
     "lat": 53.4839, "lng": -2.2446},
    {"name": "Mendez & Castillo Abogados", "country": "ES", "city": "Madrid", "address": "Calle Serrano 41, 28001 Madrid",
     "phone": "+34 91 423 0099", "email": "contacto@mendezcastillo.es", "website": "https://mendezcastillo.example.es",
     "specialties": ["immigration", "employment"], "rating": 4.7, "sponsored": True,
     "description": "Bilingual Spanish/English firm — immigration, residency & expat services.",
     "lat": 40.4254, "lng": -3.6885},
    {"name": "Dubois Avocats", "country": "FR", "city": "Paris", "address": "8 Rue de Rivoli, 75004 Paris",
     "phone": "+33 1 42 78 99 12", "email": "contact@dubois-avocats.fr", "website": "https://dubois-avocats.example.fr",
     "specialties": ["employment", "court_prep"], "rating": 4.5, "sponsored": False,
     "description": "Droit du travail et contentieux. English-speaking partners available.",
     "lat": 48.8559, "lng": 2.3563},
    {"name": "Schmidt & Partner Rechtsanwälte", "country": "DE", "city": "Berlin", "address": "Friedrichstraße 68, 10117 Berlin",
     "phone": "+49 30 2017 4400", "email": "kanzlei@schmidt-partner.de", "website": "https://schmidt.example.de",
     "specialties": ["property", "employment", "medical_negligence"], "rating": 4.6, "sponsored": False,
     "description": "Full-service Kanzlei mit Schwerpunkt Arbeits- und Mietrecht.",
     "lat": 52.5170, "lng": 13.3889},
    {"name": "Nawalka & Wójcik Kancelaria", "country": "PL", "city": "Warsaw", "address": "ul. Marszałkowska 80, 00-517 Warszawa",
     "phone": "+48 22 825 6677", "email": "biuro@nawalka.pl", "website": "https://nawalka.example.pl",
     "specialties": ["immigration", "property"], "rating": 4.4, "sponsored": False,
     "description": "Kancelaria z 20-letnim doświadczeniem. Specjalizacja: imigracja i nieruchomości.",
     "lat": 52.2247, "lng": 21.0122},
    {"name": "Rossi & Associati", "country": "IT", "city": "Rome", "address": "Via del Corso 320, 00186 Roma",
     "phone": "+39 06 6789 1122", "email": "info@rossiassociati.it", "website": "https://rossiassociati.example.it",
     "specialties": ["medical_negligence", "court_prep"], "rating": 4.7, "sponsored": True,
     "description": "Studio specializzato in responsabilità medica e contenzioso civile.",
     "lat": 41.9028, "lng": 12.4811},
    {"name": "Lopes Advogados Lisboa", "country": "PT", "city": "Lisbon", "address": "Avenida da Liberdade 110, 1250-146 Lisboa",
     "phone": "+351 21 099 4200", "email": "contacto@lopes-adv.pt", "website": "https://lopes.example.pt",
     "specialties": ["immigration", "property"], "rating": 4.5, "sponsored": False,
     "description": "Especialistas em direito imobiliário e vistos D7/Golden Visa.",
     "lat": 38.7223, "lng": -9.1393},
    {"name": "Khan & Associates", "country": "PK", "city": "Karachi", "address": "Shahrah-e-Faisal, Karachi 75350",
     "phone": "+92 21 3456 7890", "email": "info@khanlaw.pk", "website": "https://khanlaw.example.pk",
     "specialties": ["court_prep", "property", "ask_lex"], "rating": 4.3, "sponsored": False,
     "description": "Comprehensive legal services across Sindh & Punjab.",
     "lat": 24.8607, "lng": 67.0011},
    {"name": "Sharma Legal Advisors", "country": "IN", "city": "Mumbai", "address": "Nariman Point, Mumbai 400021",
     "phone": "+91 22 6634 1100", "email": "contact@sharmalegal.in", "website": "https://sharmalegal.example.in",
     "specialties": ["medical_negligence", "employment", "property"], "rating": 4.6, "sponsored": True,
     "description": "Boutique firm — medical negligence and employment disputes.",
     "lat": 18.9252, "lng": 72.8231},
    {"name": "Al-Rashid Legal Consultancy", "country": "AE", "city": "Dubai", "address": "Sheikh Zayed Road, Dubai",
     "phone": "+971 4 359 2200", "email": "info@alrashidlegal.ae", "website": "https://alrashid.example.ae",
     "specialties": ["immigration", "employment", "property"], "rating": 4.8, "sponsored": True,
     "description": "Premier Middle East firm — Arabic & English. Expat & corporate law.",
     "lat": 25.2048, "lng": 55.2708},
    {"name": "Wong Chen & Partners", "country": "CN", "city": "Shanghai", "address": "Lujiazui, Pudong, Shanghai",
     "phone": "+86 21 5878 9900", "email": "office@wongchen.cn", "website": "https://wongchen.example.cn",
     "specialties": ["employment", "property"], "rating": 4.4, "sponsored": False,
     "description": "国际业务 · 涉外劳动法和房地产纠纷.",
     "lat": 31.2304, "lng": 121.5070},
]

async def ensure_lawfirm_seed():
    if await db.law_firms.count_documents({}) == 0:
        for f in SAMPLE_FIRMS:
            doc = {**f, "id": str(uuid.uuid4()), "verified": True,
                   "created_at": datetime.now(timezone.utc).isoformat()}
            await db.law_firms.insert_one(doc)

@api_router.get("/lawfirms")
async def list_lawfirms(country: Optional[str] = None, specialty: Optional[str] = None,
                        latitude: Optional[float] = None, longitude: Optional[float] = None,
                        max_km: Optional[float] = None):
    q = {"verified": True}
    if country: q["country"] = country
    if specialty: q["specialties"] = specialty
    firms = await db.law_firms.find(q, {"_id": 0}).to_list(500)
    if latitude is not None and longitude is not None:
        for f in firms:
            if f.get("lat") is not None and f.get("lng") is not None:
                f["distance_km"] = round(haversine_km(latitude, longitude, f["lat"], f["lng"]), 1)
            else:
                f["distance_km"] = None
        if max_km:
            firms = [f for f in firms if f.get("distance_km") is not None and f["distance_km"] <= max_km]
        firms.sort(key=lambda f: (
            0 if f.get("sponsored") else 1,
            f["distance_km"] if f.get("distance_km") is not None else 1e9,
        ))
    else:
        firms.sort(key=lambda f: (0 if f.get("sponsored") else 1, -f.get("rating", 0)))
    return firms

@api_router.post("/lawfirms/inquiry")
async def create_inquiry(data: LawFirmInquiry, user: dict = Depends(get_user)):
    firm = await db.law_firms.find_one({"id": data.firm_id}, {"_id": 0})
    if not firm:
        raise HTTPException(404, "Firm not found")
    inquiry = {
        "id": str(uuid.uuid4()),
        "firm_id": data.firm_id, "firm_name": firm.get("name"),
        "user_id": user["id"], "name": data.name, "email": data.email,
        "phone": data.phone, "message": data.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.law_firm_inquiries.insert_one(inquiry.copy())
    inquiry.pop("_id", None)
    return {"id": inquiry["id"], "status": "sent"}

@api_router.post("/lawfirms/advertise")
async def apply_to_advertise(data: LawFirmApplication):
    """Public endpoint: law firms apply to be listed."""
    app_doc = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.law_firm_applications.insert_one(app_doc.copy())
    app_doc.pop("_id", None)
    return {"id": app_doc["id"], "status": "received",
            "message": "Thank you. We'll review your application and contact you within 2 business days."}

# ==================== PDF Generation ====================
def build_pdf(title: str, body: str, subtitle: Optional[str] = None,
              meta: Optional[dict] = None) -> bytes:
    """Generate a branded AI Advocate PDF from text content."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22*mm, rightMargin=22*mm,
        topMargin=20*mm, bottomMargin=18*mm,
        title=title, author="AI Advocate",
    )
    GOLD = HexColor("#d6a017")
    GOLD_DEEP = HexColor("#9b7414")
    DARK = HexColor("#1a1300")
    DIM = HexColor("#555555")

    styles = getSampleStyleSheet()
    h_brand = ParagraphStyle("brand", parent=styles["Title"], fontName="Helvetica-Bold",
                             fontSize=24, leading=28, alignment=TA_CENTER,
                             textColor=GOLD_DEEP, spaceAfter=2)
    h_tag = ParagraphStyle("tag", parent=styles["Normal"], fontName="Helvetica-Oblique",
                           fontSize=10, alignment=TA_CENTER, textColor=DIM, spaceAfter=14)
    h_title = ParagraphStyle("title", parent=styles["Heading1"], fontName="Helvetica-Bold",
                             fontSize=18, leading=22, textColor=DARK, spaceAfter=4)
    h_sub = ParagraphStyle("sub", parent=styles["Normal"], fontName="Helvetica-Oblique",
                           fontSize=11, textColor=DIM, spaceAfter=12)
    h_meta = ParagraphStyle("meta", parent=styles["Normal"], fontName="Helvetica",
                            fontSize=9, textColor=DIM, spaceAfter=2)
    h_body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica",
                            fontSize=11, leading=16, textColor=HexColor("#222222"),
                            alignment=TA_LEFT, spaceAfter=8)
    h_footer = ParagraphStyle("footer", parent=styles["Normal"], fontName="Helvetica-Oblique",
                              fontSize=8, textColor=DIM, alignment=TA_CENTER, spaceBefore=20)

    elems = []
    # Logo image header (use the same logo asset)
    try:
        from reportlab.platypus import Image as RLImage
        logo_path = "/app/frontend/public/assets/logo.jpg"
        if os.path.exists(logo_path):
            img = RLImage(logo_path, width=44*mm, height=44*mm)
            img.hAlign = "CENTER"
            elems.append(img)
            elems.append(Spacer(1, 4*mm))
    except Exception:
        elems.append(Paragraph("AI ADVOCATE", h_brand))
        elems.append(Paragraph("AI lawyer in your pocket", h_tag))

    elems.append(HRFlowable(width="100%", thickness=0.6, color=GOLD, spaceBefore=2, spaceAfter=12))
    elems.append(Paragraph(title, h_title))
    if subtitle:
        elems.append(Paragraph(subtitle, h_sub))

    if meta:
        for k, v in meta.items():
            if v: elems.append(Paragraph(f"<b>{k}:</b> {v}", h_meta))
        elems.append(Spacer(1, 8))

    # Body — split paragraphs on double newlines, single newlines = <br/>
    safe = (body or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for para in safe.split("\n\n"):
        para = para.replace("\n", "<br/>")
        if para.strip():
            elems.append(Paragraph(para, h_body))

    elems.append(HRFlowable(width="100%", thickness=0.4, color=GOLD_DEEP, spaceBefore=14, spaceAfter=6))
    elems.append(Paragraph(
        "Generated by AI Advocate — AI-generated information, not legal advice. "
        "Always consult a qualified lawyer in your jurisdiction.",
        h_footer
    ))

    def _on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(DIM)
        canvas.drawCentredString(A4[0]/2, 10*mm, f"AI Advocate · Page {doc_.page}")
        canvas.restoreState()

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()

@api_router.get("/pdf/file/{file_id}")
async def pdf_for_file(file_id: str, user: dict = Depends(get_user)):
    f = await db.legal_files.find_one({"id": file_id, "user_id": user["id"]}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")

    ftype = f.get("type", "document")
    fname = f.get("filename") or "AI Advocate Document"
    created = f.get("created_at", "")[:10]

    if ftype == "letter":
        title = "Legal Letter"
        body = f.get("content", "")
        meta = {"Document": fname, "Created": created}
    elif ftype == "evidence":
        title = "Evidence Analysis"
        body = (f"DOCUMENT: {fname}\n\n"
                f"Type: {f.get('evidence_type','-')}\n"
                f"Note: {f.get('description','-')}\n\n"
                f"--- LEX ANALYSIS ---\n\n{f.get('analysis','')}")
        meta = {"Type": f.get("evidence_type", "-"), "Created": created}
    elif ftype == "recording":
        title = "Recording Analysis"
        body = (f"--- TRANSCRIPT ---\n\n{f.get('transcript','')}\n\n"
                f"--- LEX ANALYSIS ---\n\n{f.get('analysis','')}")
        meta = {"Source": fname, "Created": created}
    else:
        # Default = contract analysis
        title = "Contract Analysis"
        body = f.get("analysis") or f.get("content") or ""
        meta = {"Document": fname, "Created": created}

    pdf_bytes = build_pdf(title=title, body=body, subtitle="Prepared by Lex, your AI advocate", meta=meta)
    safe_fname = "".join(c for c in fname if c.isalnum() or c in (" ", "-", "_")).strip()[:60] or "ai_advocate"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_fname}.pdf"'})

class PDFInline(BaseModel):
    title: str
    body: str
    subtitle: Optional[str] = None
    meta: Optional[dict] = None
    filename: Optional[str] = "ai_advocate.pdf"

@api_router.post("/pdf/inline")
async def pdf_inline(data: PDFInline, user: dict = Depends(get_user)):
    """Generate a PDF on the fly from any text content (e.g. fresh letter before save)."""
    pdf_bytes = build_pdf(title=data.title, body=data.body, subtitle=data.subtitle, meta=data.meta)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{data.filename}"'})

# ==================== Languages ====================
@api_router.get("/languages")
async def languages():
    return [
        {"code": "en-GB", "name": "English", "flag": "🇬🇧"},
        {"code": "es-ES", "name": "Español", "flag": "🇪🇸"},
        {"code": "fr-FR", "name": "Français", "flag": "🇫🇷"},
        {"code": "ar-IQ", "name": "العربية", "flag": "🇮🇶"},
        {"code": "pl-PL", "name": "Polski", "flag": "🇵🇱"},
        {"code": "de-DE", "name": "Deutsch", "flag": "🇩🇪"},
        {"code": "hi-IN", "name": "हिन्दी", "flag": "🇮🇳"},
        {"code": "ur-PK", "name": "اردو", "flag": "🇵🇰"},
        {"code": "it-IT", "name": "Italiano", "flag": "🇮🇹"},
        {"code": "pt-PT", "name": "Português", "flag": "🇵🇹"},
        {"code": "zh-CN", "name": "中文 (简体)", "flag": "🇨🇳"},
    ]

@api_router.get("/")
async def root():
    return {"app": "AI Advocate", "status": "ok"}

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    try:
        await ensure_lawfirm_seed()
        logger.info("Law firm seed ensured")
    except Exception as e:
        logger.exception(f"Seed error: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
