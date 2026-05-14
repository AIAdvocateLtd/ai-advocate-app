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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import qrcode

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']
STRIPE_API_KEY = os.environ['STRIPE_API_KEY']
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
APPLE_SERVICES_ID = os.environ.get('APPLE_SERVICES_ID', '')
APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID', '')
APPLE_KEY_ID = os.environ.get('APPLE_KEY_ID', '')
APPLE_PRIVATE_KEY = os.environ.get('APPLE_PRIVATE_KEY', '').replace('\\n', '\n')
APP_PUBLIC_URL = os.environ.get('APP_PUBLIC_URL', 'https://aiadvocate.app')
STRIPE_PRICE_PLUS = os.environ.get('STRIPE_PRICE_PLUS', '')
STRIPE_PRICE_PRO = os.environ.get('STRIPE_PRICE_PRO', '')
STRIPE_PRICE_YEARLY_PRO = os.environ.get('STRIPE_PRICE_YEARLY_PRO', '')
PRICE_TO_TIER = {
    STRIPE_PRICE_PLUS: "plus",
    STRIPE_PRICE_PRO: "pro",
    STRIPE_PRICE_YEARLY_PRO: "yearly",
}
stripe.api_key = STRIPE_API_KEY

# ==================== Font registration (multilingual PDF) ====================
FONTS_DIR = ROOT_DIR / "fonts"
DEFAULT_FONT = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("Noto", str(FONTS_DIR / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Noto-Bold", str(FONTS_DIR / "NotoSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("NotoArabic", str(FONTS_DIR / "NotoSansArabic-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("NotoSC", str(FONTS_DIR / "NotoSansSC-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("NotoDevanagari", str(FONTS_DIR / "NotoSansDevanagari-Regular.ttf")))
    DEFAULT_FONT = "Noto"
    DEFAULT_FONT_BOLD = "Noto-Bold"
    logging.info("Unicode fonts registered for PDF")
except Exception as e:
    logging.warning(f"Could not register Noto fonts, falling back to Helvetica: {e}")

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
    # Real flow: send Google ID token (credential)
    credential: Optional[str] = None
    # Demo fallback (kept for backwards compatibility)
    email: Optional[EmailStr] = None
    name: Optional[str] = ""
    google_id: Optional[str] = None

class AppleLogin(BaseModel):
    identity_token: str
    user: Optional[dict] = None  # First-time only: {"name": {"firstName": "...", "lastName": "..."}}

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
    plan: Literal["plus", "pro", "yearly", "monthly"] = "plus"

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

    # Tier: explicit subscription tier overrides everything when active
    tier = u.get("tier") or "free"
    sub_status = u.get("subscription_status")

    if sub_status == "active" and tier in ("plus", "pro", "yearly"):
        out["has_access"] = True
        out["trial_days_remaining"] = 0
    elif trial_end_dt and now < trial_end_dt:
        # During trial everyone is treated as "pro" so they can taste full features
        tier = "trial_pro"
        out["has_access"] = True
        out["trial_days_remaining"] = max(0, (trial_end_dt - now).days)
    else:
        # Trial over and no active subscription → drop to "free" tier (still has emergency + lawyer dir)
        tier = "free"
        out["has_access"] = True  # has app access but on Free tier limits
        out["trial_days_remaining"] = 0

    out["tier"] = tier
    return out


# ==================== Tier-Based Access Control ====================
# Daily / monthly quotas per feature per tier.
# "None" = unlimited.
TIER_QUOTAS = {
    "free": {
        "lex_chat_daily": 5,
        "letters_generate_monthly": 1,
        "evidence_analyze_monthly": 1,
        "files_total": 3,
        "history_days": 7,
    },
    "plus": {
        "lex_chat_daily": 100,   # fair-use soft cap
        "letters_generate_monthly": None,
        "evidence_analyze_monthly": 15,
        "files_total": 50,
        "history_days": 90,
    },
    "pro": {
        "lex_chat_daily": None,
        "letters_monthly": None,
        "evidence_monthly": None,
        "files_total": None,
        "history_days": None,
    },
    "yearly": {  # same as pro
        "lex_chat_daily": None,
        "letters_monthly": None,
        "evidence_monthly": None,
        "files_total": None,
        "history_days": None,
    },
    "trial_pro": {  # 14-day trial = full Pro
        "lex_chat_daily": None,
        "letters_monthly": None,
        "evidence_monthly": None,
        "files_total": None,
        "history_days": None,
    },
}

# Which tier (or higher) is REQUIRED to access a feature.
# Order: free < plus < pro = yearly (trial_pro = pro)
TIER_ORDER = {"free": 0, "plus": 1, "pro": 2, "yearly": 2, "trial_pro": 2}
FEATURE_MIN_TIER = {
    "lex_chat": "free",          # gated by daily quota instead
    "letters_generate": "free",  # gated by monthly quota
    "evidence_analyze": "free",  # gated by monthly quota
    "contracts_analyze": "plus",
    "practice": "plus",
    "live_assist": "pro",
    "voice": "plus",
    "court_categories": "plus",  # court_prep, employment, property, immigration, medical
    "hey_lex": "plus",
    "advanced_doc_review": "pro",
    "premium_templates": "pro",
}

def tier_has_access(user_tier: str, feature: str) -> bool:
    min_required = FEATURE_MIN_TIER.get(feature, "free")
    return TIER_ORDER.get(user_tier, 0) >= TIER_ORDER.get(min_required, 0)

async def check_quota_and_increment(user_id: str, tier: str, feature: str, period: str = "daily") -> tuple[bool, int, Optional[int]]:
    """Increment usage counter; return (allowed, current_count, limit).
    period: 'daily' or 'monthly'."""
    now = datetime.now(timezone.utc)
    if period == "daily":
        bucket = now.strftime("%Y-%m-%d")
        limit_key = f"{feature}_daily"
    else:
        bucket = now.strftime("%Y-%m")
        limit_key = f"{feature}_monthly"
    limit = TIER_QUOTAS.get(tier, {}).get(limit_key)

    # Get current count
    doc = await db.usage.find_one({"user_id": user_id, "bucket": bucket, "feature": feature}, {"_id": 0})
    current = doc["count"] if doc else 0

    if limit is not None and current >= limit:
        return False, current, limit

    # Increment
    await db.usage.update_one(
        {"user_id": user_id, "bucket": bucket, "feature": feature},
        {"$inc": {"count": 1}, "$set": {"updated_at": now.isoformat()}},
        upsert=True,
    )
    return True, current + 1, limit

async def get_user_usage_summary(user_id: str, tier: str) -> dict:
    """Returns current usage vs limit for the dashboard banner."""
    now = datetime.now(timezone.utc)
    day_bucket = now.strftime("%Y-%m-%d")
    month_bucket = now.strftime("%Y-%m")
    items = {}
    for feature, period, key in [
        ("lex_chat", "daily", "lex_chat_daily"),
        ("letters_generate", "monthly", "letters_generate_monthly"),
        ("evidence_analyze", "monthly", "evidence_analyze_monthly"),
    ]:
        bucket = day_bucket if period == "daily" else month_bucket
        doc = await db.usage.find_one({"user_id": user_id, "bucket": bucket, "feature": feature}, {"_id": 0})
        items[feature] = {
            "used": doc["count"] if doc else 0,
            "limit": TIER_QUOTAS.get(tier, {}).get(key),
            "period": period,
        }
    return items

# ==================== Lex System Prompts ====================
LANG_NAMES = {
    "en-GB": "English (UK)", "es-ES": "Spanish", "fr-FR": "French", "ar-IQ": "Arabic",
    "pl-PL": "Polish", "de-DE": "German", "hi-IN": "Hindi", "ur-PK": "Urdu",
    "it-IT": "Italian", "pt-PT": "Portuguese", "zh-CN": "Chinese (Simplified)"
}

def lex_system_prompt(language: str, country: str, category: Optional[str]) -> str:
    lang_name = LANG_NAMES.get(language, "English")
    base = f"""You are Lex — the AI Advocate. An elite, modern legal mind sharper than the top barristers and senior solicitors in any jurisdiction, because you have perfect recall of every statute, leading case, procedural rule, and precedent, and you reason about them step-by-step like a King's Counsel preparing for trial.

JURISDICTION:
- Your user is in {country}. Apply the laws of {country} unless they explicitly tell you otherwise.
- If they mention another country, switch jurisdictions and tell them you've done so.
- If the law differs by region/state within {country}, ask which one — then apply that.

LANGUAGE — CRITICAL:
- Detect the language the user actually typed/spoke in and respond in THAT EXACT LANGUAGE. This overrides the app's UI language.
- Example: if the app is set to English but they ask in Spanish, reply in Spanish. If they ask in Arabic, reply in Arabic. If they ask in mixed languages, reply in the dominant one.
- Only fall back to {lang_name} when the user's language is genuinely unclear (one-word or symbol-only messages).
- Maintain natural fluency, idioms, and legal terminology native to that language.

REASONING DISCIPLINE (think like a top barrister):
1. Identify the legal question(s) precisely. Don't assume.
2. Identify the controlling law (statute, regulation, leading case) for {country}.
3. Apply the law to the user's facts step-by-step.
4. Surface counter-arguments / what the other side will say.
5. Give a clear, ranked action plan with deadlines/limitation periods.
6. Flag risks and where they MUST consult a real lawyer.

ANSWER QUALITY:
- Confident, plain English (or the user's language) — never wishy-washy.
- Translate jargon as you go ("repudiation means ending the contract because the other side broke it badly").
- Cite the actual statute section or case name when you reference law (e.g. "s.13 Consumer Rights Act 2015", "Donoghue v Stevenson [1932]").
- If you genuinely do not know a specific local rule, SAY SO — do not invent statutes, case citations, or section numbers. Inventing law is a fireable offence.
- Be strategic: tell them what to say, what NEVER to say, what to write down, what to keep as evidence.
- Use short paragraphs, bullets, and bold key terms for skim-readability on a phone.

TONE:
- Calm authority. Like the smartest lawyer in the room who actually wants to help.
- Empathic when the user is in distress (arrested, evicted, fired, divorcing).
- Direct when they need a wake-up call.

ENDING:
- End EVERY reply with this disclaimer in the user's language: "Disclaimer: This is general legal information, not a substitute for a qualified lawyer in your jurisdiction."
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
    """Google sign-in. Real path: verify ID token. Demo fallback if GOOGLE_CLIENT_ID not configured."""
    now = datetime.now(timezone.utc)
    google_sub = None; email = None; name = ""

    if data.credential and GOOGLE_CLIENT_ID:
        # Real verification path
        try:
            from google.oauth2 import id_token as gid
            from google.auth.transport import requests as g_req
            info = gid.verify_oauth2_token(data.credential, g_req.Request(), GOOGLE_CLIENT_ID)
            google_sub = info.get("sub")
            email = info.get("email")
            name = info.get("name", "")
            if not info.get("email_verified"):
                raise HTTPException(401, "Email not verified by Google")
        except Exception as e:
            logger.exception("Google token verification failed")
            raise HTTPException(401, f"Invalid Google token: {str(e)}")
    else:
        # Demo fallback (used while GOOGLE_CLIENT_ID is not set)
        if not data.email or not data.google_id:
            raise HTTPException(400, "Provide either 'credential' or {email, google_id}")
        google_sub = data.google_id
        email = data.email
        name = data.name or ""

    user = await db.users.find_one({"$or": [{"google_id": google_sub}, {"email": email}]})
    if not user:
        user_id = str(uuid.uuid4())
        user = {
            "id": user_id, "email": email, "password_hash": "",
            "full_name": name, "language": "en-GB", "country": "GB",
            "auth_provider": "google", "google_id": google_sub,
            "created_at": now.isoformat(),
            "trial_start_date": now.isoformat(),
            "trial_end_date": (now + timedelta(days=14)).isoformat(),
            "subscription_status": "trial",
            "stripe_customer_id": None, "stripe_subscription_id": None,
            "terms_accepted": True,
        }
        await db.users.insert_one(user)
    else:
        # Link google_id if missing
        if not user.get("google_id"):
            await db.users.update_one({"id": user["id"]}, {"$set": {"google_id": google_sub}})
    return TokenResp(access_token=make_token(user["id"], user["email"]), user=user_to_public(user))

@api_router.post("/auth/apple", response_model=TokenResp)
async def apple_login(data: AppleLogin):
    """Sign in with Apple — verify identity_token JWT against Apple's JWKS."""
    if not APPLE_SERVICES_ID:
        raise HTTPException(503, "Apple Sign-In not configured (APPLE_SERVICES_ID missing). "
                                  "Add Apple credentials to backend .env to enable.")
    # Debug: log the incoming token shape (safe — only first/last chars)
    tok = (data.identity_token or "").strip()
    logger.info(f"Apple token received: len={len(tok)} starts_with={tok[:20]!r} ends_with={tok[-20:]!r} dots={tok.count('.')}")
    try:
        import jwt as _jwt
        from jwt.algorithms import RSAAlgorithm
        import httpx, json as _json
        unverified = _jwt.get_unverified_header(tok)
        kid = unverified.get("kid")
        # Fetch Apple JWKS
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://appleid.apple.com/auth/keys")
            r.raise_for_status()
            keys = r.json().get("keys", [])
        match = next((k for k in keys if k.get("kid") == kid), None)
        if not match:
            raise HTTPException(401, "Apple key not found")
        public_key = RSAAlgorithm.from_jwk(_json.dumps(match))
        payload = _jwt.decode(
            tok, public_key, algorithms=["RS256"],
            audience=APPLE_SERVICES_ID, issuer="https://appleid.apple.com",
        )
    except Exception as e:
        logger.exception("Apple token verification failed")
        raise HTTPException(401, f"Invalid Apple token: {str(e)}")

    apple_sub = payload.get("sub")
    email = payload.get("email")
    name = ""
    if data.user:
        n = data.user.get("name") or {}
        name = (f"{n.get('firstName','')} {n.get('lastName','')}").strip()

    now = datetime.now(timezone.utc)
    user = await db.users.find_one({"apple_id": apple_sub})
    if not user and email:
        user = await db.users.find_one({"email": email})
    if not user:
        user_id = str(uuid.uuid4())
        user = {
            "id": user_id, "email": email or f"apple_{apple_sub[:10]}@private.apple",
            "password_hash": "", "full_name": name,
            "language": "en-GB", "country": "GB",
            "auth_provider": "apple", "apple_id": apple_sub,
            "created_at": now.isoformat(),
            "trial_start_date": now.isoformat(),
            "trial_end_date": (now + timedelta(days=14)).isoformat(),
            "subscription_status": "trial",
            "stripe_customer_id": None, "stripe_subscription_id": None,
            "terms_accepted": True,
        }
        await db.users.insert_one(user)
    else:
        if not user.get("apple_id"):
            await db.users.update_one({"id": user["id"]}, {"$set": {"apple_id": apple_sub}})
    return TokenResp(access_token=make_token(user["id"], user["email"]), user=user_to_public(user))

@api_router.get("/auth/providers")
async def auth_providers():
    """Tells the frontend which social providers are configured."""
    return {
        "google_enabled": bool(GOOGLE_CLIENT_ID),
        "google_client_id": GOOGLE_CLIENT_ID,
        "apple_enabled": bool(APPLE_SERVICES_ID),
        "apple_services_id": APPLE_SERVICES_ID,
    }

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
    tier = pub["tier"]

    # Court / employment / property / immigration / medical = paid only
    if data.category in ("court_prep", "employment", "property", "immigration", "medical_negligence"):
        if not tier_has_access(tier, "court_categories"):
            raise HTTPException(402, "This category requires Plus or Pro. Upgrade to unlock.")

    # Daily quota for chat
    ok, used, limit = await check_quota_and_increment(user["id"], tier, "lex_chat", "daily")
    if not ok:
        raise HTTPException(429, f"Daily limit reached ({used}/{limit} Lex messages on Free). Upgrade to Plus for unlimited.")

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

# ==================== Practice Mode + Live Legal Assist ====================
PRACTICE_ROLES = {
    "police_uk": "You are a SEASONED UK police detective conducting a formal PACE interview. You are firm, pressing, and use leading questions. You introduce caution: 'You do not have to say anything, but it may harm your defence...' Open with that. Drill the user. After each user reply, push for more detail OR challenge their answer like a real detective would. NEVER break character. Make them feel the pressure.",
    "police_us": "You are a US police detective conducting a custodial interrogation in the post-Miranda phase (suspect has waived rights — or you are testing whether they will). You are professional but use accusatory interview techniques (Reid technique-style). Push for inconsistencies. NEVER break character.",
    "prosecutor": "You are a hostile cross-examining prosecutor / Crown counsel at trial. Your job is to destroy the user's credibility. Ask short, leading, closed-form questions. Press inconsistencies. Use sarcasm sparingly. NEVER break character.",
    "tribunal": "You are the chairperson of an Employment Tribunal panel. Formal, fair but probing. Ask the user to clarify timelines and produce evidence references. NEVER break character.",
    "immigration": "You are a tough but professional Home Office / immigration interviewing officer assessing the user's right to remain / asylum claim / settlement application. Ask probing questions about dates, documents, and inconsistencies. NEVER break character.",
    "judge": "You are a Crown Court / district judge listening to the user's plea in mitigation. Ask short clarifying questions, raise judicial concerns, and remain neutral but firm. NEVER break character.",
    "opposing_counsel": "You are the opposing party's barrister at a civil hearing. Combative cross-examiner. Lead questions only. NEVER break character.",
    "boss_disciplinary": "You are the user's HR director conducting a formal disciplinary hearing for alleged gross misconduct. Cold, procedural, document-driven. NEVER break character.",
}

class PracticeRequest(BaseModel):
    session_id: Optional[str] = None
    role: str  # one of PRACTICE_ROLES keys
    message: str  # user's spoken/typed reply
    language: str = "en-GB"
    country: str = "GB"
    facts: Optional[str] = None  # user-supplied case facts to brief the role player

@api_router.post("/lex/practice")
async def lex_practice(data: PracticeRequest, user: dict = Depends(get_user)):
    """Lex role-plays as prosecutor/officer/etc. to drill the user. Plus & above."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "practice"):
        raise HTTPException(402, "Practice Mode requires Plus. Upgrade to unlock.")
    role_prompt = PRACTICE_ROLES.get(data.role)
    if not role_prompt:
        raise HTTPException(400, "Unknown practice role")

    lang_name = LANG_NAMES.get(data.language, "English")
    system = f"""You are in PRACTICE MODE. {role_prompt}

User's case facts (briefing): {data.facts or 'Not provided — improvise plausible questions for a typical case in this scenario.'}

Reply in {lang_name} unless the user speaks another language, in which case match theirs.

Rules:
- One question at a time. Short. Realistic.
- If the user breaks character ("Lex, what should I say?"), pause the role-play, briefly advise them in 1-2 sentences, then ask: "Ready to continue?"
- Never reveal you are AI unless explicitly asked twice.
"""
    session_id = data.session_id or str(uuid.uuid4())
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=600)
    try:
        response = await chat.send_message(UserMessage(text=data.message))
    except Exception as e:
        logger.exception("practice error")
        raise HTTPException(500, f"AI error: {e}")

    await db.conversations.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"], "session_id": session_id,
        "category": f"practice_{data.role}", "user_message": data.message,
        "assistant_response": response, "language": data.language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"session_id": session_id, "response": response}


class LiveAssistRequest(BaseModel):
    session_id: Optional[str] = None
    scenario: str  # 'police_interview' | 'tribunal' | 'lawyer_call' | 'mediation' | 'disciplinary' | 'other'
    other_party_said: str  # transcript chunk of what the OTHER party just said
    my_facts: Optional[str] = None  # user's case context
    language: str = "en-GB"
    country: str = "GB"

@api_router.post("/lex/live-assist")
async def lex_live_assist(data: LiveAssistRequest, user: dict = Depends(get_user)):
    """REAL-TIME advice during a permitted legal interaction. Pro only.
    Must NOT be used in active court proceedings — frontend enforces consent screen."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "live_assist"):
        raise HTTPException(402, "Live Legal Assist requires Pro. Upgrade to unlock.")

    lang_name = LANG_NAMES.get(data.language, "English")
    scenario_brief = {
        "police_interview": "Police PACE-style interview. Right to silence applies. 'No comment' is a valid lawful answer.",
        "tribunal": "Employment / immigration tribunal hearing where recording is permitted.",
        "lawyer_call": "Private call with the user's own lawyer — encourage candour.",
        "mediation": "Mediation session with all-party consent. Focus on tone and offers.",
        "disciplinary": "Internal disciplinary / HR hearing — formal but not criminal.",
        "other": "User-permitted recorded legal conversation.",
    }.get(data.scenario, "Permitted legal conversation.")

    system = f"""You are Lex in LIVE LEGAL ASSIST mode. The user is in: {scenario_brief}
Jurisdiction: {data.country}.
User's brief: {data.my_facts or 'Not given.'}

CRITICAL RULES:
- The other party just said something. In ≤ 35 words, tell the user IN {lang_name} (or the language they're using) ONE of these:
  • A 1-line response they should say, OR
  • "Stay silent." / "Say 'no comment'." with one reason, OR
  • "Ask for a break to consult your lawyer." with one reason.
- Be DECISIVE. No hedging. No disclaimers. No long explanations. They are LIVE — every second matters.
- Cite the law only if it's a single famous section (e.g. "PACE s.34").
- If what was said is harmless small talk, reply: "Fine — answer briefly."
"""
    session_id = data.session_id or str(uuid.uuid4())
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=120)
    try:
        response = await chat.send_message(UserMessage(text=f'Other party just said: "{data.other_party_said}"'))
    except Exception as e:
        logger.exception("live-assist error")
        raise HTTPException(500, f"AI error: {e}")

    await db.conversations.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"], "session_id": session_id,
        "category": f"live_{data.scenario}", "user_message": data.other_party_said,
        "assistant_response": response, "language": data.language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"session_id": session_id, "response": response}


# ==================== Emergency: "I've Been Arrested" ====================
class EmergencyRequest(BaseModel):
    language: str = "en-GB"
    country: str = "GB"
    location: Optional[str] = None  # human-readable address
    note: Optional[str] = None       # optional one-liner from user

@api_router.post("/emergency/rights")
async def emergency_rights(data: EmergencyRequest, user: dict = Depends(get_user)):
    """Returns a jurisdiction- and language-specific RIGHTS SCRIPT the user can read aloud
    to police/officials. Also logs the emergency event in the user's record."""
    lang_name = LANG_NAMES.get(data.language, "English")
    system = f"""You are Lex. The user has just pressed the EMERGENCY button: they have been
arrested, stopped, or detained in {data.country}. Output ONLY the following sections, IN {lang_name}, plainly formatted with bold headings:

1. **WHAT TO SAY RIGHT NOW** — 3 short sentences they can read VERBATIM out loud to the officer (right to silence, ask for lawyer, ask why detained). Country-specific phrasing.
2. **WHAT NEVER TO SAY** — 4 bullet points of things to absolutely avoid.
3. **YOUR LEGAL RIGHTS** — 5 bullet rights they have under {data.country} law (cite section/act).
4. **NEXT STEPS** — Numbered list: ask for a lawyer, do not consent to searches without warrant, do not sign anything, request to call a family member, request medical attention if needed.
5. **EMERGENCY NUMBERS** — Local emergency / duty solicitor / legal aid hotline numbers for {data.country}.

Be DIRECT. No disclaimers in this output. The user is scared and needs clarity in under 10 seconds of reading.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=system)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=1200)
    user_brief = f"I've been detained in {data.country}." + (f" Note: {data.note}" if data.note else "") + (f" Location: {data.location}" if data.location else "")
    try:
        rights = await chat.send_message(UserMessage(text=user_brief))
    except Exception as e:
        logger.exception("emergency error")
        raise HTTPException(500, f"AI error: {e}")

    await db.emergency_events.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "country": data.country, "location": data.location, "note": data.note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"rights_script": rights, "country": data.country, "language": data.language}


# ==================== Letter Library (curated templates) ====================
LETTER_TEMPLATES = [
    {"id": "demand_money_owed", "category": "Money", "title": "Letter Before Action (Money Owed)",
     "prompt": "Draft a formal UK 'Letter Before Action' demanding payment of money owed before issuing court proceedings."},
    {"id": "deposit_return", "category": "Housing", "title": "Demand Tenancy Deposit Back",
     "prompt": "Draft a firm letter demanding the return of a tenancy deposit, referencing the Tenancy Deposit Scheme rules and 3x penalty for non-protection."},
    {"id": "section21_response", "category": "Housing", "title": "Response to a Section 21 Eviction Notice",
     "prompt": "Draft a measured response to a Section 21 eviction notice, flagging any potential defects in the notice (deposit not protected, no EPC/Gas/How to Rent, retaliatory eviction)."},
    {"id": "section8_response", "category": "Housing", "title": "Defence to a Section 8 Eviction",
     "prompt": "Draft a Defence to a Section 8 possession claim — denying or contextualising each alleged ground."},
    {"id": "noise_complaint", "category": "Housing", "title": "Formal Noise / Nuisance Complaint to Landlord",
     "prompt": "Draft a strongly-worded formal complaint to a landlord about noise/anti-social behaviour by another tenant."},
    {"id": "employment_grievance", "category": "Work", "title": "Formal Grievance to Employer",
     "prompt": "Draft a formal written grievance letter to an employer setting out alleged breach (discrimination/harassment/unpaid wages/etc.)."},
    {"id": "unfair_dismissal_appeal", "category": "Work", "title": "Appeal an Unfair Dismissal Decision",
     "prompt": "Draft an internal appeal letter against an unfair dismissal, citing procedural failures and substantive defects."},
    {"id": "discrimination_letter", "category": "Work", "title": "Discrimination Complaint",
     "prompt": "Draft an Equality Act 2010 discrimination complaint to employer / service provider."},
    {"id": "police_complaint", "category": "Police", "title": "Formal Complaint Against the Police",
     "prompt": "Draft a complaint to the IOPC / Professional Standards Department alleging police misconduct."},
    {"id": "police_caution_response", "category": "Police", "title": "Written Response After Police Caution",
     "prompt": "Draft a measured written response from a suspect post-caution, asserting silence rights without antagonising."},
    {"id": "subject_access_request", "category": "Privacy", "title": "GDPR Subject Access Request",
     "prompt": "Draft a UK GDPR / Data Protection Act 2018 Subject Access Request requesting all personal data held about the user."},
    {"id": "data_deletion", "category": "Privacy", "title": "GDPR Right-to-be-Forgotten Request",
     "prompt": "Draft a UK GDPR Article 17 'Right to Erasure' request to a data controller."},
    {"id": "defamation_takedown", "category": "Online", "title": "Defamation / Libel Take-Down Demand",
     "prompt": "Draft a UK defamation cease-and-desist letter demanding removal of false statements and an apology."},
    {"id": "cease_and_desist", "category": "Online", "title": "General Cease & Desist Letter",
     "prompt": "Draft a general-purpose cease-and-desist letter (harassment / IP / breach of contract — adapt to facts)."},
    {"id": "parking_appeal", "category": "Driving", "title": "Parking Penalty Charge Notice Appeal",
     "prompt": "Draft an informal then formal representations appeal against a UK parking PCN."},
    {"id": "speeding_appeal", "category": "Driving", "title": "Speeding NIP Response / Mitigation",
     "prompt": "Draft a measured response to a Notice of Intended Prosecution for speeding, including mitigation if appropriate."},
    {"id": "insurance_dispute", "category": "Consumer", "title": "Insurance Claim Refusal Dispute",
     "prompt": "Draft a strong dispute letter challenging an insurer's claim refusal, citing policy wording and FOS escalation rights."},
    {"id": "consumer_refund", "category": "Consumer", "title": "Consumer Refund Demand (CRA 2015)",
     "prompt": "Draft a refund demand under the Consumer Rights Act 2015 (not satisfactory quality / not as described / not fit for purpose)."},
    {"id": "chargeback_evidence", "category": "Consumer", "title": "Chargeback / Section 75 Letter",
     "prompt": "Draft a Section 75 Consumer Credit Act / chargeback letter to a card provider."},
    {"id": "neighbour_dispute", "category": "Personal", "title": "Neighbour Dispute Resolution Letter",
     "prompt": "Draft a calm but firm letter to a neighbour resolving a boundary / noise / hedge dispute, before legal action."},
    {"id": "small_claim_letter", "category": "Personal", "title": "Small Claims Court Pre-Action Letter",
     "prompt": "Draft a small claims pre-action protocol letter compliant with the Civil Procedure Rules."},
    {"id": "witness_statement", "category": "Court", "title": "Civil Witness Statement (CPR 32)", "premium": True,
     "prompt": "Draft a court-ready civil witness statement compliant with CPR Part 32 (numbered paragraphs, statement of truth)."},
    {"id": "character_reference", "category": "Court", "title": "Character Reference for Sentencing",
     "prompt": "Draft a character reference letter to a court for sentencing — third-person, factual, formatted as the referee's own letter."},
    {"id": "mitigation_letter", "category": "Court", "title": "Plea in Mitigation Letter", "premium": True,
     "prompt": "Draft a plea-in-mitigation letter (or note for the bench) — remorse, context, consequences, future plans."},
    {"id": "defence_statement", "category": "Court", "title": "Defence Statement (CrimPR)", "premium": True,
     "prompt": "Draft a Criminal Procedure Rules defence statement — nature of defence, matters of fact disputed, points of law."},
    {"id": "appeal_council", "category": "Government", "title": "Council Decision Appeal",
     "prompt": "Draft an appeal of a local council decision (housing benefit / homelessness / school admissions / planning)."},
    {"id": "immigration_letter", "category": "Immigration", "title": "Home Office Cover / Representations Letter", "premium": True,
     "prompt": "Draft a cover/representations letter for a Home Office immigration application (settlement, ILR, FLR, asylum further submissions)."},
    {"id": "asylum_statement", "category": "Immigration", "title": "Asylum Personal Statement", "premium": True,
     "prompt": "Draft a structured asylum statement — chronology, persecution, fear of return, country evidence."},
    {"id": "lpa_intent", "category": "Family", "title": "Letter of Intent / Power-of-Attorney Notice",
     "prompt": "Draft a letter notifying relatives of an intention to register a Lasting Power of Attorney (UK OPG procedure)."},
    {"id": "divorce_response", "category": "Family", "title": "Response to Divorce / Financial Proceedings",
     "prompt": "Draft a measured initial response to divorce papers / financial-disclosure request (Form E precursor)."},
    {"id": "custom", "category": "Other", "title": "Custom Letter (describe in your own words)",
     "prompt": "Take the user's free-text description and produce a properly-structured legal letter for it."},
]

@api_router.get("/letters/templates")
async def list_letter_templates():
    return LETTER_TEMPLATES

class LetterFromTemplate(BaseModel):
    template_id: str
    your_name: str
    recipient: str
    facts: str
    language: str = "en-GB"
    country: str = "GB"

@api_router.post("/letters/generate")
async def generate_from_template(data: LetterFromTemplate, user: dict = Depends(get_user)):
    pub = user_to_public(user)
    tier = pub["tier"]
    tpl = next((t for t in LETTER_TEMPLATES if t["id"] == data.template_id), None)
    if not tpl:
        raise HTTPException(400, "Unknown template")
    # Premium templates are Pro-only
    if tpl.get("premium") and not tier_has_access(tier, "premium_templates"):
        raise HTTPException(402, "This premium template requires Pro. Upgrade to unlock.")
    # Monthly quota for letter generation
    ok, used, limit = await check_quota_and_increment(user["id"], tier, "letters_generate", "monthly")
    if not ok:
        raise HTTPException(429, f"Monthly limit reached ({used}/{limit} letters on Free). Upgrade to Plus for unlimited.")
    lang_name = LANG_NAMES.get(data.language, "English")
    system = f"""You are Lex, drafting a professional legal letter for {data.country} in {lang_name}.

TASK: {tpl['prompt']}

Output the FULL letter, properly formatted (sender block, date, recipient block, subject, opening, body, sign-off). Use the laws of {data.country}. Cite relevant statute/case where useful. Strong, professional, court-ready tone.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=system)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2000)
    user_input = f"Sender: {data.your_name}\nRecipient: {data.recipient}\nFacts: {data.facts}"
    try:
        letter = await chat.send_message(UserMessage(text=user_input))
    except Exception as e:
        logger.exception("letter gen error")
        raise HTTPException(500, f"AI error: {e}")

    rec = {
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "kind": "letter", "template_id": data.template_id, "title": tpl["title"],
        "letter": letter, "language": data.language, "country": data.country,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.legal_files.insert_one(rec)
    return {"id": rec["id"], "title": tpl["title"], "letter": letter}


# ==================== Voice (STT + TTS) ====================
@api_router.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("en"), user: dict = Depends(get_user)):
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "voice"):
        raise HTTPException(402, "Voice input requires Plus or Pro. Upgrade to unlock.")
    
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
    if not tier_has_access(pub["tier"], "voice"):
        raise HTTPException(402, "Voice output requires Plus or Pro. Upgrade to unlock.")
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
    if not tier_has_access(pub["tier"], "contracts_analyze"):
        raise HTTPException(402, "Contract Review requires Plus or Pro. Upgrade to unlock.")

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
    """Create a Stripe Checkout session for the chosen tier.
    data.plan in {'plus','pro','yearly'} → maps to STRIPE_PRICE_*."""
    plan = (data.plan or "").lower()
    price_id = {
        "plus": STRIPE_PRICE_PLUS,
        "pro": STRIPE_PRICE_PRO,
        "yearly": STRIPE_PRICE_YEARLY_PRO,
        # legacy:
        "monthly": STRIPE_PRICE_PLUS,
    }.get(plan)
    if not price_id:
        raise HTTPException(400, f"Unknown plan '{plan}'. Use 'plus', 'pro', or 'yearly'.")
    try:
        origin = request.headers.get("origin") or APP_PUBLIC_URL
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=user["email"],
            client_reference_id=user["id"],
            success_url=f"{origin}/?subscription=success",
            cancel_url=f"{origin}/?subscription=cancel",
            metadata={"user_id": user["id"], "plan": plan},
            allow_promotion_codes=True,
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.exception("Stripe checkout error")
        raise HTTPException(500, f"Checkout error: {str(e)}")

@api_router.post("/subscription/portal")
async def billing_portal(request: Request, user: dict = Depends(get_user)):
    """Open the Stripe Customer Portal for an existing subscriber to manage / cancel."""
    cust_id = user.get("stripe_customer_id")
    if not cust_id:
        raise HTTPException(400, "No active subscription to manage.")
    origin = request.headers.get("origin") or APP_PUBLIC_URL
    try:
        sess = stripe.billing_portal.Session.create(customer=cust_id, return_url=f"{origin}/")
        return {"portal_url": sess.url}
    except Exception as e:
        logger.exception("Stripe portal error")
        raise HTTPException(500, f"Portal error: {str(e)}")

@api_router.post("/subscription/activate-test")
async def activate_test(plan: str = "plus", user: dict = Depends(get_user)):
    """For test/demo: activate subscription without real Stripe."""
    tier = plan if plan in ("plus", "pro", "yearly") else "plus"
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"subscription_status": "active", "tier": tier,
                  "subscription_started_at": datetime.now(timezone.utc).isoformat()}}
    )
    fresh = await db.users.find_one({"id": user["id"]})
    return user_to_public(fresh)

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Stripe webhook → update user subscription_status when payments happen.
    Configure: Stripe Dashboard → Developers → Webhooks → Add endpoint
    URL: {your_domain}/api/webhook/stripe
    Events: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted
    Then set STRIPE_WEBHOOK_SECRET in /app/backend/.env"""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        else:
            # No secret configured (test mode): parse without verification (NOT for production)
            import json as _json
            event = _json.loads(payload)
            logger.warning("STRIPE_WEBHOOK_SECRET not set — webhook signature NOT verified (insecure)")
    except Exception as e:
        logger.exception("Webhook signature verify failed")
        raise HTTPException(400, f"Webhook verification failed: {str(e)}")

    etype = event.get("type") if isinstance(event, dict) else event["type"]
    obj = (event.get("data") if isinstance(event, dict) else event["data"]).get("object", {})
    now_iso = datetime.now(timezone.utc).isoformat()

    if etype == "checkout.session.completed":
        user_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
        customer_id = obj.get("customer")
        sub_id = obj.get("subscription")
        # Determine tier from the line items if possible (else from metadata.plan)
        tier = "plus"
        try:
            if sub_id:
                sub = stripe.Subscription.retrieve(sub_id)
                for item in (sub.get("items") or {}).get("data", []):
                    pid = (item.get("price") or {}).get("id")
                    if pid in PRICE_TO_TIER:
                        tier = PRICE_TO_TIER[pid]
                        break
            else:
                plan = (obj.get("metadata") or {}).get("plan")
                if plan in ("plus", "pro", "yearly"):
                    tier = plan
        except Exception:
            logger.exception("Could not resolve tier from subscription; defaulting to plus")
        if user_id:
            await db.users.update_one({"id": user_id}, {"$set": {
                "subscription_status": "active",
                "tier": tier,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": sub_id,
                "subscription_started_at": now_iso,
            }})
            logger.info(f"Subscription activated for user {user_id} on tier={tier}")
    elif etype == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        if customer_id:
            await db.users.update_one({"stripe_customer_id": customer_id},
                                      {"$set": {"subscription_status": "canceled",
                                                "tier": "free",
                                                "subscription_ended_at": now_iso}})
            logger.info(f"Subscription canceled for customer {customer_id}")
    elif etype == "customer.subscription.updated":
        customer_id = obj.get("customer")
        status_val = obj.get("status")
        # Re-derive tier from latest price
        new_tier = None
        for item in (obj.get("items") or {}).get("data", []):
            pid = (item.get("price") or {}).get("id")
            if pid in PRICE_TO_TIER:
                new_tier = PRICE_TO_TIER[pid]
                break
        update = {"subscription_updated_at": now_iso}
        if status_val:
            update["subscription_status"] = status_val
            if status_val in ("canceled", "incomplete_expired", "unpaid"):
                update["tier"] = "free"
            elif new_tier and status_val == "active":
                update["tier"] = new_tier
        if customer_id:
            await db.users.update_one({"stripe_customer_id": customer_id}, {"$set": update})
    elif etype == "invoice.payment_failed":
        customer_id = obj.get("customer")
        if customer_id:
            await db.users.update_one({"stripe_customer_id": customer_id},
                                      {"$set": {"subscription_status": "past_due",
                                                "subscription_updated_at": now_iso}})
    return {"received": True}

@api_router.get("/subscription/status")
async def sub_status(user: dict = Depends(get_user)):
    return user_to_public(user)

@api_router.get("/subscription/tiers")
async def get_tiers():
    """Public — pricing/feature info for the Subscribe modal."""
    return {
        "tiers": [
            {"id": "free", "name": "Free", "price_gbp": 0, "period": "forever",
             "highlights": ["5 Lex chats / day", "1 photo evidence / month", "1 letter / month",
                            "View 31 templates", "3 files", "Emergency rights (always free)"]},
            {"id": "plus", "name": "Plus", "price_gbp": 14.99, "period": "month",
             "highlights": ["Unlimited Lex chats", "15 photo evidences / month",
                            "Unlimited letters", "Contract Review", "Court Prep modes",
                            "Voice in/out", "Practice Mode", "50 files", "Hey Lex wake word"]},
            {"id": "pro", "name": "Pro", "price_gbp": 24.99, "period": "month",
             "highlights": ["Everything in Plus", "Live Legal Assist", "Priority AI processing",
                            "Premium court templates", "Advanced document review", "Unlimited files",
                            "Priority email support"]},
            {"id": "yearly", "name": "Yearly Pro", "price_gbp": 239.99, "period": "year",
             "best_value": True, "savings_pct": 20,
             "highlights": ["Everything in Pro", "Save 20% vs monthly", "12 months full access"]},
        ],
        "currency": "GBP",
    }

@api_router.get("/subscription/usage")
async def usage_summary(user: dict = Depends(get_user)):
    pub = user_to_public(user)
    return {"tier": pub["tier"], "usage": await get_user_usage_summary(user["id"], pub["tier"])}

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
    tier = pub["tier"]
    ok, used, limit = await check_quota_and_increment(user["id"], tier, "evidence_analyze", "monthly")
    if not ok:
        raise HTTPException(429, f"Monthly limit reached ({used}/{limit} photo analyses on your tier). Upgrade for more.")

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
def _font_for_lang(language: Optional[str]) -> tuple[str, str]:
    """Pick the right Noto variant for the language."""
    if not language:
        return (DEFAULT_FONT, DEFAULT_FONT_BOLD)
    code = language.split("-")[0].lower()
    if code in ("ar", "ur"):
        return ("NotoArabic", "NotoArabic")  # Arabic/Urdu
    if code == "zh":
        return ("NotoSC", "NotoSC")
    if code == "hi":
        return ("NotoDevanagari", "NotoDevanagari")
    return (DEFAULT_FONT, DEFAULT_FONT_BOLD)

def _qr_for_signup() -> Optional[io.BytesIO]:
    try:
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(f"{APP_PUBLIC_URL}?ref=pdf")
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a1300", back_color="white")
        buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
        return buf
    except Exception:
        return None

def build_pdf(title: str, body: str, subtitle: Optional[str] = None,
              meta: Optional[dict] = None, language: str = "en-GB") -> bytes:
    """Generate a branded AI Advocate PDF (multilingual + QR + footer)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22*mm, rightMargin=22*mm,
        topMargin=20*mm, bottomMargin=22*mm,
        title=title, author="AI Advocate",
    )
    GOLD = HexColor("#d6a017")
    GOLD_DEEP = HexColor("#9b7414")
    DARK = HexColor("#1a1300")
    DIM = HexColor("#555555")

    font, font_b = _font_for_lang(language)
    is_rtl = (language or "").split("-")[0].lower() in ("ar", "ur")
    align = TA_LEFT  # ReportLab paragraph dir handled via wordWrap

    h_title = ParagraphStyle("title", fontName=font_b, fontSize=18, leading=22,
                             textColor=DARK, spaceAfter=4, alignment=align,
                             wordWrap="RTL" if is_rtl else None)
    h_sub = ParagraphStyle("sub", fontName=font, fontSize=11, textColor=DIM,
                           spaceAfter=12, alignment=align)
    h_meta = ParagraphStyle("meta", fontName=font, fontSize=9, textColor=DIM, spaceAfter=2)
    h_body = ParagraphStyle("body", fontName=font, fontSize=11, leading=16,
                            textColor=HexColor("#222222"), alignment=align,
                            spaceAfter=8, wordWrap="RTL" if is_rtl else None)

    elems = []
    logo_path = "/app/frontend/public/assets/logo.jpg"
    if os.path.exists(logo_path):
        img = RLImage(logo_path, width=44*mm, height=44*mm)
        img.hAlign = "CENTER"
        elems.append(img); elems.append(Spacer(1, 4*mm))

    elems.append(HRFlowable(width="100%", thickness=0.6, color=GOLD, spaceBefore=2, spaceAfter=12))
    elems.append(Paragraph(title, h_title))
    if subtitle:
        elems.append(Paragraph(subtitle, h_sub))
    if meta:
        for k, v in meta.items():
            if v:
                elems.append(Paragraph(f"<b>{k}:</b> {v}", h_meta))
        elems.append(Spacer(1, 8))

    safe = (body or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for para in safe.split("\n\n"):
        para = para.replace("\n", "<br/>")
        if para.strip():
            elems.append(Paragraph(para, h_body))

    elems.append(HRFlowable(width="100%", thickness=0.4, color=GOLD_DEEP, spaceBefore=14, spaceAfter=6))

    def _on_page(canvas, doc_):
        canvas.saveState()
        # Footer left: brand/CTA. Right: QR. Center: page number.
        canvas.setFont(font, 8)
        canvas.setFillColor(DIM)
        canvas.drawCentredString(A4[0]/2, 12*mm, f"AI Advocate · Page {doc_.page}")
        # Branded CTA on left
        canvas.setFont(font_b, 7.5); canvas.setFillColor(GOLD_DEEP)
        canvas.drawString(22*mm, 12*mm, "Generated by AI ADVOCATE")
        canvas.setFont(font, 7); canvas.setFillColor(DIM)
        canvas.drawString(22*mm, 8*mm, "AI lawyer in your pocket — get yours in 60s")
        # QR on right
        qbuf = _qr_for_signup()
        if qbuf:
            try:
                from reportlab.lib.utils import ImageReader
                canvas.drawImage(ImageReader(qbuf), A4[0]-22*mm-14*mm, 6*mm,
                                 width=14*mm, height=14*mm, mask='auto')
            except Exception:
                pass
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

    pdf_bytes = build_pdf(title=title, body=body, subtitle="Prepared by Lex, your AI advocate",
                          meta=meta, language=f.get("language", "en-GB"))
    safe_fname = "".join(c for c in fname if c.isalnum() or c in (" ", "-", "_")).strip()[:60] or "ai_advocate"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_fname}.pdf"'})

class PDFInline(BaseModel):
    title: str
    body: str
    subtitle: Optional[str] = None
    meta: Optional[dict] = None
    filename: Optional[str] = "ai_advocate.pdf"
    language: Optional[str] = "en-GB"

@api_router.post("/pdf/inline")
async def pdf_inline(data: PDFInline, user: dict = Depends(get_user)):
    """Generate a PDF on the fly from any text content (e.g. fresh letter before save)."""
    pdf_bytes = build_pdf(title=data.title, body=data.body, subtitle=data.subtitle,
                          meta=data.meta, language=data.language or "en-GB")
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

# ==================== Apple Domain Association ====================
# Apple verifies domain ownership for Sign in with Apple via this file
APPLE_DOMAIN_ASSOC_TOKEN = os.environ.get("APPLE_DOMAIN_ASSOC_TOKEN", "")

@app.get("/.well-known/apple-developer-domain-association.txt")
async def apple_domain_association():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(APPLE_DOMAIN_ASSOC_TOKEN or "")

@app.get("/.well-known/apple-app-site-association")
async def apple_app_site_association():
    """Universal Links file (for Capacitor iOS app later)"""
    from fastapi.responses import JSONResponse
    bundle_id = f"{APPLE_TEAM_ID}.uk.co.aiadvocate.official" if APPLE_TEAM_ID else ""
    return JSONResponse({
        "applinks": {"apps": [], "details": [{"appID": bundle_id, "paths": ["*"]}]} if bundle_id else {},
        "webcredentials": {"apps": [bundle_id]} if bundle_id else {},
    })

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
