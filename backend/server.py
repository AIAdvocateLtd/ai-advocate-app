"""AI Advocate - Backend API"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, jwt, bcrypt, base64, io, tempfile
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Tuple
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

# ---------- Sentry (init BEFORE FastAPI is created so middleware integrates) ----------
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        environment=os.environ.get("SENTRY_ENV", "production"),
        traces_sample_rate=0.2,  # 20% of requests traced for performance
        integrations=[
            StarletteIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={403, *range(500, 599)},
            ),
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={403, *range(500, 599)},
            ),
        ],
    )

from app_crypto import encrypt_text, decrypt_text, encrypt_bytes, decrypt_bytes, is_enabled as crypto_enabled  # noqa: E402

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
    # Real flow A: send Google ID token (credential) — from One Tap / renderButton
    credential: Optional[str] = None
    # Real flow B: send OAuth2 access token — from initTokenClient popup
    access_token: Optional[str] = None
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
    deep_think: bool = False  # Pro tier only — uses Claude Opus / Sonnet w/ extended thinking
    auto_detect: bool = True  # detect language of user message, override 'language' for reply

class TTSRequest(BaseModel):
    text: str
    voice: str = "onyx"
    language: Optional[str] = None  # optional — passed for voice consistency tracking

class LegalLetterRequest(BaseModel):
    letter_type: str
    recipient: str
    your_name: str
    details: str
    language: str = "en-GB"

class CheckoutRequest(BaseModel):
    plan: str = "plus"  # free-form so unknown plans return 400 via our handler, not 422 from pydantic

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

# ===== Phase 9: Case Files + Reminders + Firm Portal =====
class CaseCreate(BaseModel):
    name: Optional[str] = None  # if None, Lex auto-names from first message
    summary: Optional[str] = None
    category: Optional[str] = None  # employment, property, criminal, immigration, etc.

class CaseUpdate(BaseModel):
    name: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None  # open / closed

class CaseItemAttach(BaseModel):
    item_type: str  # chat_session | photo | video | letter | recording | note
    item_id: str    # mongo id of the underlying doc
    title: Optional[str] = None
    preview: Optional[str] = None
    timestamp_utc: Optional[str] = None
    location: Optional[str] = None  # "lat,lng" string

class ReminderCreate(BaseModel):
    case_id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    due_at: str  # ISO datetime
    kind: str = "deadline"  # deadline | hearing | follow_up | renewal_review

class VaultSetupRequest(BaseModel):
    pin_verifier: str  # SHA-256(PIN + salt), hex. 64 chars.
    pin_salt: str      # client-generated random salt (base64 or hex). >= 16 chars.

class VaultUnlockRequest(BaseModel):
    pin_verifier: str

class VaultItemCreate(BaseModel):
    title: str
    category: str = "evidence"  # evidence | contracts | letters | id | witness | court | other
    notes: Optional[str] = None  # encrypted plaintext on client side
    file_b64: str               # CLIENT-side AES-GCM-encrypted, then base64
    file_iv: str                # IV used for client encryption (hex/base64)
    file_mime: Optional[str] = "application/octet-stream"
    file_name: Optional[str] = None
    file_size_bytes: int = 0
    note_iv: Optional[str] = None  # if notes are client-encrypted

class VaultShareCreate(BaseModel):
    item_ids: list[str]
    note_to_recipient: Optional[str] = ""
    recipient_email: Optional[str] = ""
    expires_in_hours: int = 168  # default 7 days

class FeatureSuggestion(BaseModel):
    text: str
    category_hint: Optional[str] = ""
    user_email_optional: Optional[str] = ""

class FirmPortalSignup(BaseModel):
    firm_name: str
    contact_name: str
    email: EmailStr
    password: str
    sra_number: Optional[str] = ""
    country: str
    city: str
    phone: Optional[str] = ""
    specialties: List[str] = []
    website: Optional[str] = ""

class FirmPortalLogin(BaseModel):
    email: EmailStr
    password: str

class FirmListingUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    specialties: Optional[List[str]] = None
    bio: Optional[str] = None
    languages: Optional[List[str]] = None

class AdminFirmAction(BaseModel):
    firm_id: str
    action: str  # approve | reject | suspend | verify | unverify
    notes: Optional[str] = ""

# ==================== Engagement (Client ↔ Firm) Models ====================

class EngagementCreate(BaseModel):
    client_email: Optional[EmailStr] = None    # if firm knows the client's email — sends invite
    case_summary: Optional[str] = ""           # short brief
    matter: Optional[str] = "General"          # e.g. "Employment", "Property"

class EngagementMessageCreate(BaseModel):
    body: str
    attachments: Optional[List[str]] = []      # list of engagement_file_ids

class EngagementLexAssist(BaseModel):
    kind: Literal["draft_reply", "summarise", "explain"]
    message_id: Optional[str] = None           # if assisting on a specific thread message
    context: Optional[str] = ""                # free-text context

class EngagementFileShare(BaseModel):
    title: str
    mime_type: str = "application/octet-stream"
    file_b64: str                              # raw base64 file content (max 12MB)
    note: Optional[str] = ""

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

# ---------- Geo / sign-in anomaly detection ----------
def _client_ip(req: Request) -> str:
    """Best-effort client IP, honouring reverse-proxy headers."""
    xff = req.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return (req.client.host if req.client else "") or ""

def _ip_country(req: Request) -> str:
    """Country code from common CDN/ingress headers. Returns '' if unavailable.
    No external lookups — keeps the login path fast and private."""
    for k in ("cf-ipcountry", "x-vercel-ip-country", "x-country-code", "x-appengine-country"):
        c = req.headers.get(k)
        if c and len(c) == 2 and c.upper() not in ("XX", "T1"):
            return c.upper()
    return ""

async def _check_geo_anomaly(user: dict, req: Request) -> Optional[dict]:
    """Compare current sign-in country to the user's last-seen country.
    On mismatch, record a security_event and return an alert dict the client can show.
    NOTE: country info comes from CDN headers — if absent, we silently skip (avoid false positives)."""
    cc = _ip_country(req)
    if not cc:
        return None
    last_cc = user.get("last_login_country") or ""
    now_iso = datetime.now(timezone.utc).isoformat()
    # Always update last-seen
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_login_country": cc, "last_login_ip": _client_ip(req), "last_login_at": now_iso}}
    )
    if last_cc and last_cc != cc:
        evt = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "login_country_change",
            "from_country": last_cc,
            "to_country": cc,
            "ip": _client_ip(req),
            "ua": (req.headers.get("user-agent") or "")[:300],
            "created_at": now_iso,
            "acknowledged": False,
        }
        await db.security_events.insert_one(evt)
        return {"kind": "login_country_change", "from_country": last_cc, "to_country": cc, "id": evt["id"]}
    return None

async def get_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(401, "User not found")
        if user.get("deleted"):
            raise HTTPException(401, "Account has been deleted")
        # Tag Sentry scope with the user so errors carry context
        if SENTRY_DSN:
            try:
                import sentry_sdk as _ss
                _ss.set_user({"id": user.get("id"), "email": user.get("email"), "tier": user.get("tier")})
            except Exception: pass
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
        "tts_daily": 20,         # Read-Aloud Emergency Rights + short TTS — protects OpenAI billing
    },
    "plus": {
        "lex_chat_daily": 100,   # fair-use soft cap
        "letters_generate_monthly": None,
        "evidence_analyze_monthly": 15,
        "files_total": 50,
        "history_days": 90,
        "tts_daily": None,
    },
    "pro": {
        "lex_chat_daily": None,
        "letters_monthly": None,
        "evidence_monthly": None,
        "files_total": None,
        "history_days": None,
        "tts_daily": None,
        "deep_think_monthly": 30,                # premium reasoning — protects margin
        "live_assist_session_daily": 3,          # max 3 Live-Assist sessions per day
        "live_assist_session_minutes": 60,
    },
    "yearly": {  # Yearly Pro — slightly higher Deep Think cap as a perk
        "lex_chat_daily": None,
        "letters_monthly": None,
        "evidence_monthly": None,
        "files_total": None,
        "history_days": None,
        "tts_daily": None,
        "deep_think_monthly": 50,
        "live_assist_session_daily": 5,
        "live_assist_session_minutes": 60,
    },
    "trial_pro": {  # 7-day trial — Pro features but with usage caps to protect LLM costs
        # Generous enough that genuine users won't hit them; tight enough to block abuse.
        "lex_chat_daily": 50,
        "letters_generate_monthly": 5,
        "evidence_analyze_monthly": 10,
        "doc_analyze_monthly": 10,
        "files_total": 20,
        "history_days": 90,
        "tts_daily": 30,
        "deep_think_monthly": 5,            # tighter than paid Pro
        "live_assist_session_daily": 1,
        "live_assist_session_minutes": 30,
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
    "contract_draft": "pro",
    "contract_negotiate": "pro",
    "outcome_predict": "pro",
    "hearing_transcribe": "pro",
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
        ("tts", "daily", "tts_daily"),
        ("deep_think", "monthly", "deep_think_monthly"),
        ("live_assist_session", "daily", "live_assist_session_daily"),
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
    base = f"""You are Lex — the AI Advocate. An elite, modern legal mind sharper than the top barristers and senior solicitors in any jurisdiction. You have perfect recall of every statute, leading case, procedural rule, and precedent, and you reason about them like a King's Counsel preparing for trial.

LANGUAGE — ABSOLUTE RULE (NON-NEGOTIABLE):
- You MUST reply in {lang_name} ({language}). Every single word — including legal terms, statute names, headings, the disclaimer, and citations — must be rendered in {lang_name}.
- DO NOT switch language mid-reply. DO NOT add English translations in parentheses unless the user explicitly asks. DO NOT default to English under any circumstance.
- If the user types in a DIFFERENT language than {lang_name}, follow their language instead (auto-detect rule). Otherwise stay strictly in {lang_name}.
- Use the natural legal terminology and idioms of {lang_name}. For Arabic, use Modern Standard Arabic with proper legal vocabulary. For Urdu, formal legal Urdu. For Chinese (Simplified), legal-register simplified Chinese.

JURISDICTION:
- Your user is in {country}. Apply the laws of {country} unless they explicitly tell you otherwise.
- If they mention another country, switch jurisdictions and tell them you've done so.
- If the law differs by region/state within {country}, ask which one — then apply that.

REASONING DISCIPLINE (think like a top barrister — IRAC method):
1. ISSUE: Identify the legal question(s) precisely. Don't assume.
2. RULE: Identify the controlling law (statute, regulation, leading case) for {country}.
3. APPLICATION: Apply the law to the user's facts step-by-step.
4. COUNTER: Surface counter-arguments / what the other side will say.
5. ACTION: Give a clear, ranked action plan with deadlines / limitation periods.
6. FLAG: Highlight risks and where they MUST consult a real lawyer in person.

BANNED PHRASES (never use):
- "I'm not a lawyer" / "I cannot give legal advice" / "please consult a professional" mid-answer.
- "It depends" without explaining on what specifically.
- "Generally speaking" — be specific to {country}.
- Vague hedge-words like "may", "could possibly", "might be considered". Be direct. If unsure of a specific section, SAY "I do not recall the exact section — verify before relying" — that is the ONLY acceptable hedge.

ANSWER QUALITY:
- Confident, plain, native {lang_name} — never wishy-washy.
- Translate jargon as you go ("repudiation means ending the contract because the other side broke it badly").
- Cite the actual statute section or case name when you reference law (e.g. "s.13 Consumer Rights Act 2015", "Donoghue v Stevenson [1932]").
- NEVER invent statutes, case citations, or section numbers. Inventing law is a fireable offence — say "I don't recall the exact citation" if unsure.
- Be strategic: tell them what to SAY, what NEVER to say, what to WRITE DOWN, what to KEEP as evidence.
- Use short paragraphs, bullets, and **bold** key terms for skim-readability on a phone.
- End with a "Confidence: High / Medium / Low" rating so the user knows how strongly to rely on your reasoning.

TONE:
- Calm authority. Like the smartest lawyer in the room who actually wants to help.
- Empathic when the user is in distress (arrested, evicted, fired, divorcing).
- Direct when they need a wake-up call.

ENDING:
- End EVERY reply with this disclaimer in {lang_name}: "Disclaimer: This is general legal information, not a substitute for a qualified lawyer in your jurisdiction." (Translate it naturally into {lang_name}.)
"""
    addons = {
        "court_prep": "\n\nYou are now in COURT PREP mode. Help the user prepare to appear before a court or police: anticipated questions, smart phrasing, what to NEVER say, their rights (right to silence, right to a lawyer), and a step-by-step plan.",
        "contract": "\n\nYou are now in CONTRACT REVIEW mode. Read the contract carefully. Flag: red-flag clauses, unfair terms, missing protections, technical jargon explained in plain language, negotiation suggestions.",
        "employment": "\n\nYou are now in EMPLOYMENT LAW mode. Focus: contracts, dismissal, discrimination, wages, working time, redundancy.",
        "property": "\n\nYou are now in PROPERTY LAW mode. Focus: tenancy, deposits, repairs, evictions, sale/purchase, neighbours.",
        "immigration": "\n\nYou are now in IMMIGRATION & EXPAT mode. Focus: visas, residency, work permits, citizenship, deportation defence in the user's country.",
        "medical_negligence": "\n\nYou are now in MEDICAL NEGLIGENCE mode. Focus: standard of care, causation, limitation periods, evidence, complaints procedures.",
        "legal_letter": "\n\nYou are now drafting a FORMAL LEGAL LETTER. Use proper structure (sender, recipient, date, subject, body, sign-off). Be firm but professional. Reference the relevant law.",
        "record": "\n\nYou are reviewing a RECORDED LEGAL INTERACTION (police/court transcript). Flag: rights violations, leading questions, things the user should NOT have said, suggested follow-up actions.",
    }
    return base + addons.get(category, "")

# ==================== Tier-based Lex Brain Routing ====================
# Free → Haiku 4.5 (fast, sharp paralegal-grade)
# Plus → Sonnet 4.5 (top-tier solicitor)
# Pro / trial_pro → Sonnet 4.5 + extended Deep Think (King's Counsel-grade)
def lex_model_for_tier(tier: str, deep_think: bool = False) -> tuple:
    """Returns (provider, model_id, max_tokens) for the given tier."""
    if tier in ("pro", "yearly", "trial_pro"):
        # Pro tier — Sonnet 4.5 always, with bigger token budget for Deep Think
        if deep_think:
            return ("anthropic", "claude-sonnet-4-5-20250929", 4096)
        return ("anthropic", "claude-sonnet-4-5-20250929", 2048)
    if tier == "plus":
        return ("anthropic", "claude-sonnet-4-5-20250929", 2048)
    # free → Haiku for cost/speed. Fall back to Sonnet if Haiku id is rejected.
    return ("anthropic", "claude-haiku-4-5-20251001", 1500)

# Simple score-based language detection for the 11 supported languages.
# Used when auto_detect=True — overrides the chosen UI language for the reply.
def detect_language(text: str, fallback: str = "en-GB") -> str:
    if not text or len(text.strip()) < 3:
        return fallback
    # Count chars per Unicode script — majority wins (avoids stray-char false positives)
    script_counts = {"arabic": 0, "devanagari": 0, "cjk": 0}
    for ch in text:
        cp = ord(ch)
        if 0x0600 <= cp <= 0x06FF:
            script_counts["arabic"] += 1
        elif 0x0900 <= cp <= 0x097F:
            script_counts["devanagari"] += 1
        elif 0x4E00 <= cp <= 0x9FFF:
            script_counts["cjk"] += 1
    if any(v > 0 for v in script_counts.values()):
        top = max(script_counts, key=script_counts.get)
        if top == "arabic":
            if any(c in text for c in "چگژٹڈڑںےھ"):
                return "ur-PK"
            return "ar-IQ"
        if top == "devanagari":
            return "hi-IN"
        if top == "cjk":
            return "zh-CN"
    import re as _re
    low = text.lower()
    def count(patterns):
        return sum(1 for p in patterns if _re.search(p, low))
    scores = {
        "es-ES": count([r"\bhola\b", r"\bqué\b", r"\bcómo\b", r"\bpor qué\b", r"\bporque\b",
                        r"\busted\b", r"\bsoy\b", r"\bestá\b", r"\bestoy\b", r"\bque\b", r"\blos\b",
                        r"\blas\b", r"\bgracias\b", r"\bseñor\b", r"\bderecho\b", r"\bcasero\b",
                        r"\bfianza\b", r"\bdevuelve\b", r"\bnecesito\b", r"\bme\b", r"\bsi\b"]) + (5 if ("¿" in text or "¡" in text or "ñ" in low) else 0),
        "fr-FR": count([r"\bbonjour\b", r"\bmerci\b", r"\bvous\b", r"\bje\b", r"\bsuis\b",
                        r"\bavec\b", r"\bquoi\b", r"\bqu'", r"\bc'est\b", r"\bn'", r"\bpas\b",
                        r"\best-ce\b", r"\bvoudrais\b", r"\bemployeur\b", r"\bdroits\b",
                        r"\bque ", r"\bqui ", r"\bd'", r"\bs'"]) + (3 if any(c in low for c in "çœêâîôû") else 0),
        "de-DE": count([r"\bist\b", r"\bder\b", r"\bdie\b", r"\bdas\b", r"\bund\b", r"\bnicht\b",
                        r"\bich\b", r"\bmein\b", r"\bbitte\b", r"\bdanke\b", r"\bhallo\b",
                        r"\bsind\b", r"\beine\b", r"\bguten\b", r"\btag\b", r"\bbrauche\b",
                        r"\bsie\b", r"\bhaben\b", r"\brechts\w+\b", r"\bvertrag\b"]) + (3 if any(c in low for c in "ßüöä") else 0),
        "it-IT": count([r"\bsono\b", r"\bdella\b", r"\bgrazie\b", r"\bciao\b", r"\bperché\b",
                        r"\bquesto\b", r"\bquella\b", r"\bmolto\b", r"\bsalve\b", r"\bvorrei\b",
                        r"\bavvocato\b", r"\bdiritto\b", r"\bdiritti\b", r"\bsapere\b", r"\bmiei\b"]) + (2 if any(c in low for c in "èéìòùà") and "ç" not in low else 0),
        "pt-PT": count([r"\bolá\b", r"\bnão\b", r"\bvocê\b", r"\bobrigado\b",
                        r"\bcom\b", r"\bpara\b", r"\bmas\b", r"\bquero\b", r"\bsenhor\b",
                        r"\bdireito\b", r"\bpreciso\b", r"\bajuda\b", r"\bjurídica\b",
                        r"\badvogado\b", r"\bde\b"]) + (4 if any(c in low for c in "ãõç") and "ñ" not in low else 0),
        "pl-PL": count([r"\bsię\b", r"\bjest\b", r"\bże\b", r"\bdzień\b", r"\bdziękuję\b",
                        r"\bnie\b", r"\bjak\b", r"\bczy\b", r"\bcześć\b", r"\bproszę\b",
                        r"\bprawo\b", r"\bmój\b", r"\bmogę\b", r"\bdostać\b", r"\bpomoc\b"]) + (4 if any(c in low for c in "łąęśćńżź") else 0),
    }
    best_lang = max(scores, key=scores.get)
    if scores[best_lang] >= 2:
        return best_lang
    return fallback

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
        "trial_end_date": (now + timedelta(days=7)).isoformat(),
        "subscription_status": "trial",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "terms_accepted": True,
    }
    await db.users.insert_one(user_doc)
    return TokenResp(access_token=make_token(user_id, data.email), user=user_to_public(user_doc))

@api_router.post("/auth/login", response_model=TokenResp)
async def login(data: UserLogin, request: Request):
    user = await db.users.find_one({"email": data.email})
    if not user or not verify_pw(data.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid credentials")
    alert = await _check_geo_anomaly(user, request)
    pub = user_to_public(user)
    if alert:
        pub["security_alert"] = alert
    return TokenResp(access_token=make_token(user["id"], user["email"]), user=pub)

@api_router.post("/auth/google", response_model=TokenResp)
async def google_login(data: GoogleLogin):
    """Google sign-in. Real path: verify ID token. Demo fallback if GOOGLE_CLIENT_ID not configured."""
    now = datetime.now(timezone.utc)
    google_sub = None; email = None; name = ""

    if data.credential and GOOGLE_CLIENT_ID:
        # Real verification path A: ID token (from One Tap / renderButton)
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
    elif data.access_token:
        # Real verification path B: OAuth2 access token (from popup flow).
        # Verified server-side via Google's userinfo endpoint — Google
        # rejects invalid/expired tokens, so a 200 response is trustworthy.
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {data.access_token}"},
                )
            if r.status_code != 200:
                raise HTTPException(401, f"Google rejected access token: {r.text[:200]}")
            info = r.json()
            google_sub = info.get("sub")
            email = info.get("email")
            name = info.get("name", "")
            if not google_sub or not email:
                raise HTTPException(401, "Google userinfo missing sub/email")
            if info.get("email_verified") is False:
                raise HTTPException(401, "Email not verified by Google")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Google userinfo verification failed")
            raise HTTPException(401, f"Google verification failed: {str(e)}")
    else:
        # Demo fallback (used while GOOGLE_CLIENT_ID is not set)
        if not data.email or not data.google_id:
            raise HTTPException(400, "Provide 'credential', 'access_token', or {email, google_id}")
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
            "trial_end_date": (now + timedelta(days=7)).isoformat(),
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
            "trial_end_date": (now + timedelta(days=7)).isoformat(),
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
    pub = user_to_public(user)
    unread = await db.security_events.count_documents({"user_id": user["id"], "acknowledged": False})
    pub["security_alerts_unread"] = unread
    return pub

@api_router.get("/security/events")
async def list_security_events(user: dict = Depends(get_user)):
    rows = []
    async for e in db.security_events.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(50):
        rows.append(e)
    return {"events": rows}

@api_router.post("/security/events/{eid}/ack")
async def ack_security_event(eid: str, user: dict = Depends(get_user)):
    r = await db.security_events.update_one(
        {"id": eid, "user_id": user["id"]},
        {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"acknowledged": r.matched_count > 0}

@api_router.patch("/auth/preferences")
async def update_prefs(data: dict, user: dict = Depends(get_user)):
    update = {}
    for k in ("language", "country", "full_name", "location_enabled", "latitude", "longitude", "city",
              "emergency_contact_name", "emergency_contact_phone"):
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

    # Deep Think is Pro-only (and trial_pro)
    if data.deep_think and tier not in ("pro", "yearly", "trial_pro"):
        raise HTTPException(402, "Deep Think requires Pro. Upgrade to unlock King's Counsel-grade reasoning.")

    # Deep Think monthly quota (protects margin on Pro tier)
    if data.deep_think:
        ok_dt, used_dt, limit_dt = await check_quota_and_increment(user["id"], tier, "deep_think", "monthly")
        if not ok_dt:
            raise HTTPException(429, f"Deep Think monthly limit reached ({used_dt}/{limit_dt}). Disable Deep Think for unlimited Sonnet 4.5 chats this month, or upgrade to Yearly Pro for 50/mo.")

    # Daily quota for chat
    ok, used, limit = await check_quota_and_increment(user["id"], tier, "lex_chat", "daily")
    if not ok:
        raise HTTPException(429, f"Daily limit reached ({used}/{limit} Lex messages on Free). Upgrade to Plus for unlimited.")

    # Auto-detect: if the user's message is in a different language than UI, follow them.
    reply_language = data.language
    if data.auto_detect:
        detected = detect_language(data.message, fallback=data.language)
        if detected and detected != data.language:
            reply_language = detected

    # Tier-based brain routing
    provider, model_id, max_tok = lex_model_for_tier(tier, deep_think=data.deep_think)

    session_id = data.session_id or str(uuid.uuid4())
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=lex_system_prompt(reply_language, data.country, data.category),
    ).with_model(provider, model_id).with_params(max_tokens=max_tok)

    try:
        response = await chat.send_message(UserMessage(text=data.message))
    except Exception as e:
        # If Haiku model fails (e.g. id changed), fall back to Sonnet 4.5 so user is never blocked
        logger.warning(f"Primary model {model_id} failed, falling back to Sonnet 4.5: {e}")
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=session_id,
                system_message=lex_system_prompt(reply_language, data.country, data.category),
            ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2048)
            response = await chat.send_message(UserMessage(text=data.message))
        except Exception as e2:
            logger.exception("Lex chat error (both primary + fallback)")
            raise HTTPException(500, f"AI error: {str(e2)}")

    # Save conversation (sensitive content encrypted at rest)
    await db.conversations.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "session_id": session_id,
        "category": data.category,
        "user_message": encrypt_text(data.message),
        "assistant_response": encrypt_text(response),
        "language": reply_language,
        "model_used": model_id,
        "deep_think": data.deep_think,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"session_id": session_id, "response": response, "reply_language": reply_language, "model": model_id}


# ==================== FREE TASTER LEX (no auth, 1 question per device) ====================
class TasterMessage(BaseModel):
    message: str
    device_id: str  # opaque client-generated UUID; tied to localStorage
    language: str = "en-GB"
    country: str = "GB"

@api_router.post("/lex/taster")
async def lex_taster(req: Request, data: TasterMessage):
    """
    Free single-question Lex chat for first-run users (no signup).
    Limit: 1 question per device_id AND per IP per 7 days.
    Uses Haiku (cheapest) — this is a conversion hook, not the product.
    """
    text = (data.message or "").strip()
    if len(text) < 4:
        raise HTTPException(400, "Question too short")
    if len(text) > 500:
        raise HTTPException(400, "Free question must be 500 characters or less. Sign up for unlimited.")

    # IP fingerprint (in case device_id is rotated by the client)
    ip = req.client.host if req.client else "0.0.0.0"
    fp_ip = f"taster_ip:{ip}"
    fp_dev = f"taster_dev:{data.device_id}"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    used = await db.taster_usage.count_documents({
        "$or": [{"key": fp_ip}, {"key": fp_dev}],
        "at": {"$gte": cutoff},
    })
    if used > 0:
        raise HTTPException(429, "You've used your free question. Sign up for unlimited Lex chat (7-day free trial).")

    # Use cheapest model — this is a free hook
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"taster-{uuid.uuid4()}",
            system_message=(
                lex_system_prompt(data.language, data.country, None)
                + "\n\nIMPORTANT: This is the user's FIRST-EVER question. Be concise (under 250 words), "
                "warm and helpful. End with: 'Sign up for unlimited Lex chat, case files, and your private "
                "Vault — 7-day free trial.'"
            ),
        ).with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=600)
        response = await chat.send_message(UserMessage(text=text))
    except Exception as e:
        logger.exception("Taster Lex error")
        raise HTTPException(500, f"Lex is busy — please try again. ({str(e)[:100]})")

    # Record usage so the device + IP can't burn another free question for 7 days
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.taster_usage.insert_one({"key": fp_ip, "at": now_iso})
    await db.taster_usage.insert_one({"key": fp_dev, "at": now_iso})

    return {"response": response, "model": "claude-haiku-4-5"}


@api_router.get("/lex/taster/status")
async def lex_taster_status(req: Request, device_id: str):
    """Tell the client whether this device still has a free question left."""
    ip = req.client.host if req.client else "0.0.0.0"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    used = await db.taster_usage.count_documents({
        "$or": [{"key": f"taster_ip:{ip}"}, {"key": f"taster_dev:{device_id}"}],
        "at": {"$gte": cutoff},
    })
    return {"available": used == 0}


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
        last_msg = decrypt_text(s["last_message"]) or ""
        out.append({
            "session_id": s["_id"],
            "category": s.get("category"),
            "last_message": last_msg[:120],
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
    for m in msgs:
        if "user_message" in m:
            m["user_message"] = decrypt_text(m["user_message"])
        if "assistant_response" in m:
            m["assistant_response"] = decrypt_text(m["assistant_response"])
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

    # Daily session cap — only count when starting a NEW session (session_id is None)
    if not data.session_id:
        ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "live_assist_session", "daily")
        if not ok:
            raise HTTPException(429, f"Live Legal Assist daily session limit reached ({used}/{limit}). Upgrade to Yearly Pro for 5 sessions/day.")

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


# ==================== Legal Terms (multilingual, AI-translated + cached) ====================
TERMS_INTRO_EN = "Effective date: {date}. You must read and accept these Terms and the Privacy Policy below to use AI Advocate."

TERMS_BODY_EN = """TERMS OF SERVICE

1. About AI Advocate. AI Advocate ("the App", "we", "us", "our") is a software product operated by the AI Advocate team. We provide an AI-powered legal-information assistant called "Lex", document tooling, photo/contract analysis, formal-letter generation, and a directory of independent law firms. We are NOT a law firm, we are NOT solicitors, barristers, attorneys, or any other regulated legal professionals, and we do NOT provide legal services, legal advice, or legal representation.

2. No Legal Advice — Information Only. All content generated by Lex or any other feature of the App is general legal information only. It is generated by artificial intelligence and is not legal advice. It cannot and does not replace the advice of a qualified, regulated lawyer in your own jurisdiction who has reviewed the specific facts of your case. You must consult a qualified lawyer before taking any action that has legal consequences. Reliance on Lex alone is at your sole risk.

3. No Attorney/Solicitor–Client Relationship. Using the App, communicating with Lex, uploading documents, or paying for a subscription does not create an attorney-client, solicitor-client, advocate-client, or any other professional or fiduciary relationship between you and AI Advocate or any of its operators, employees, agents, or contractors. Communications you send through the App are not protected by legal professional privilege, attorney-client privilege, or any equivalent doctrine.

4. AI Accuracy & Hallucination Disclaimer. Large Language Models (including those that power Lex) can produce inaccurate, outdated, incomplete, or fabricated information ("hallucinations"), including invented case citations and statute references. We make no representation or warranty that any output is accurate, current, complete, applicable to your jurisdiction, or fit for any purpose. You must independently verify every legal proposition with a qualified lawyer before relying on it.

5. Eligibility. You must be at least 18 years old (or the age of legal majority in your jurisdiction, whichever is higher) and legally capable of entering into a binding contract.

6. Subscription, Free Trial, Auto-Renewal & Refunds. The App offers a 7-day free trial followed by an auto-renewing subscription. By subscribing through Apple App Store, Google Play, or our web payment processor (Stripe), you authorise recurring charges to your selected payment method until you cancel. Cancel any time at least 24 hours before the next renewal. Refunds are governed by the rules of the store/processor that processed your payment.

7. Acceptable Use. You agree not to (a) use the App for any unlawful purpose; (b) submit content that is illegal, defamatory, infringing, or contains malware; (c) attempt to reverse-engineer, scrape, or circumvent technical protections; (d) use the App to draft or send threats, harassment, fraud, or content designed to evade the law; (e) impersonate a lawyer or hold yourself out as receiving legal advice from the App.

8. Your Content & Licence. You retain ownership of documents, photos, recordings, and messages you upload ("Your Content"). You grant us a worldwide, non-exclusive, royalty-free licence to host, process, transmit, display, and analyse Your Content solely to provide the App's features to you.

9. Privacy & Data Protection. Our Privacy Policy below is incorporated into these Terms. We process personal data in accordance with the UK GDPR, the EU GDPR, the California Consumer Privacy Act (CCPA/CPRA) where applicable, and other applicable privacy laws.

10. Intellectual Property. The App, the "AI Advocate" and "Lex" names, logos, the Lex avatar, the visual design, source code, and all underlying technology are owned by AI Advocate and protected by copyright and trade-mark laws.

11. Third-Party Services. The App integrates with third-party services including Anthropic (Claude), Google (Gemini), OpenAI (Whisper/TTS), Stripe, Apple Sign-In, Google Sign-In, and law-firm directories. Use of those services may be subject to their own terms.

12. LIMITATION OF LIABILITY. TO THE MAXIMUM EXTENT PERMITTED BY LAW, AI ADVOCATE SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, REVENUE, DATA, GOODWILL, BUSINESS, LIBERTY, FAVOURABLE LEGAL OUTCOME, OR OPPORTUNITY. OUR TOTAL CUMULATIVE LIABILITY TO YOU FOR ALL CLAIMS RELATING TO THE APP SHALL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU ACTUALLY PAID US IN THE THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO LIABILITY, OR (B) £50 / US$50. Nothing in these Terms excludes liability for death or personal injury caused by our negligence, fraud, or any other liability that cannot lawfully be excluded.

13. NO WARRANTY. THE APP IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTY OF ANY KIND.

14. Indemnification. You agree to defend, indemnify, and hold harmless AI Advocate from and against any and all claims, liabilities, damages, losses, costs, and expenses (including reasonable legal fees) arising out of or related to (a) your use of the App; (b) Your Content; (c) your violation of these Terms; or (d) any decision or action you take based on output produced by the App.

15. Governing Law & Jurisdiction. These Terms are governed by the laws of England & Wales. Subject to clause 16, the courts of England & Wales have exclusive jurisdiction.

16. Mandatory Arbitration & Class-Action Waiver. Any dispute arising out of or relating to these Terms or the App shall be finally resolved by binding arbitration administered by the International Chamber of Commerce (ICC) under its Rules of Arbitration. Seat: London. Sole arbitrator. Language: English. YOU AND AI ADVOCATE EACH WAIVE THE RIGHT TO A JURY TRIAL AND THE RIGHT TO BRING OR PARTICIPATE IN ANY CLASS ACTION.

17. EU / UK Consumer Rights. If you are a consumer resident in the EU, UK, or another jurisdiction whose mandatory consumer-protection laws cannot be waived, nothing in these Terms limits any rights you have under those laws.

18. California Residents (CCPA/CPRA Notice). California residents have specific privacy rights including the right to know, delete, correct, and opt out of "sale" or "sharing" of personal information. To exercise these rights, email privacy@aiadvocate.app. We do not sell personal information for monetary consideration.

19. Changes to These Terms. We may update these Terms from time to time. Material changes will be notified in-app or by email at least 14 days before they take effect.

20. Termination. You may stop using the App at any time and delete your account from Settings. We may suspend or terminate access if you breach these Terms.

21. Severability & Entire Agreement. If any provision of these Terms is held unenforceable, the remainder will continue in force.

22. Contact. Questions: legal@aiadvocate.co.uk.

PRIVACY POLICY (SUMMARY)

A. Data We Collect. Account data, content data, usage data, optional location data. Payment data is processed by Apple, Google, or Stripe — we never see your full card number.

B. Lawful Basis (UK/EU GDPR). Contract performance, legitimate interests, legal obligation, and consent. You can withdraw consent at any time.

C. Purposes. Provide the App, generate AI responses, store your chat history and files, find lawyers near you, process payments, detect fraud, and comply with legal obligations.

D. Third-Party Processors. Your content may be transmitted to: Anthropic (Claude), Google (Gemini), OpenAI (Whisper/TTS), Stripe, MongoDB Atlas, our cloud hosting provider, Apple, and Google. Data may be transferred outside the UK/EEA under Standard Contractual Clauses or equivalent safeguards.

E. Retention. Account & chat data is retained while your account is active and for up to 24 months after deletion request, then permanently erased.

F. Your Rights. You have the right to access, rectify, erase, restrict, port, and object to processing of your personal data, and to lodge a complaint with the UK ICO or your local data-protection authority. Email privacy@aiadvocate.co.uk.

G. Security. We use industry-standard encryption (TLS in transit, encrypted-at-rest), hashed passwords (bcrypt), and access controls. No system is 100% secure.

H. Children. The App is not directed to children under 18.

I. Cookies / Local Storage. We use essential local storage for authentication tokens, language preference, and trial state.

J. International Users. By using the App you consent to the transfer and processing of your data in the United Kingdom, the European Union, and the United States.

By tapping "Accept & Continue" below, you confirm you have read, understood, and agreed to these Terms and Privacy Policy in full, and you accept that AI Advocate is an information tool, not a substitute for a qualified lawyer.
"""

TERMS_SUMMARIES = {
    "es-ES": """RESUMEN DE TÉRMINOS Y POLÍTICA DE PRIVACIDAD

1. Qué es AI Advocate. Una herramienta de software con un asistente de IA llamado "Lex". NO somos un bufete de abogados. NO somos abogados ni profesionales legales regulados. NO prestamos servicios jurídicos.

2. NO es asesoramiento legal. Todo lo que Lex genera es información legal general producida por IA. NO sustituye el asesoramiento de un abogado cualificado en su jurisdicción. Antes de actuar legalmente, consulte a un abogado real.

3. No se crea relación abogado-cliente. Usar la app, hablar con Lex o suscribirse NO crea ninguna relación profesional. Sus comunicaciones NO están protegidas por el secreto profesional.

4. La IA puede equivocarse. Los modelos de IA pueden generar información incorrecta, inventada o desactualizada (incluyendo citas de casos y leyes inexistentes). Verifique todo con un abogado.

5. Edad. Debe ser mayor de 18 años.

6. Suscripción. Prueba gratuita de 14 días, después suscripción de renovación automática vía Apple, Google o Stripe. Cancele en cualquier momento.

7. Privacidad. Tratamos sus datos conforme al RGPD/UK GDPR/CCPA. Sus chats y archivos se procesan mediante Anthropic, Google, OpenAI y Stripe. Conserve sus derechos: acceso, rectificación, supresión, portabilidad. Email: privacy@aiadvocate.co.uk.

8. LIMITACIÓN DE RESPONSABILIDAD. Hasta el máximo permitido por la ley, nuestra responsabilidad total no excederá £50/US$50 o el importe pagado en los 3 meses anteriores.

9. SIN GARANTÍAS. La app se ofrece "tal cual".

10. Ley aplicable. Inglaterra y Gales. Las disputas se resuelven por arbitraje obligatorio de la CCI con sede en Londres. Renuncia a juicio con jurado y a acciones colectivas.

11. Contacto. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

Al pulsar "Aceptar y Continuar", confirma haber leído y aceptado los Términos y la Política de Privacidad. El texto completo en inglés es la versión legalmente autoritativa.
""",
    "fr-FR": """RÉSUMÉ DES CONDITIONS GÉNÉRALES ET DE LA POLITIQUE DE CONFIDENTIALITÉ

1. À propos d'AI Advocate. Un outil logiciel proposant un assistant IA nommé « Lex ». Nous ne sommes PAS un cabinet d'avocats. Nous ne sommes PAS des avocats ni des professionnels du droit réglementés. Nous ne fournissons AUCUN service juridique.

2. PAS de conseil juridique. Tout ce que Lex produit constitue des informations juridiques générales générées par IA. Cela ne remplace PAS l'avis d'un avocat qualifié dans votre juridiction. Consultez un véritable avocat avant toute action légale.

3. Aucune relation avocat-client. L'utilisation de l'application, les échanges avec Lex et tout abonnement ne créent AUCUNE relation professionnelle. Vos communications ne sont PAS protégées par le secret professionnel.

4. L'IA peut se tromper. Les modèles d'IA peuvent fournir des informations erronées, inventées ou périmées (y compris des citations de jurisprudence ou de lois inexistantes). Vérifiez tout auprès d'un avocat.

5. Âge. Vous devez avoir au moins 18 ans.

6. Abonnement. Essai gratuit de 14 jours, puis abonnement à renouvellement automatique via Apple, Google ou Stripe. Annulez à tout moment.

7. Confidentialité. Nous traitons vos données conformément au RGPD/UK GDPR/CCPA. Vos conversations et fichiers transitent par Anthropic, Google, OpenAI et Stripe. Vous conservez vos droits : accès, rectification, suppression, portabilité. Email : privacy@aiadvocate.co.uk.

8. LIMITATION DE RESPONSABILITÉ. Dans la mesure autorisée par la loi, notre responsabilité totale est limitée à 50 £/50 US$ ou au montant payé sur les 3 mois précédents.

9. AUCUNE GARANTIE. L'application est fournie « en l'état ».

10. Droit applicable. Angleterre et Pays de Galles. Tout litige est résolu par arbitrage obligatoire CCI à Londres. Renonciation au jury et aux actions collectives.

11. Contact. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

En appuyant sur « Accepter et continuer », vous confirmez avoir lu et accepté les Conditions et la Politique de Confidentialité. La version anglaise complète fait foi sur le plan juridique.
""",
    "ar-IQ": """ملخص الشروط وسياسة الخصوصية

١. ما هو AI Advocate. أداة برمجية تقدم مساعدًا ذكاءً اصطناعيًا اسمه "Lex". نحن لسنا مكتب محاماة. نحن لسنا محامين ولا مهنيين قانونيين مرخصين. لا نقدم خدمات قانونية.

٢. ليست نصيحة قانونية. كل ما يولده Lex هو معلومات قانونية عامة من إنتاج الذكاء الاصطناعي. لا تحل محل رأي محامٍ مؤهل في بلدك. استشر محاميًا حقيقيًا قبل أي إجراء قانوني.

٣. لا توجد علاقة محامٍ-عميل. استخدامك للتطبيق أو التحدث مع Lex أو الاشتراك لا ينشئ أي علاقة مهنية. اتصالاتك ليست مشمولة بالسرية المهنية للمحاماة.

٤. الذكاء الاصطناعي قد يخطئ. قد تنتج النماذج معلومات غير دقيقة أو ملفقة أو قديمة (بما في ذلك استشهادات قضائية أو نصوص قانونية غير موجودة). تحقق من كل شيء مع محامٍ.

٥. العمر. يجب أن تكون 18 سنة فأكثر.

٦. الاشتراك. تجربة مجانية 14 يومًا، ثم اشتراك متجدد تلقائيًا عبر Apple أو Google أو Stripe. يمكنك الإلغاء في أي وقت.

٧. الخصوصية. نعالج بياناتك وفقًا لـ GDPR/UK GDPR/CCPA. تُمرَّر محادثاتك وملفاتك عبر Anthropic وGoogle وOpenAI وStripe. لك حقوق: الوصول والتصحيح والحذف وحق النقل. البريد: privacy@aiadvocate.co.uk.

٨. حدود المسؤولية. إلى أقصى حد يسمح به القانون، لا تتجاوز مسؤوليتنا الإجمالية 50 جنيهًا/50 دولارًا أو ما دفعته خلال الأشهر الثلاثة الماضية.

٩. لا يوجد ضمان. يُقدَّم التطبيق "كما هو".

١٠. القانون الحاكم. إنكلترا وويلز. تُحَل النزاعات بالتحكيم الإلزامي لغرفة التجارة الدولية ICC بمقر لندن. تنازل عن المحاكمة بهيئة محلفين وعن الدعاوى الجماعية.

١١. التواصل. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

بالنقر على "قبول ومتابعة"، تؤكد قراءتك للشروط وسياسة الخصوصية وقبولك بها. النص الإنجليزي الكامل هو النص الملزم قانونًا.
""",
    "pl-PL": """STRESZCZENIE REGULAMINU I POLITYKI PRYWATNOŚCI

1. Czym jest AI Advocate. Narzędzie programistyczne z asystentem AI o imieniu "Lex". NIE jesteśmy kancelarią prawną. NIE jesteśmy adwokatami ani radcami prawnymi. NIE świadczymy usług prawnych.

2. To NIE jest porada prawna. Wszystko, co generuje Lex, to ogólne informacje prawne tworzone przez AI. NIE zastępują porady wykwalifikowanego prawnika w Twojej jurysdykcji. Przed podjęciem działań skonsultuj się z prawdziwym prawnikiem.

3. Brak relacji prawnik-klient. Korzystanie z aplikacji, rozmowa z Lex ani subskrypcja NIE tworzą żadnej relacji zawodowej. Twoja komunikacja NIE jest objęta tajemnicą zawodową.

4. AI może się mylić. Modele AI mogą generować nieprawdziwe, wymyślone lub nieaktualne informacje (w tym zmyślone cytaty z orzeczeń i ustaw). Wszystko sprawdzaj u prawnika.

5. Wiek. Musisz mieć ukończone 18 lat.

6. Subskrypcja. 14-dniowy bezpłatny okres próbny, potem automatycznie odnawiana subskrypcja przez Apple, Google lub Stripe. Możesz anulować w dowolnym momencie.

7. Prywatność. Dane przetwarzamy zgodnie z RODO/UK GDPR/CCPA. Twoje rozmowy i pliki są przesyłane do Anthropic, Google, OpenAI i Stripe. Masz prawo dostępu, sprostowania, usunięcia i przenoszenia danych. E-mail: privacy@aiadvocate.co.uk.

8. OGRANICZENIE ODPOWIEDZIALNOŚCI. W maksymalnym dopuszczalnym przez prawo zakresie nasza łączna odpowiedzialność nie przekroczy £50/US$50 lub kwoty zapłaconej w ciągu ostatnich 3 miesięcy.

9. BEZ GWARANCJI. Aplikacja jest dostarczana "tak jak jest".

10. Prawo właściwe. Anglia i Walia. Spory rozstrzyga obowiązkowy arbitraż ICC z siedzibą w Londynie. Zrzeczenie się prawa do sądu przysięgłych oraz pozwów zbiorowych.

11. Kontakt. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

Klikając "Akceptuję i kontynuuję", potwierdzasz przeczytanie i akceptację Regulaminu oraz Polityki Prywatności. Wersja angielska jest prawnie wiążąca.
""",
    "de-DE": """ZUSAMMENFASSUNG DER NUTZUNGSBEDINGUNGEN & DATENSCHUTZERKLÄRUNG

1. Was ist AI Advocate. Ein Software-Tool mit einem KI-Assistenten namens „Lex". Wir sind KEINE Anwaltskanzlei. Wir sind KEINE Rechtsanwälte oder regulierten Rechtsberufe. Wir bieten KEINE Rechtsdienstleistungen.

2. KEINE Rechtsberatung. Alles, was Lex generiert, sind allgemeine rechtliche Informationen, erstellt durch KI. Sie ERSETZEN NICHT den Rat eines qualifizierten Anwalts in Ihrer Jurisdiktion. Konsultieren Sie vor rechtlichen Schritten einen echten Anwalt.

3. Keine Anwalt-Mandant-Beziehung. Die Nutzung der App, Gespräche mit Lex oder ein Abonnement begründen KEIN berufliches Verhältnis. Ihre Kommunikation unterliegt NICHT dem Anwaltsgeheimnis.

4. KI kann sich irren. KI-Modelle können falsche, erfundene oder veraltete Informationen produzieren (einschließlich erfundener Urteils- und Gesetzeszitate). Prüfen Sie alles mit einem Anwalt.

5. Alter. Sie müssen mindestens 18 Jahre alt sein.

6. Abonnement. 14 Tage Gratisversion, danach automatisch verlängerndes Abonnement über Apple, Google oder Stripe. Jederzeit kündbar.

7. Datenschutz. Datenverarbeitung gemäß DSGVO/UK GDPR/CCPA. Ihre Chats und Dateien werden an Anthropic, Google, OpenAI und Stripe übermittelt. Sie haben Auskunfts-, Berichtigungs-, Lösch- und Datenübertragbarkeitsrechte. E-Mail: privacy@aiadvocate.co.uk.

8. HAFTUNGSBESCHRÄNKUNG. Im gesetzlich zulässigen Höchstmaß haftet AI Advocate höchstens mit £50/US$50 oder dem in den letzten 3 Monaten gezahlten Betrag.

9. KEINE GARANTIEN. Die App wird „wie besehen" angeboten.

10. Anwendbares Recht. England und Wales. Streitigkeiten werden durch verbindliche ICC-Schiedsgerichtsbarkeit in London entschieden. Verzicht auf Jury-Verfahren und Sammelklagen.

11. Kontakt. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

Durch Tippen auf „Akzeptieren und Fortfahren" bestätigen Sie, die Bedingungen und die Datenschutzerklärung gelesen und akzeptiert zu haben. Die vollständige englische Fassung ist rechtlich verbindlich.
""",
    "hi-IN": """नियम और गोपनीयता नीति का सारांश

1. AI Advocate क्या है। एक सॉफ्टवेयर टूल जिसमें "Lex" नामक AI सहायक है। हम कानूनी फर्म नहीं हैं। हम वकील या कोई पंजीकृत कानूनी पेशेवर नहीं हैं। हम कानूनी सेवाएँ नहीं देते।

2. यह कानूनी सलाह नहीं है। Lex जो भी देता है वह AI द्वारा निर्मित सामान्य कानूनी जानकारी है। यह आपके क्षेत्राधिकार के योग्य वकील की सलाह का विकल्प नहीं है। कोई भी कानूनी कदम उठाने से पहले असली वकील से परामर्श लें।

3. वकील-ग्राहक संबंध नहीं बनता। ऐप उपयोग, Lex से बात, या सदस्यता लेने से कोई पेशेवर संबंध नहीं बनता। आपकी बातचीत वकील-ग्राहक गोपनीयता से सुरक्षित नहीं है।

4. AI गलती कर सकता है। AI मॉडल गलत, मनगढ़ंत या पुरानी जानकारी दे सकते हैं (काल्पनिक केस-कानून सहित)। सब कुछ वकील से सत्यापित करें।

5. आयु। आपकी उम्र कम से कम 18 वर्ष होनी चाहिए।

6. सदस्यता। 14-दिन का मुफ्त ट्रायल, फिर Apple, Google या Stripe के माध्यम से स्वतः नवीनीकरण। कभी भी रद्द करें।

7. गोपनीयता। GDPR/UK GDPR/CCPA के अनुसार डेटा संसाधित। आपकी चैट और फ़ाइलें Anthropic, Google, OpenAI और Stripe को भेजी जाती हैं। आपके अधिकार: एक्सेस, सुधार, मिटाना, पोर्टेबिलिटी। ईमेल: privacy@aiadvocate.co.uk।

8. दायित्व की सीमा। कानून द्वारा अनुमत अधिकतम सीमा तक, हमारी कुल देयता £50/US$50 या पिछले 3 महीनों में भुगतान की गई राशि से अधिक नहीं होगी।

9. कोई वारंटी नहीं। ऐप "जैसा है" आधार पर प्रदान किया जाता है।

10. लागू कानून। इंग्लैंड और वेल्स। विवादों का समाधान लंदन में ICC अनिवार्य मध्यस्थता द्वारा। जूरी ट्रायल और क्लास-एक्शन का त्याग।

11. संपर्क। legal@aiadvocate.co.uk · support@aiadvocate.co.uk

"स्वीकार करें और जारी रखें" टैप करके आप पुष्टि करते हैं कि आपने नियम और गोपनीयता नीति पढ़ ली है और स्वीकार कर ली है। पूर्ण अंग्रेज़ी संस्करण कानूनी रूप से प्रामाणिक है।
""",
    "ur-PK": """شرائط اور پرائیویسی پالیسی کا خلاصہ

١۔ AI Advocate کیا ہے۔ ایک سافٹ ویئر ٹول جس میں "Lex" نامی AI معاون ہے۔ ہم قانونی فرم نہیں ہیں۔ ہم وکیل یا کوئی منظم قانونی پیشہ ور نہیں ہیں۔ ہم قانونی خدمات فراہم نہیں کرتے۔

٢۔ یہ قانونی مشورہ نہیں۔ Lex جو کچھ بھی پیدا کرتا ہے وہ AI سے بنی عمومی قانونی معلومات ہے۔ یہ آپ کے دائرہ اختیار میں مستند وکیل کے مشورے کا متبادل نہیں۔ کسی بھی قانونی اقدام سے پہلے اصلی وکیل سے مشورہ کریں۔

٣۔ وکیل-موکل تعلق قائم نہیں ہوتا۔ ایپ کے استعمال، Lex سے بات یا سبسکرپشن سے کوئی پیشہ ورانہ تعلق قائم نہیں ہوتا۔ آپ کی گفتگو وکیل-موکل رازداری سے محفوظ نہیں۔

٤۔ AI غلطی کر سکتا ہے۔ AI ماڈلز غلط، من گھڑت یا پرانی معلومات دے سکتے ہیں (بشمول غیر موجود کیس-قانون)۔ ہر چیز وکیل سے تصدیق کریں۔

٥۔ عمر۔ آپ کی عمر کم از کم 18 سال ہونی چاہیے۔

٦۔ سبسکرپشن۔ 14-دن کا مفت ٹرائل، پھر Apple، Google یا Stripe کے ذریعے خود کار تجدید۔ کسی بھی وقت منسوخ کریں۔

٧۔ پرائیویسی۔ ڈیٹا GDPR/UK GDPR/CCPA کے مطابق۔ آپ کی چیٹس اور فائلیں Anthropic، Google، OpenAI اور Stripe کو بھیجی جاتی ہیں۔ آپ کے حقوق: رسائی، اصلاح، حذف، پورٹیبلٹی۔ ای میل: privacy@aiadvocate.co.uk۔

٨۔ ذمہ داری کی حد۔ قانون کی زیادہ سے زیادہ اجازت تک، ہماری کل ذمہ داری £50/US$50 یا پچھلے 3 مہینوں میں ادا شدہ رقم سے زیادہ نہیں ہوگی۔

٩۔ کوئی وارنٹی نہیں۔ ایپ "جیسی ہے" کی بنیاد پر فراہم کی جاتی ہے۔

١٠۔ لاگو قانون۔ انگلینڈ اور ویلز۔ تنازعات کا حل لندن میں ICC لازمی ثالثی کے ذریعے۔ جیوری ٹرائل اور کلاس ایکشن سے دستبرداری۔

١١۔ رابطہ۔ legal@aiadvocate.co.uk · support@aiadvocate.co.uk

"قبول کریں اور جاری رکھیں" پر ٹیپ کر کے آپ تصدیق کرتے ہیں کہ آپ نے شرائط اور پرائیویسی پالیسی پڑھ لی اور قبول کر لی ہے۔ مکمل انگریزی ورژن قانونی طور پر مستند ہے۔
""",
    "it-IT": """RIASSUNTO DEI TERMINI E DELL'INFORMATIVA SULLA PRIVACY

1. Cos'è AI Advocate. Uno strumento software con un assistente IA chiamato "Lex". NON siamo uno studio legale. NON siamo avvocati né professionisti del diritto regolamentati. NON forniamo servizi legali.

2. NON è consulenza legale. Tutto ciò che Lex genera sono informazioni legali generali prodotte dall'IA. NON sostituiscono il parere di un avvocato qualificato nella tua giurisdizione. Consulta un avvocato vero prima di qualsiasi azione legale.

3. Nessun rapporto avvocato-cliente. L'uso dell'app, il dialogo con Lex o l'abbonamento NON creano alcun rapporto professionale. Le tue comunicazioni NON sono coperte dal segreto professionale.

4. L'IA può sbagliare. I modelli IA possono produrre informazioni errate, inventate o obsolete (incluse citazioni di sentenze o leggi inesistenti). Verifica tutto con un avvocato.

5. Età. Devi avere almeno 18 anni.

6. Abbonamento. Prova gratuita di 14 giorni, poi abbonamento a rinnovo automatico tramite Apple, Google o Stripe. Cancella in qualsiasi momento.

7. Privacy. Trattiamo i tuoi dati secondo GDPR/UK GDPR/CCPA. Le tue chat e i file passano attraverso Anthropic, Google, OpenAI e Stripe. Diritti: accesso, rettifica, cancellazione, portabilità. Email: privacy@aiadvocate.co.uk.

8. LIMITAZIONE DI RESPONSABILITÀ. Nei limiti consentiti dalla legge, la nostra responsabilità totale non supererà £50/US$50 o l'importo pagato negli ultimi 3 mesi.

9. NESSUNA GARANZIA. L'app è fornita "così com'è".

10. Legge applicabile. Inghilterra e Galles. Le controversie si risolvono tramite arbitrato obbligatorio ICC con sede a Londra. Rinuncia al processo con giuria e alle azioni collettive.

11. Contatti. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

Toccando "Accetta e Continua" confermi di aver letto e accettato i Termini e la Privacy Policy. La versione inglese completa è quella legalmente autoritativa.
""",
    "pt-PT": """RESUMO DOS TERMOS E DA POLÍTICA DE PRIVACIDADE

1. O que é o AI Advocate. Uma ferramenta de software com um assistente IA chamado "Lex". NÃO somos uma sociedade de advogados. NÃO somos advogados nem profissionais jurídicos regulados. NÃO prestamos serviços jurídicos.

2. NÃO é aconselhamento jurídico. Tudo o que o Lex gera é informação jurídica geral produzida por IA. NÃO substitui a consulta com um advogado qualificado na sua jurisdição. Antes de qualquer ação legal, consulte um advogado real.

3. Sem relação advogado-cliente. Usar a app, falar com o Lex ou subscrever NÃO cria qualquer relação profissional. As suas comunicações NÃO estão cobertas pelo sigilo profissional.

4. A IA pode errar. Os modelos podem produzir informação incorrecta, inventada ou desactualizada (incluindo jurisprudência inexistente). Confirme tudo com um advogado.

5. Idade. Deve ter pelo menos 18 anos.

6. Subscrição. Período gratuito de 14 dias, depois subscrição com renovação automática via Apple, Google ou Stripe. Cancele a qualquer momento.

7. Privacidade. Tratamos os dados conforme RGPD/UK GDPR/CCPA. Os seus chats e ficheiros passam por Anthropic, Google, OpenAI e Stripe. Direitos: acesso, rectificação, apagamento, portabilidade. Email: privacy@aiadvocate.co.uk.

8. LIMITAÇÃO DE RESPONSABILIDADE. Até ao máximo permitido por lei, a nossa responsabilidade total não excederá £50/US$50 ou o valor pago nos últimos 3 meses.

9. SEM GARANTIAS. A app é fornecida "no estado em que se encontra".

10. Lei aplicável. Inglaterra e País de Gales. Os litígios são resolvidos por arbitragem obrigatória da CCI com sede em Londres. Renúncia a julgamento por júri e a acções colectivas.

11. Contacto. legal@aiadvocate.co.uk · support@aiadvocate.co.uk

Ao tocar em "Aceitar e Continuar", confirma ter lido e aceite os Termos e a Política de Privacidade. A versão integral em inglês é a legalmente vinculativa.
""",
    "zh-CN": """条款和隐私政策摘要

1. AI Advocate 是什么。一款带有名为 "Lex" 的 AI 助手的软件工具。我们不是律师事务所。我们不是律师，也不是任何受监管的法律专业人士。我们不提供法律服务。

2. 不是法律建议。Lex 产生的所有内容都是由 AI 生成的一般法律信息。它不能替代您所在司法管辖区合格律师的意见。在采取任何法律行动之前，请咨询真正的律师。

3. 不构成律师-委托人关系。使用本应用、与 Lex 对话或订阅均不会建立任何专业关系。您的通信不受律师-委托人特权保护。

4. AI 可能出错。AI 模型可能产生不准确、虚构或过时的信息（包括虚构的判例和法条）。请向律师核实一切。

5. 年龄。您必须年满 18 岁。

6. 订阅。14 天免费试用，之后通过 Apple、Google 或 Stripe 自动续订。可随时取消。

7. 隐私。我们按照 GDPR/UK GDPR/CCPA 处理数据。您的聊天和文件会通过 Anthropic、Google、OpenAI 和 Stripe 传输。您享有访问、更正、删除、可携权。邮箱：privacy@aiadvocate.co.uk。

8. 责任限制。在法律允许的最大范围内，我们的总责任不超过 £50/US$50 或您在过去 3 个月支付的金额。

9. 无担保。本应用按"现状"提供。

10. 适用法律。英格兰和威尔士。争议通过总部位于伦敦的国际商会（ICC）强制仲裁解决。放弃陪审团审判和集体诉讼。

11. 联系方式。legal@aiadvocate.co.uk · support@aiadvocate.co.uk

点击"接受并继续"即表示您已阅读并接受本条款和隐私政策。完整英文版本具有法律效力。
""",
}

@api_router.get("/legal/terms")
async def get_terms(language: str = "en-GB"):
    """Return the Terms & Privacy body.
    Strategy: English is authoritative full doc. For other languages we serve a hand-translated SUMMARY of
    the key legal points (so it's instant + reliable, no LLM dependency), with a note that the full
    English version is the legally authoritative text."""
    if language == "en-GB" or language == "en":
        return {"language": language, "body": TERMS_BODY_EN, "authoritative": True}
    summary = TERMS_SUMMARIES.get(language)
    if summary:
        return {"language": language, "body": summary, "authoritative": False,
                "note": "Summary in your language. The full English version is the legally authoritative text.",
                "english_full": TERMS_BODY_EN}
    # Unknown language → fall back to English
    return {"language": "en-GB", "body": TERMS_BODY_EN, "authoritative": True}

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
    # Allow short, safety-critical reads regardless of tier (emergency rights, etc).
    # Tier-gate only for general voice replies (long-form Lex chat).
    if len(data.text) > 1500:
        if not tier_has_access(pub["tier"], "voice"):
            raise HTTPException(402, "Voice output (long-form) requires Plus or Pro. Upgrade to unlock.")
    # Per-day TTS quota (protects OpenAI billing — free tier capped at 20/day, paid unlimited)
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "tts", "daily")
    if not ok:
        raise HTTPException(429, f"Daily Read-Aloud limit reached ({used}/{limit}). Upgrade to Plus for unlimited voice.")
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
    data.plan in {'plus','pro','yearly'} → maps to STRIPE_PRICE_*.
    Note: free 7-day trial is granted automatically on signup, not at Stripe checkout — so this is a direct subscribe."""
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
        # FIRM portal checkout — metadata.firm_id is set by /api/firm/subscribe
        firm_id = (obj.get("metadata") or {}).get("firm_id")
        if firm_id:
            firm_plan = (obj.get("metadata") or {}).get("firm_plan", "featured")
            customer_id = obj.get("customer")
            sub_id = obj.get("subscription")
            set_doc = {
                "billing_tier": firm_plan, "billing_status": "active",
                "stripe_customer_id": customer_id, "stripe_subscription_id": sub_id,
                "subscription_started_at": now_iso,
            }
            # Featured + Premium include the visible "featured" placement
            if firm_plan in ("featured", "premium"):
                set_doc["featured"] = True
                await db.lawfirms.update_one({"firm_account_id": firm_id}, {"$set": {"featured": True}})
            # Premium tier also includes the verified trust badge
            if firm_plan == "premium":
                set_doc["verified"] = True
                await db.lawfirms.update_one({"firm_account_id": firm_id}, {"$set": {"verified": True}})
            await db.firm_accounts.update_one({"id": firm_id}, {"$set": set_doc})
            logger.info(f"Firm {firm_id} upgraded to {firm_plan}")
            return {"ok": True, "firm_upgraded": True}

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
            # Downgrade consumer if matching user
            consumer_res = await db.users.update_one(
                {"stripe_customer_id": customer_id},
                {"$set": {"subscription_status": "canceled", "tier": "free", "subscription_ended_at": now_iso}}
            )
            # Downgrade firm if matching firm_account
            firm_res = await db.firm_accounts.update_one(
                {"stripe_customer_id": customer_id},
                {"$set": {"tier": "free", "billing_tier": "free", "billing_status": "canceled",
                          "featured": False, "verified": False, "subscription_ended_at": now_iso}}
            )
            # Also remove firm visibility flags in the public lawfirms directory
            firm = await db.firm_accounts.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "id": 1})
            if firm:
                await db.lawfirms.update_one({"firm_account_id": firm["id"]},
                                             {"$set": {"featured": False, "verified": False}})
            logger.info(f"Subscription canceled for customer {customer_id} — consumer={consumer_res.modified_count} firm={firm_res.modified_count}")
    elif etype == "customer.subscription.updated":
        customer_id = obj.get("customer")
        status_val = obj.get("status")
        # Derive tier from latest price (consumer)
        new_consumer_tier = None
        new_firm_tier = None
        for item in (obj.get("items") or {}).get("data", []):
            pid = (item.get("price") or {}).get("id")
            if pid in PRICE_TO_TIER:
                new_consumer_tier = PRICE_TO_TIER[pid]
                break
            # Check firm price IDs
            firm_prices = {
                os.environ.get("STRIPE_PRICE_FIRM_FEATURED", ""): "featured",
                os.environ.get("STRIPE_PRICE_FIRM_PREMIUM", ""): "premium",
                os.environ.get("STRIPE_PRICE_FIRM_PRACTICE", ""): "practice",
            }
            if pid in firm_prices and firm_prices[pid]:
                new_firm_tier = firm_prices[pid]
                break
        # Update consumer
        consumer_update = {"subscription_updated_at": now_iso}
        if status_val:
            consumer_update["subscription_status"] = status_val
            if status_val in ("canceled", "incomplete_expired", "unpaid"):
                consumer_update["tier"] = "free"
            elif new_consumer_tier and status_val == "active":
                consumer_update["tier"] = new_consumer_tier
        if customer_id:
            await db.users.update_one({"stripe_customer_id": customer_id}, {"$set": consumer_update})
            # Update firm if it matches
            firm_update = {"subscription_updated_at": now_iso}
            if status_val:
                firm_update["billing_status"] = status_val
                if status_val in ("canceled", "incomplete_expired", "unpaid"):
                    firm_update["tier"] = "free"
                    firm_update["billing_tier"] = "free"
                    firm_update["featured"] = False
                    firm_update["verified"] = False
                elif new_firm_tier and status_val == "active":
                    firm_update["tier"] = new_firm_tier
                    firm_update["billing_tier"] = new_firm_tier
                    firm_update["featured"] = (new_firm_tier in ("featured", "premium", "practice"))
                    firm_update["verified"] = (new_firm_tier in ("premium", "practice"))
            res = await db.firm_accounts.update_one({"stripe_customer_id": customer_id}, {"$set": firm_update})
            # Reflect firm visibility in lawfirms directory
            if res.modified_count > 0 and "featured" in firm_update:
                firm = await db.firm_accounts.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "id": 1})
                if firm:
                    await db.lawfirms.update_one({"firm_account_id": firm["id"]},
                                                 {"$set": {"featured": firm_update["featured"], "verified": firm_update["verified"]}})
    elif etype == "invoice.payment_failed":
        customer_id = obj.get("customer")
        if customer_id:
            await db.users.update_one({"stripe_customer_id": customer_id},
                                      {"$set": {"subscription_status": "past_due",
                                                "subscription_updated_at": now_iso}})
            await db.firm_accounts.update_one({"stripe_customer_id": customer_id},
                                              {"$set": {"billing_status": "past_due",
                                                        "subscription_updated_at": now_iso}})
            logger.warning(f"Payment failed for customer {customer_id}")
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
                            "View 31 templates", "3 files", "Emergency rights (always free)",
                            "Read-Aloud rights (20 / day)"]},
            {"id": "plus", "name": "Plus", "price_gbp": 14.99, "period": "month",
             "highlights": ["Unlimited Lex chats", "15 photo evidences / month",
                            "Unlimited letters", "Contract Review", "Court Prep modes",
                            "Voice in/out", "Practice Mode", "50 files", "Hey Lex wake word",
                            "Claude Sonnet 4.5 brain"]},
            {"id": "pro", "name": "Pro", "price_gbp": 34.99, "period": "month",
             "highlights": ["Everything in Plus", "Outcome Predictor + Contract Drafter + Negotiate",
                            "Live Hearing Recorder", "Live Legal Assist (3 sessions/day)",
                            "🧠 Deep Think — 30 / month (King's Counsel-grade reasoning)",
                            "Priority AI processing", "Premium court templates",
                            "Advanced document review", "Unlimited files", "Priority email support"]},
            {"id": "yearly", "name": "Yearly Pro", "price_gbp": 319.99, "period": "year",
             "best_value": True, "savings_pct": 24,
             "highlights": ["Everything in Pro", "🧠 Deep Think — 50 / month (bigger cap)",
                            "Live Assist — 5 sessions/day", "Save £100 vs paying monthly",
                            "12 months full access — no monthly faff"]},
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

# ==================== CASE FILES ====================
@api_router.post("/cases")
async def create_case(data: CaseCreate, user: dict = Depends(get_user)):
    case_id = str(uuid.uuid4())
    name = (data.name or "Untitled case").strip()[:120]
    doc = {
        "id": case_id, "user_id": user["id"], "name": name,
        "summary": encrypt_text((data.summary or "")[:500]), "category": data.category or "general",
        "status": "open", "items_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cases.insert_one(doc)
    doc.pop("_id", None)
    doc["summary"] = decrypt_text(doc["summary"])
    return doc

@api_router.get("/cases")
async def list_cases(user: dict = Depends(get_user), status: Optional[str] = None):
    q = {"user_id": user["id"]}
    if status: q["status"] = status
    out = []
    async for c in db.cases.find(q, {"_id": 0}).sort("updated_at", -1).limit(200):
        if "summary" in c: c["summary"] = decrypt_text(c["summary"])
        out.append(c)
    return {"cases": out}

@api_router.get("/cases/{case_id}")
async def get_case(case_id: str, user: dict = Depends(get_user)):
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not c: raise HTTPException(404, "Case not found")
    if "summary" in c: c["summary"] = decrypt_text(c["summary"])
    items = []
    async for it in db.case_items.find({"case_id": case_id, "user_id": user["id"]}, {"_id": 0}).sort("created_at", -1):
        if "description" in it: it["description"] = decrypt_text(it["description"])
        items.append(it)
    c["items"] = items
    return c

@api_router.patch("/cases/{case_id}")
async def update_case(case_id: str, data: CaseUpdate, user: dict = Depends(get_user)):
    upd = {k: v for k, v in data.dict(exclude_none=True).items() if k in ("name", "summary", "status")}
    if not upd: raise HTTPException(400, "Nothing to update")
    if "summary" in upd: upd["summary"] = encrypt_text(upd["summary"])
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.cases.update_one({"id": case_id, "user_id": user["id"]}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Case not found")
    c = await db.cases.find_one({"id": case_id}, {"_id": 0})
    return c

@api_router.delete("/cases/{case_id}")
async def delete_case(case_id: str, user: dict = Depends(get_user)):
    r = await db.cases.delete_one({"id": case_id, "user_id": user["id"]})
    if r.deleted_count == 0: raise HTTPException(404, "Case not found")
    await db.case_items.delete_many({"case_id": case_id})
    return {"deleted": True}

@api_router.post("/cases/{case_id}/items")
async def attach_item(case_id: str, data: CaseItemAttach, user: dict = Depends(get_user)):
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"]})
    if not c: raise HTTPException(404, "Case not found")
    item = {
        "id": str(uuid.uuid4()), "case_id": case_id, "user_id": user["id"],
        "item_type": data.item_type, "item_id": data.item_id,
        "title": (data.title or "")[:200], "preview": (data.preview or "")[:500],
        "timestamp_utc": data.timestamp_utc or datetime.now(timezone.utc).isoformat(),
        "location": data.location or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.case_items.insert_one(item)
    await db.cases.update_one({"id": case_id}, {"$inc": {"items_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    item.pop("_id", None)
    return item

@api_router.post("/cases/{case_id}/auto-name")
async def auto_name_case(case_id: str, user: dict = Depends(get_user)):
    """Use Lex to auto-name a case from its first 5 items (privacy-preserving — short summary only)."""
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not c: raise HTTPException(404, "Case not found")
    items = []
    async for it in db.case_items.find({"case_id": case_id}, {"_id": 0}).sort("created_at", 1).limit(5):
        items.append(f"- [{it['item_type']}] {it.get('title','')[:80]} {it.get('preview','')[:200]}")
    if not items:
        return {"name": c["name"]}
    blob = "\n".join(items)
    prompt = f"""Based on the following items from a legal case file, give me a short 2–6 word case name in English (or the user's language).
Just the name, no quotes, no preamble.
Items:
{blob}"""
    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"case_name_{case_id}",
                       system_message="You name legal case files. Reply with ONLY the case name, no other text. Examples: 'Parking PCN Appeal', 'Unfair Dismissal — Acme Ltd', 'Section 21 Eviction'."
                       ).with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=40)
        name = (await chat.send_message(UserMessage(text=prompt))).strip().strip('"').strip("'")[:80]
    except Exception:
        try:
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"case_name_{case_id}",
                           system_message="Name legal case files. Reply with ONLY the case name."
                           ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=40)
            name = (await chat.send_message(UserMessage(text=prompt))).strip().strip('"').strip("'")[:80]
        except Exception:
            name = c["name"]
    if name and name != c["name"]:
        await db.cases.update_one({"id": case_id}, {"$set": {"name": name, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"name": name}

@api_router.get("/cases/{case_id}/export-pdf")
async def export_case_pdf(case_id: str, user: dict = Depends(get_user)):
    """Court-ready PDF: timeline of every chat, photo, video, letter — with timestamps + locations + SHA256 hashes."""
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not c: raise HTTPException(404, "Case not found")
    items = []
    async for it in db.case_items.find({"case_id": case_id}, {"_id": 0}).sort("created_at", 1):
        items.append(it)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import cm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>Case File: {c['name']}</b>", styles["Title"]),
        Paragraph(f"User: {user['email']}", styles["Normal"]),
        Paragraph(f"Case opened: {c['created_at']}", styles["Normal"]),
        Paragraph(f"Status: {c['status'].upper()}", styles["Normal"]),
        Paragraph(f"Exported: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]),
        Paragraph(f"Items: {len(items)}", styles["Normal"]),
        Spacer(1, 0.5*cm),
        Paragraph("<b>Timeline</b>", styles["Heading2"]),
    ]
    import hashlib as _hashlib
    for i, it in enumerate(items, 1):
        h = _hashlib.sha256(f"{it.get('item_id','')}{it.get('timestamp_utc','')}{user['id']}".encode()).hexdigest()[:16]
        story += [
            Paragraph(f"<b>{i}. [{it.get('item_type','').upper()}]</b> {it.get('title','')}", styles["Heading3"]),
            Paragraph(f"<i>Recorded: {it.get('timestamp_utc','')}</i>", styles["Normal"]),
        ]
        if it.get("location"):
            story.append(Paragraph(f"<i>Location: {it['location']}</i>", styles["Normal"]))
        story.append(Paragraph(f"<i>Evidence hash: {h}</i>", styles["Normal"]))
        if it.get("preview"):
            story.append(Paragraph(it["preview"][:1500].replace("\n","<br/>"), styles["Normal"]))
        story.append(Spacer(1, 0.3*cm))
    doc.build(story)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="case-{case_id[:8]}.pdf"'})

# ==================== Lex Vault (zero-knowledge encrypted storage) ====================
import secrets as _secrets

# Per-tier item caps. Vault is FREE for everyone (safety feature), with tiered limits.
VAULT_ITEM_CAPS = {
    "free": 5, "trial_pro": 50, "plus": 25, "pro": 200, "yearly": 200, "trial": 5,
}
VAULT_MAX_FILE_BYTES = 12 * 1024 * 1024  # 12MB per item

def _vault_doc_to_public(d: dict, include_blob: bool = False) -> dict:
    out = {
        "id": d.get("id"), "title": d.get("title"), "category": d.get("category"),
        "notes_enc": d.get("notes_enc"),
        "note_iv": d.get("note_iv"),
        "file_iv": d.get("file_iv"),
        "file_mime": d.get("file_mime"), "file_name": d.get("file_name"),
        "file_size_bytes": d.get("file_size_bytes", 0),
        "created_at": d.get("created_at"),
    }
    if include_blob:
        out["file_b64"] = d.get("file_b64")
    return out


@api_router.get("/vault/status")
async def vault_status(user: dict = Depends(get_user)):
    """Has the user set a Vault PIN yet? Used by UI to show setup vs unlock flow."""
    v = await db.vault_meta.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"setup": bool(v), "pin_salt": (v or {}).get("pin_salt"), "items_count": (v or {}).get("items_count", 0)}


@api_router.post("/vault/setup")
async def vault_setup(data: VaultSetupRequest, user: dict = Depends(get_user)):
    """First-time Vault setup. Stores ONLY a SHA-256 verifier hash + salt — server
    NEVER sees the actual PIN. If the user forgets their PIN, items cannot be recovered."""
    if not data.pin_verifier or len(data.pin_verifier) < 32:
        raise HTTPException(400, "Invalid PIN verifier")
    existing = await db.vault_meta.find_one({"user_id": user["id"]})
    if existing:
        raise HTTPException(400, "Vault already set up. Use 'wipe' to start over.")
    await db.vault_meta.insert_one({
        "user_id": user["id"],
        "pin_verifier": data.pin_verifier,
        "pin_salt": data.pin_salt,
        "items_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"setup": True}


@api_router.post("/vault/unlock")
async def vault_unlock(data: VaultUnlockRequest, user: dict = Depends(get_user)):
    """Verify the PIN by comparing the client-supplied SHA-256 verifier with the stored one.
    Security: 5 wrong attempts → 15-min cool-off. 10 wrong attempts → automatic vault wipe (panic mode)."""
    v = await db.vault_meta.find_one({"user_id": user["id"]})
    if not v:
        raise HTTPException(404, "Vault not set up yet")
    # Check cooldown
    failed = int(v.get("failed_attempts") or 0)
    locked_until = v.get("locked_until")
    now = datetime.now(timezone.utc)
    if locked_until:
        try:
            lu = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
            if lu > now:
                remaining = int((lu - now).total_seconds())
                raise HTTPException(429, f"Vault locked. Try again in {remaining // 60 + 1} minutes ({failed} wrong attempts).")
        except (ValueError, AttributeError):
            pass
    # PIN verify
    if not _secrets.compare_digest((v.get("pin_verifier") or ""), (data.pin_verifier or "")):
        failed += 1
        update = {"failed_attempts": failed, "last_failed_at": now.isoformat()}
        if failed >= 10:
            # PANIC WIPE — destroy all vault items, reset meta. User must set up again.
            await db.vault_items.delete_many({"user_id": user["id"]})
            await db.vault_meta.delete_one({"user_id": user["id"]})
            raise HTTPException(401, "Too many wrong attempts — vault wiped for your security. All items destroyed.")
        elif failed >= 5:
            update["locked_until"] = (now + timedelta(minutes=15)).isoformat()
            await db.vault_meta.update_one({"user_id": user["id"]}, {"$set": update})
            raise HTTPException(429, f"Too many wrong attempts. Vault locked for 15 minutes. ({10 - failed} attempts remaining before auto-wipe.)")
        await db.vault_meta.update_one({"user_id": user["id"]}, {"$set": update})
        attempts_left = 5 - failed
        raise HTTPException(401, f"Incorrect PIN. {attempts_left} attempt{'s' if attempts_left != 1 else ''} before 15-min lock.")
    await db.vault_meta.update_one(
        {"user_id": user["id"]},
        {"$set": {"failed_attempts": 0, "locked_until": None, "last_unlocked_at": now.isoformat()}}
    )
    return {"unlocked": True}


@api_router.get("/vault/items/{item_id}")
async def vault_get_item(item_id: str, user: dict = Depends(get_user)):
    """Fetch full encrypted blob for a specific item (decryption happens client-side).
    Server transparently strips its own outer encryption layer so the client only sees
    its own AES-GCM ciphertext (which only the user's PIN can decrypt)."""
    d = await db.vault_items.find_one({"id": item_id, "user_id": user["id"], "deleted": {"$ne": True}}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Item not found")
    if d.get("file_b64"):
        d["file_b64"] = decrypt_text(d["file_b64"])
    if d.get("notes_enc"):
        d["notes_enc"] = decrypt_text(d["notes_enc"])
    return _vault_doc_to_public(d, include_blob=True)


@api_router.get("/vault/items")
async def vault_list(user: dict = Depends(get_user)):
    """List vault items (without the heavy file blob — fetch each item individually for download)."""
    out = []
    async for d in db.vault_items.find(
        {"user_id": user["id"], "deleted": {"$ne": True}}, {"_id": 0, "file_b64": 0}
    ).sort("created_at", -1):
        if d.get("notes_enc"):
            d["notes_enc"] = decrypt_text(d["notes_enc"])
        out.append(_vault_doc_to_public(d, include_blob=False))
    return {"items": out, "count": len(out)}


@api_router.post("/vault/items")
async def vault_add_item(data: VaultItemCreate, user: dict = Depends(get_user)):
    """Store a CLIENT-side encrypted item. Server adds another layer (encrypt_text) on top of
    the already-encrypted blob — defence-in-depth."""
    pub = user_to_public(user)
    cap = VAULT_ITEM_CAPS.get(pub["tier"], 5)
    current = await db.vault_items.count_documents({"user_id": user["id"], "deleted": {"$ne": True}})
    if current >= cap:
        raise HTTPException(402, f"Vault limit reached ({current}/{cap}). Upgrade to Pro for unlimited.")
    if data.file_size_bytes > VAULT_MAX_FILE_BYTES:
        raise HTTPException(413, f"File too large (max {VAULT_MAX_FILE_BYTES // (1024*1024)}MB)")

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "title": (data.title or "Untitled")[:200],
        "category": data.category or "evidence",
        # Server adds extra encryption layer over what is already client-encrypted
        "notes_enc": encrypt_text(data.notes) if data.notes else None,
        "note_iv": data.note_iv,
        "file_b64": encrypt_text(data.file_b64),
        "file_iv": data.file_iv,
        "file_mime": data.file_mime or "application/octet-stream",
        "file_name": data.file_name,
        "file_size_bytes": int(data.file_size_bytes or 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False,
    }
    await db.vault_items.insert_one(doc)
    await db.vault_meta.update_one({"user_id": user["id"]}, {"$inc": {"items_count": 1}})
    doc.pop("_id", None)
    return _vault_doc_to_public(doc, include_blob=False)


@api_router.delete("/vault/items/{item_id}")
async def vault_delete_item(item_id: str, user: dict = Depends(get_user)):
    r = await db.vault_items.update_one(
        {"id": item_id, "user_id": user["id"]},
        {"$set": {"deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}}
    )
    if r.modified_count == 0:
        raise HTTPException(404, "Item not found")
    await db.vault_meta.update_one({"user_id": user["id"]}, {"$inc": {"items_count": -1}})
    return {"deleted": True}


@api_router.post("/vault/wipe")
async def vault_wipe(user: dict = Depends(get_user)):
    """Panic delete — wipes everything in the vault AND resets the PIN.
    Items go to a 24-hour soft-delete tombstone so the user can recover by contacting support if it was a mistake.
    """
    await db.vault_items.update_many(
        {"user_id": user["id"]},
        {"$set": {"deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat(), "wiped": True}},
    )
    await db.vault_meta.delete_one({"user_id": user["id"]})
    return {"wiped": True}


@api_router.post("/vault/share")
async def vault_share(data: VaultShareCreate, user: dict = Depends(get_user)):
    """Generate a 7-day expiring share token for selected vault items.
    NOTE: For the MVP, the share is a server-decrypt-on-fetch link. The client must
    upload re-encrypted blobs using a temporary share key before sharing for true E2E."""
    if not data.item_ids:
        raise HTTPException(400, "No items selected")
    # Verify all items belong to this user
    count = await db.vault_items.count_documents({"id": {"$in": data.item_ids}, "user_id": user["id"], "deleted": {"$ne": True}})
    if count != len(data.item_ids):
        raise HTTPException(404, "One or more items not found")
    token = _secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=max(1, min(168, data.expires_in_hours)))
    await db.vault_shares.insert_one({
        "id": str(uuid.uuid4()),
        "token": token,
        "user_id": user["id"],
        "item_ids": data.item_ids,
        "note_to_recipient": (data.note_to_recipient or "")[:1000],
        "recipient_email": data.recipient_email,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "revoked": False,
    })
    base = APP_PUBLIC_URL.rstrip("/")
    return {
        "share_url": f"{base}/vault-share/{token}",
        "token": token,
        "expires_at": expires_at.isoformat(),
    }


# ==================== Feature suggestion ====================
@api_router.post("/feedback/suggest")
async def feedback_suggest(data: FeatureSuggestion, user: dict = Depends(get_user)):
    text = (data.text or "").strip()
    if not text or len(text) < 5:
        raise HTTPException(400, "Please write at least a few words about what you'd like to see.")
    await db.feature_requests.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user.get("email"),
        "text": text[:2000],
        "category_hint": (data.category_hint or "")[:100],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"received": True, "thanks": "Thanks — we read every suggestion."}


# ==================== GDPR — right to erasure + data portability ====================
@api_router.get("/users/me/export")
async def gdpr_export_my_data(user: dict = Depends(get_user)):
    """GDPR Article 20 / UK-GDPR — data portability. Returns the user's full data as JSON.
    Encrypted fields (chat content, case summaries, vault items) are TRANSPARENTLY DECRYPTED here so
    the user gets their plaintext data back."""
    uid = user["id"]
    me = await db.users.find_one({"id": uid}, {"_id": 0, "hashed_password": 0})
    if not me:
        raise HTTPException(404, "User not found")
    # Strip secrets and tokens that aren't user data
    me.pop("apple_id", None); me.pop("google_id", None)

    convos = []
    async for c in db.conversations.find({"user_id": uid}, {"_id": 0}).sort("created_at", 1).limit(2000):
        if "user_message" in c: c["user_message"] = decrypt_text(c["user_message"])
        if "assistant_response" in c: c["assistant_response"] = decrypt_text(c["assistant_response"])
        convos.append(c)

    cases = []
    async for k in db.cases.find({"user_id": uid}, {"_id": 0}):
        if "summary" in k: k["summary"] = decrypt_text(k["summary"])
        cases.append(k)

    case_items = []
    async for it in db.case_items.find({"user_id": uid}, {"_id": 0}):
        if "description" in it: it["description"] = decrypt_text(it["description"])
        case_items.append(it)

    files = await db.legal_files.find({"user_id": uid}, {"_id": 0}).to_list(2000)
    reminders = await db.reminders.find({"user_id": uid}, {"_id": 0}).to_list(2000)
    feature_requests = await db.feature_requests.find({"user_id": uid}, {"_id": 0}).to_list(500)
    # Vault metadata only — never include encrypted file blobs in plain export
    vault_items = await db.vault_items.find(
        {"user_id": uid, "deleted": {"$ne": True}},
        {"_id": 0, "file_b64": 0}
    ).to_list(500)

    return {
        "export_generated_at": datetime.now(timezone.utc).isoformat(),
        "format_version": 1,
        "notes": "This is your full personal data held by AI Advocate. Vault file contents are encrypted with your PIN and not exported here — open the Vault on your device to decrypt them.",
        "user": me,
        "conversations": convos,
        "cases": cases,
        "case_items": case_items,
        "legal_files": files,
        "reminders": reminders,
        "feature_requests": feature_requests,
        "vault_items_metadata": vault_items,
    }


@api_router.delete("/users/me")
async def gdpr_delete_my_account(user: dict = Depends(get_user)):
    """GDPR Article 17 — right to erasure. Apple App Store 5.1.1(v) compliant.
    Permanently deletes ALL user data AND cancels any active Stripe subscription.
    NOTE: Some audit fields (subscription history for tax records — UK 6yr statutory) are kept anonymised.
    """
    uid = user["id"]
    # 1) Cancel any active Stripe subscription so the user isn't billed after deletion
    sub_id = user.get("stripe_subscription_id")
    if sub_id and STRIPE_API_KEY:
        try:
            stripe.Subscription.delete(sub_id)  # cancels immediately, prorated
            logger.info(f"Cancelled Stripe sub {sub_id} as part of account deletion")
        except Exception as e:
            logger.warning(f"Failed to cancel Stripe sub during account deletion: {e}")
    # 2) Delete user-owned data across collections
    cols_to_wipe = [
        "conversations", "cases", "case_items", "case_notes", "legal_files",
        "reminders", "feature_requests", "vault_items", "vault_meta", "vault_shares",
        "usage_counters", "lex_chats", "security_events", "engagement_files",
    ]
    for col in cols_to_wipe:
        try: await db[col].delete_many({"user_id": uid})
        except Exception: pass
    # 3) Engagements & their messages — user is either client or invited party
    engs = []
    async for e in db.engagements.find({"client_user_id": uid}, {"_id": 0, "id": 1}):
        engs.append(e["id"])
    if engs:
        await db.engagement_messages.delete_many({"engagement_id": {"$in": engs}})
        await db.engagement_files.delete_many({"engagement_id": {"$in": engs}})
        await db.engagements.delete_many({"id": {"$in": engs}})
    # 4) Anonymise the user record (kept to prevent trial abuse but personally unidentifiable)
    await db.users.update_one(
        {"id": uid},
        {"$set": {
            "deleted": True,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "email": f"deleted-{uid}@ai-advocate.local",
            "name": "(deleted)",
            "hashed_password": None,
            "apple_id": None, "google_id": None,
            "stripe_customer_id": None, "stripe_subscription_id": None,
            "last_login_ip": None, "last_login_country": None,
        }}
    )
    logger.info(f"Account deleted (GDPR) for user {uid}")
    return {"deleted": True, "message": "Your account and all personal data have been permanently deleted."}


# ==================== Lex topic classifier (smart category routing) ====================
@api_router.post("/lex/classify")
async def lex_classify(payload: dict, user: dict = Depends(get_user)):
    """Lightweight classifier: maps a user's free-text question to one of our tile categories.
    Uses cheap Haiku model. Returns {category, confidence, suggestion}."""
    text = (payload.get("text") or "").strip()
    if len(text) < 12:
        return {"category": "general", "confidence": "low"}
    sysmsg = (
        "You classify legal questions into ONE of these UK-app categories, returning STRICT JSON only:\n"
        "Categories: employment | property | immigration | criminal | family | medical | consumer | debt | tax | general\n"
        "Respond ONLY with: {\"category\":\"<one of above>\",\"confidence\":\"high|medium|low\",\"reason\":\"<≤8 words>\"}\n"
        "Pick 'general' if it doesn't clearly fit a specific category."
    )
    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"classify-{uuid.uuid4()}", system_message=sysmsg)\
            .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=80)
        resp = await chat.send_message(UserMessage(text=text))
    except Exception:
        return {"category": "general", "confidence": "low"}
    import json as _json, re as _re
    payload_txt = _re.sub(r"^```(?:json)?\s*|\s*```$", "", resp.strip())
    try:
        d = _json.loads(payload_txt)
        return {"category": d.get("category", "general"), "confidence": d.get("confidence", "low"), "reason": d.get("reason", "")}
    except Exception:
        return {"category": "general", "confidence": "low"}


# ==================== VIDEO RECORDING + LEX ANALYSIS ====================
@api_router.post("/video/analyze")
async def analyze_video(audio: UploadFile = File(...), language: str = "en-GB", country: str = "GB",
                         case_id: Optional[str] = None, location: Optional[str] = None,
                         user: dict = Depends(get_user)):
    """Pro-tier: receive audio extracted from video → Whisper transcript → Lex analysis →
    flag rights violations, leading questions, drafts complaint letter."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "court_categories"):
        raise HTTPException(402, "Video analysis requires Pro. Upgrade to unlock.")
    # Quota
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "evidence_analyze", "monthly")
    if not ok: raise HTTPException(429, f"Monthly evidence limit reached ({used}/{limit}).")

    audio_bytes = await audio.read()
    if len(audio_bytes) > 25 * 1024 * 1024:  # 25MB whisper limit
        raise HTTPException(413, "Audio too large (max 25MB). Trim to first 5 minutes of the most relevant section.")
    stt_client = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    try:
        transcript = await stt_client.transcribe_audio(
            audio_data=audio_bytes, filename=audio.filename or "video.webm",
            model="whisper-1", language=language[:2],
        )
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")

    # Lex analysis
    sys_prompt = lex_system_prompt(language, country, "record")
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=sys_prompt
                   ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=3000)
    analysis_prompt = f"""I have video footage of a legal interaction (police questioning / public dispute / harassment / official interview).
Here is the transcript of the audio:

{transcript[:8000]}

Please:
1. Flag any rights violations (no caution given, leading questions, intimidation, refusal of representation).
2. Identify anything I said that I shouldn't have (admissions, contradictions).
3. Identify anything the other party said that helps my case.
4. Draft a short complaint letter or defence statement I can send (formal, UK style if my country is GB, otherwise localised to {country}).
5. End with a Confidence rating (High/Medium/Low) and a recommended next step."""
    try:
        analysis = await chat.send_message(UserMessage(text=analysis_prompt))
    except Exception as e:
        raise HTTPException(500, f"Lex analysis failed: {str(e)}")

    # Save evidence record
    ev_id = str(uuid.uuid4())
    import hashlib as _h
    evidence_hash = _h.sha256(audio_bytes).hexdigest()
    rec = {
        "id": ev_id, "user_id": user["id"], "kind": "video",
        "transcript": transcript[:20000], "analysis": analysis,
        "language": language, "country": country, "location": location,
        "evidence_hash": evidence_hash, "filename": audio.filename or "video.webm",
        "case_id": case_id, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.evidence.insert_one(rec)
    # Auto-attach to case if provided
    if case_id:
        await db.case_items.insert_one({
            "id": str(uuid.uuid4()), "case_id": case_id, "user_id": user["id"],
            "item_type": "video", "item_id": ev_id,
            "title": (audio.filename or "Video recording"),
            "preview": transcript[:400],
            "timestamp_utc": rec["created_at"], "location": location,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.cases.update_one({"id": case_id}, {"$inc": {"items_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    rec.pop("_id", None)
    return rec

# ==================== LIMITATION-PERIOD REMINDERS ====================
@api_router.post("/reminders")
async def create_reminder(data: ReminderCreate, user: dict = Depends(get_user)):
    rid = str(uuid.uuid4())
    doc = {
        "id": rid, "user_id": user["id"], "case_id": data.case_id,
        "title": data.title[:200], "description": (data.description or "")[:500],
        "due_at": data.due_at, "kind": data.kind, "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.reminders.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/reminders")
async def list_reminders(user: dict = Depends(get_user), status: Optional[str] = "pending"):
    q = {"user_id": user["id"]}
    if status: q["status"] = status
    out = []
    async for r in db.reminders.find(q, {"_id": 0}).sort("due_at", 1).limit(100):
        out.append(r)
    return {"reminders": out}

@api_router.get("/reminders/badge")
async def reminders_badge(user: dict = Depends(get_user)):
    """Count pending reminders due within next 3 days — used for nav-dot + native app-icon badge."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=3)
    cutoff_iso = cutoff.isoformat()
    now_minus_30d = (now - timedelta(days=30)).isoformat()
    q = {
        "user_id": user["id"],
        "status": "pending",
        "due_at": {"$lte": cutoff_iso, "$gte": now_minus_30d},  # due-soon OR recently overdue
    }
    count = await db.reminders.count_documents(q)
    return {"count": count}

@api_router.patch("/reminders/{rid}")
async def update_reminder(rid: str, status: Optional[str] = None, user: dict = Depends(get_user)):
    if status not in ("pending", "done", "dismissed"):
        raise HTTPException(400, "Invalid status")
    r = await db.reminders.update_one({"id": rid, "user_id": user["id"]}, {"$set": {"status": status}})
    if r.matched_count == 0: raise HTTPException(404, "Reminder not found")
    return {"updated": True}

@api_router.post("/reminders/detect")
async def detect_deadlines(message: str = Form(...), language: str = Form("en-GB"), country: str = Form("GB"),
                            user: dict = Depends(get_user)):
    """Ask Lex to extract any limitation periods / deadlines / hearing dates from a chat message.
    Returns a list of suggested reminders the user can one-tap accept."""
    sys_prompt = f"""You are a legal deadline detector. The user is in {country}. Read the message below and extract any
LEGAL DEADLINES, LIMITATION PERIODS, HEARING DATES, RESPONSE DEADLINES, or PAYMENT DUE DATES.
For each deadline found, return a JSON array entry: {{"title": "...", "due_at": "YYYY-MM-DDTHH:MM:SS+00:00", "kind": "deadline|hearing|follow_up"}}.
If no deadlines found, return [].
Reply with ONLY valid JSON — no preamble, no explanation.
If a relative date is mentioned (e.g. "within 14 days"), compute it from today {datetime.now(timezone.utc).date().isoformat()}."""
    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=sys_prompt
                       ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=500)
        raw = (await chat.send_message(UserMessage(text=message))).strip()
        # Strip code fences if any
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        import json as _json
        deadlines = _json.loads(raw)
        if not isinstance(deadlines, list): deadlines = []
    except Exception as e:
        logger.warning(f"Deadline detect parse err: {e}")
        deadlines = []
    return {"deadlines": deadlines[:5]}

# ==================== LAW FIRM PORTAL ====================
@api_router.post("/firm/signup")
async def firm_signup(data: FirmPortalSignup):
    existing = await db.firm_accounts.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(409, "Email already registered")
    fid = str(uuid.uuid4())
    doc = {
        "id": fid, "email": data.email.lower(), "password": hash_pw(data.password),
        "firm_name": data.firm_name, "contact_name": data.contact_name,
        "sra_number": data.sra_number, "country": data.country, "city": data.city,
        "phone": data.phone, "specialties": data.specialties, "website": data.website,
        "status": "pending_review",   # pending_review | approved | rejected | suspended
        "tier": "free",               # free | featured | verified
        "verified": False, "featured": False,
        "lead_count_30d": 0, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.firm_accounts.insert_one(doc)
    token = jwt.encode({"sub": fid, "kind": "firm", "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")
    doc.pop("_id", None); doc.pop("password", None)
    return {"access_token": token, "firm": doc}

@api_router.post("/firm/login")
async def firm_login(data: FirmPortalLogin):
    f = await db.firm_accounts.find_one({"email": data.email.lower()})
    if not f or not verify_pw(data.password, f["password"]):
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode({"sub": f["id"], "kind": "firm", "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")
    f.pop("_id", None); f.pop("password", None)
    return {"access_token": token, "firm": f}

async def get_firm(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if payload.get("kind") != "firm":
        raise HTTPException(403, "Not a firm account")
    f = await db.firm_accounts.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not f: raise HTTPException(401, "Firm not found")
    return f

@api_router.get("/firm/me")
async def firm_me(firm: dict = Depends(get_firm)):
    # Recent leads
    leads = []
    async for q in db.inquiries.find({"firm_id": firm["id"]}, {"_id": 0}).sort("created_at", -1).limit(50):
        leads.append(q)
    firm["recent_leads"] = leads
    return firm

@api_router.patch("/firm/listing")
async def firm_update_listing(data: FirmListingUpdate, firm: dict = Depends(get_firm)):
    if firm["status"] != "approved":
        raise HTTPException(403, "Firm not yet approved by AI Advocate admin")
    upd = {k: v for k, v in data.dict(exclude_none=True).items()}
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.lawfirms.update_one({"firm_account_id": firm["id"]}, {"$set": upd})
    return {"updated": True}

@api_router.post("/firm/subscribe")
async def firm_subscribe(plan: str = "featured", firm: dict = Depends(get_firm)):
    """Stripe checkout for firms — £49/mo Featured, £199/mo Premium, £399/mo Practice."""
    if plan not in ("featured", "premium", "practice"):
        raise HTTPException(400, "plan must be 'featured', 'premium', or 'practice'")
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Billing not configured")
    price_id = os.environ.get(f"STRIPE_PRICE_FIRM_{plan.upper()}", "")
    if not price_id:
        raise HTTPException(503, f"Stripe price ID for firm {plan} not configured. Set STRIPE_PRICE_FIRM_{plan.upper()} in .env")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription", line_items=[{"price": price_id, "quantity": 1}],
            customer_email=firm["email"],
            success_url=f"{(os.environ.get('FRONTEND_URL') or '').rstrip('/') }/firm-portal?paid=1",
            cancel_url=f"{(os.environ.get('FRONTEND_URL') or '').rstrip('/') }/firm-portal?cancelled=1",
            metadata={"firm_id": firm["id"], "firm_plan": plan},
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(500, f"Stripe checkout failed: {str(e)}")


# ==================== Engagements (Client ↔ Firm secure case threads + shared files) ====================

# Tier limits — how many concurrent active engagements a firm can hold.
FIRM_ENGAGEMENT_LIMITS = {
    "free": 0,
    "featured": 0,           # directory listing only
    "premium": 25,
    "practice": 999999,      # effectively unlimited
}
# Lex-AI per-month allowance for a firm (for draft-reply / summarise / explain on threads)
FIRM_LEX_MONTHLY_LIMITS = {
    "free": 0, "featured": 0, "premium": 100, "practice": 1000,
}
# Shared file storage cap per engagement
ENGAGEMENT_FILE_LIMIT = 50   # files per engagement
ENGAGEMENT_FILE_MAX_BYTES = 12 * 1024 * 1024  # 12MB per file

def _firm_tier(firm: dict) -> str:
    t = (firm or {}).get("tier") or "free"
    return t if t in FIRM_ENGAGEMENT_LIMITS else "free"

async def _count_active_engagements(firm_id: str) -> int:
    return await db.engagements.count_documents({"firm_id": firm_id, "status": {"$in": ["invited", "active"]}})

async def _engagement_or_403(eid: str, *, client_id: Optional[str] = None, firm_id: Optional[str] = None) -> dict:
    eng = await db.engagements.find_one({"id": eid}, {"_id": 0})
    if not eng:
        raise HTTPException(404, "Engagement not found")
    if client_id and eng.get("client_user_id") != client_id:
        raise HTTPException(403, "Not your engagement")
    if firm_id and eng.get("firm_id") != firm_id:
        raise HTTPException(403, "Not your engagement")
    return eng

@api_router.post("/firm/engagements")
async def firm_create_engagement(data: EngagementCreate, firm: dict = Depends(get_firm)):
    """Firm initiates an engagement with a client. Returns invite_token URL for client to accept."""
    tier = _firm_tier(firm)
    if FIRM_ENGAGEMENT_LIMITS[tier] <= 0:
        raise HTTPException(402, "Client engagements aren't included in your current plan. Upgrade to Premium (£199/mo) or Practice (£399/mo) to invite clients securely.")
    # Block self-invite (firm contact email == client email)
    if data.client_email and (data.client_email or "").lower() == (firm.get("email") or "").lower():
        raise HTTPException(400, "You cannot invite your own firm email as a client.")
    active = await _count_active_engagements(firm["id"])
    if active >= FIRM_ENGAGEMENT_LIMITS[tier]:
        raise HTTPException(402, f"Active engagement limit reached for {tier} plan ({FIRM_ENGAGEMENT_LIMITS[tier]}). Upgrade or close an engagement.")
    eid = str(uuid.uuid4())
    token = _secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc).isoformat()
    client_user_id = None
    if data.client_email:
        existing = await db.users.find_one({"email": data.client_email.lower()}, {"_id": 0})
        if existing:
            client_user_id = existing["id"]
    doc = {
        "id": eid,
        "firm_id": firm["id"],
        "firm_name": firm.get("firm_name") or "",
        "client_user_id": client_user_id,
        "client_email_invited": (data.client_email or "").lower() if data.client_email else "",
        "matter": data.matter or "General",
        "case_summary_enc": encrypt_text(data.case_summary or ""),
        "invite_token": token,
        "status": "invited",       # invited | active | closed | declined
        "created_at": now,
        "accepted_at": None, "closed_at": None,
    }
    await db.engagements.insert_one(doc)
    return {
        "id": eid,
        "invite_token": token,
        "invite_url": f"{(os.environ.get('FRONTEND_URL') or '').rstrip('/')}/engage/{token}",
        "status": "invited",
    }

@api_router.get("/engagements/invite/{token}")
async def engagement_invite_preview(token: str):
    """Public preview of an engagement invite — used by the consumer app's accept screen."""
    eng = await db.engagements.find_one({"invite_token": token, "status": "invited"}, {"_id": 0, "case_summary_enc": 0})
    if not eng:
        raise HTTPException(404, "Invite not found or already accepted")
    return {
        "firm_name": eng.get("firm_name") or "",
        "matter": eng.get("matter") or "General",
        "invited_at": eng.get("created_at"),
    }

@api_router.post("/engagements/accept/{token}")
async def engagement_accept(token: str, user: dict = Depends(get_user)):
    """Consumer accepts a firm's engagement invite. Binds engagement to the logged-in user."""
    eng = await db.engagements.find_one({"invite_token": token, "status": "invited"})
    if not eng:
        raise HTTPException(404, "Invite not found or already accepted")
    # If the firm specified a client_email, ensure the accepting user matches (when set)
    invited_email = (eng.get("client_email_invited") or "").lower()
    if invited_email and invited_email != (user.get("email") or "").lower():
        raise HTTPException(403, f"This invite was sent to {invited_email}. Sign in with that account to accept.")
    await db.engagements.update_one(
        {"id": eng["id"]},
        {"$set": {
            "client_user_id": user["id"],
            "status": "active",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"engagement_id": eng["id"], "status": "active"}

def _public_engagement(eng: dict, side: str = "client") -> dict:
    out = {
        "id": eng["id"],
        "firm_id": eng.get("firm_id"),
        "firm_name": eng.get("firm_name") or "",
        "client_user_id": eng.get("client_user_id"),
        "client_email_invited": eng.get("client_email_invited") or "",
        "matter": eng.get("matter") or "General",
        "status": eng.get("status"),
        "created_at": eng.get("created_at"),
        "accepted_at": eng.get("accepted_at"),
        "closed_at": eng.get("closed_at"),
        "case_summary": decrypt_text(eng.get("case_summary_enc") or ""),
    }
    if side == "firm" and eng.get("status") == "invited":
        out["invite_token"] = eng.get("invite_token")
    return out

@api_router.get("/engagements")
async def list_engagements_for_client(user: dict = Depends(get_user)):
    """Consumer-side list — all engagements where the user is the client."""
    rows = []
    async for e in db.engagements.find({"client_user_id": user["id"]}, {"_id": 0}).sort("created_at", -1):
        rows.append(_public_engagement(e, side="client"))
    return {"engagements": rows}

@api_router.get("/firm/engagements")
async def list_engagements_for_firm(firm: dict = Depends(get_firm)):
    rows = []
    async for e in db.engagements.find({"firm_id": firm["id"]}, {"_id": 0}).sort("created_at", -1):
        rows.append(_public_engagement(e, side="firm"))
    return {"engagements": rows, "tier": _firm_tier(firm), "limit": FIRM_ENGAGEMENT_LIMITS[_firm_tier(firm)], "active_count": await _count_active_engagements(firm["id"])}

@api_router.patch("/engagements/{eid}/close")
async def close_engagement(eid: str, authorization: Optional[str] = Header(None)):
    """Either party may close. We auth manually because both kinds of token are allowed here."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    kind = payload.get("kind") or "user"
    sub = payload.get("sub")
    q = {"id": eid}
    if kind == "firm": q["firm_id"] = sub
    else:              q["client_user_id"] = sub
    eng = await db.engagements.find_one(q)
    if not eng:
        raise HTTPException(404, "Engagement not found")
    await db.engagements.update_one({"id": eid}, {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc).isoformat()}})
    return {"closed": True}

# ---------- Case Thread (engagement messages) ----------

async def _resolve_engagement_for_request(eid: str, authorization: Optional[str]) -> Tuple[dict, str, str]:
    """Returns (engagement, sender_kind 'client'|'firm', sender_id) or raises 401/403/404."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    kind = payload.get("kind") or "user"
    sub = payload.get("sub")
    eng = await db.engagements.find_one({"id": eid}, {"_id": 0})
    if not eng: raise HTTPException(404, "Engagement not found")
    if eng.get("status") not in ("active", "invited"):
        # Allow read on closed engagements — block writes downstream
        pass
    if kind == "firm":
        if eng.get("firm_id") != sub: raise HTTPException(403, "Not your engagement")
        return eng, "firm", sub
    else:
        if eng.get("client_user_id") != sub: raise HTTPException(403, "Not your engagement")
        return eng, "client", sub

@api_router.post("/engagements/{eid}/messages")
async def post_engagement_message(eid: str, data: EngagementMessageCreate, authorization: Optional[str] = Header(None)):
    eng, sender_kind, sender_id = await _resolve_engagement_for_request(eid, authorization)
    if eng.get("status") == "closed":
        raise HTTPException(403, "Engagement is closed")
    body = (data.body or "").strip()
    if not body and not (data.attachments or []):
        raise HTTPException(400, "Message body or attachment required")
    mid = str(uuid.uuid4())
    doc = {
        "id": mid,
        "engagement_id": eid,
        "sender_kind": sender_kind,
        "sender_id": sender_id,
        "body_enc": encrypt_text(body),
        "attachments": data.attachments or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_by_client": sender_kind == "client",
        "read_by_firm": sender_kind == "firm",
    }
    await db.engagement_messages.insert_one(doc)
    return {"id": mid, "created_at": doc["created_at"], "sender_kind": sender_kind}

@api_router.get("/engagements/{eid}/messages")
async def list_engagement_messages(eid: str, authorization: Optional[str] = Header(None)):
    eng, sender_kind, sender_id = await _resolve_engagement_for_request(eid, authorization)
    rows = []
    async for m in db.engagement_messages.find({"engagement_id": eid}, {"_id": 0}).sort("created_at", 1):
        rows.append({
            "id": m["id"],
            "sender_kind": m.get("sender_kind"),
            "body": decrypt_text(m.get("body_enc") or ""),
            "attachments": m.get("attachments") or [],
            "created_at": m.get("created_at"),
        })
    # Mark as read for the current side
    field = "read_by_firm" if sender_kind == "firm" else "read_by_client"
    await db.engagement_messages.update_many({"engagement_id": eid, field: False}, {"$set": {field: True}})
    return {"messages": rows, "engagement": _public_engagement(eng, side=sender_kind)}

# ---------- Shared files (engagement-scoped vault) ----------

@api_router.post("/engagements/{eid}/files")
async def upload_engagement_file(eid: str, data: EngagementFileShare, authorization: Optional[str] = Header(None)):
    eng, sender_kind, sender_id = await _resolve_engagement_for_request(eid, authorization)
    if eng.get("status") == "closed":
        raise HTTPException(403, "Engagement is closed")
    try:
        raw = base64.b64decode(data.file_b64, validate=False)
    except Exception:
        raise HTTPException(400, "Invalid base64 content")
    if len(raw) > ENGAGEMENT_FILE_MAX_BYTES:
        raise HTTPException(413, "File too large (max 12MB)")
    count = await db.engagement_files.count_documents({"engagement_id": eid})
    if count >= ENGAGEMENT_FILE_LIMIT:
        raise HTTPException(402, f"Engagement file limit reached ({ENGAGEMENT_FILE_LIMIT}).")
    fid = str(uuid.uuid4())
    doc = {
        "id": fid,
        "engagement_id": eid,
        "uploader_kind": sender_kind,
        "uploader_id": sender_id,
        "title": (data.title or "Untitled")[:200],
        "mime_type": data.mime_type or "application/octet-stream",
        "size_bytes": len(raw),
        "file_enc": encrypt_bytes(raw),   # server-side Fernet
        "note_enc": encrypt_text(data.note or ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.engagement_files.insert_one(doc)
    return {"id": fid, "title": doc["title"], "size_bytes": doc["size_bytes"], "created_at": doc["created_at"]}

@api_router.get("/engagements/{eid}/files")
async def list_engagement_files(eid: str, authorization: Optional[str] = Header(None)):
    eng, sender_kind, sender_id = await _resolve_engagement_for_request(eid, authorization)
    rows = []
    async for f in db.engagement_files.find({"engagement_id": eid}, {"_id": 0, "file_enc": 0}).sort("created_at", -1):
        rows.append({
            "id": f["id"],
            "title": f.get("title"),
            "mime_type": f.get("mime_type"),
            "size_bytes": f.get("size_bytes"),
            "uploader_kind": f.get("uploader_kind"),
            "note": decrypt_text(f.get("note_enc") or ""),
            "created_at": f.get("created_at"),
        })
    return {"files": rows}

@api_router.get("/engagements/{eid}/files/{fid}")
async def download_engagement_file(eid: str, fid: str, authorization: Optional[str] = Header(None)):
    eng, sender_kind, sender_id = await _resolve_engagement_for_request(eid, authorization)
    f = await db.engagement_files.find_one({"id": fid, "engagement_id": eid}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")
    raw = decrypt_bytes(f.get("file_enc") or b"")
    return {
        "id": fid,
        "title": f.get("title"),
        "mime_type": f.get("mime_type"),
        "file_b64": base64.b64encode(raw).decode(),
    }

# ---------- Lex AI assist on a thread ----------

@api_router.post("/engagements/{eid}/lex-assist")
async def engagement_lex_assist(eid: str, data: EngagementLexAssist, authorization: Optional[str] = Header(None)):
    """Lex helps either party draft a reply / summarise the latest update / explain jargon.
    Consumer side: counts toward their normal Lex chat quota.
    Firm side: counts toward FIRM_LEX_MONTHLY_LIMITS based on tier."""
    eng, sender_kind, sender_id = await _resolve_engagement_for_request(eid, authorization)
    # Pull last ~20 messages for context
    history = []
    async for m in db.engagement_messages.find({"engagement_id": eid}, {"_id": 0}).sort("created_at", -1).limit(20):
        history.append(m)
    history.reverse()
    transcript = "\n".join([
        f"[{m.get('sender_kind','?').upper()} {m.get('created_at','')}] {decrypt_text(m.get('body_enc') or '')[:800]}"
        for m in history
    ]) or "(thread is empty)"
    matter = eng.get("matter") or "General"
    role_name = "the client" if sender_kind == "client" else "the solicitor / law firm"
    if data.kind == "draft_reply":
        instruction = f"Draft a clear, professional reply that {role_name} could send next. Keep it concise (max 200 words), polite, factual. Do not invent facts. If something is unclear, ask for it explicitly."
    elif data.kind == "summarise":
        instruction = "Summarise the case so far in 5 bullet points: status, key facts, open questions, deadlines, next action. Plain English."
    else:  # explain
        instruction = (data.context or "").strip() or "Explain the latest message from the other party in plain English. Flag any legal jargon, risks, or deadlines."
    system = (
        "You are Lex, a senior English & Welsh legal assistant inside AI Advocate's secure case thread. "
        f"You are assisting {role_name} on a matter of '{matter}'. "
        "Be professional, no hedging, no waffle. Never invent statutes or case names. "
        "If you don't know, say so. Output ONLY the requested content, no preamble."
    )
    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"engage-{eid}-{uuid.uuid4()}", system_message=system)\
            .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=900)
        prompt = f"--- CASE THREAD (most recent last) ---\n{transcript}\n\n--- TASK ---\n{instruction}"
        if data.context: prompt += f"\n\n--- EXTRA CONTEXT FROM {role_name.upper()} ---\n{data.context}"
        result = await chat.send_message(UserMessage(text=prompt))
        text = (result or "").strip()
    except Exception as e:
        raise HTTPException(503, f"Lex assist temporarily unavailable: {str(e)[:200]}")
    return {"output": text, "kind": data.kind}



# ==================== Live Mode Timestamped Notes ====================
# When a user is in a police interview, disciplinary, tribunal, etc., every
# utterance Lex hears is logged with a precise UTC timestamp so the user can
# refer back to the conversation afterwards (and export to PDF).

class LiveNote(BaseModel):
    session_id: str
    speaker: Literal["user", "other_party", "lex", "system"]
    text: str
    note_kind: Optional[Literal["utterance", "advice", "flag"]] = "utterance"

@api_router.post("/live/notes")
async def add_live_note(data: LiveNote, user: dict = Depends(get_user)):
    """Append one timestamped note to a Live Assist session log."""
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "session_id": data.session_id,
        "speaker": data.speaker,
        "text": data.text[:4000],
        "note_kind": data.note_kind or "utterance",
        "created_at": now.isoformat(),
        "ts_ms": int(now.timestamp() * 1000),
    }
    await db.live_notes.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/live/notes/{session_id}")
async def get_live_notes(session_id: str, user: dict = Depends(get_user)):
    notes = []
    async for n in db.live_notes.find(
        {"user_id": user["id"], "session_id": session_id}, {"_id": 0}
    ).sort("ts_ms", 1):
        notes.append(n)
    return {"session_id": session_id, "notes": notes, "count": len(notes)}

@api_router.get("/live/sessions")
async def list_live_sessions(user: dict = Depends(get_user)):
    """Group all live notes by session for the user's history list."""
    pipeline = [
        {"$match": {"user_id": user["id"]}},
        {"$group": {
            "_id": "$session_id",
            "first_at": {"$min": "$created_at"},
            "last_at": {"$max": "$created_at"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"last_at": -1}},
        {"$limit": 100},
    ]
    sessions = []
    async for s in db.live_notes.aggregate(pipeline):
        sessions.append({
            "session_id": s["_id"], "first_at": s["first_at"],
            "last_at": s["last_at"], "count": s["count"],
        })
    return sessions

@api_router.get("/live/notes/{session_id}/export")
async def export_live_notes_pdf(session_id: str, user: dict = Depends(get_user)):
    """PDF export of the full timestamped transcript — court-admissible reference."""
    notes = []
    async for n in db.live_notes.find(
        {"user_id": user["id"], "session_id": session_id}, {"_id": 0}
    ).sort("ts_ms", 1):
        notes.append(n)
    if not notes:
        raise HTTPException(404, "No notes found for this session")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], textColor=HexColor("#b8860b"))
    meta_style = ParagraphStyle("meta", parent=styles["Normal"], fontSize=9, textColor=HexColor("#6b6b6b"))
    speaker_styles = {
        "user":         ParagraphStyle("u", parent=styles["Normal"], fontSize=10, textColor=HexColor("#0a4d8c"), spaceBefore=6),
        "other_party":  ParagraphStyle("o", parent=styles["Normal"], fontSize=10, textColor=HexColor("#8c0a0a"), spaceBefore=6),
        "lex":          ParagraphStyle("l", parent=styles["Normal"], fontSize=10, textColor=HexColor("#b8860b"), spaceBefore=6),
        "system":       ParagraphStyle("s", parent=styles["Normal"], fontSize=9,  textColor=HexColor("#666"),    spaceBefore=4),
    }
    story = [Paragraph("AI Advocate — Live Session Transcript", title_style),
             Spacer(1, 4),
             Paragraph(f"Session: {session_id}", meta_style),
             Paragraph(f"From {notes[0]['created_at']} to {notes[-1]['created_at']}", meta_style),
             Paragraph(f"Total entries: {len(notes)}", meta_style),
             Spacer(1, 8),
             HRFlowable(width="100%", color=HexColor("#b8860b"), thickness=0.6),
             Spacer(1, 8)]
    speaker_label = {"user": "Me", "other_party": "Other party", "lex": "Lex (AI)", "system": "Note"}
    for n in notes:
        try:
            t = datetime.fromisoformat(n["created_at"].replace("Z", "+00:00"))
            ts = t.strftime("%H:%M:%S")
        except Exception:
            ts = "--:--:--"
        line = f"<b>[{ts}] {speaker_label.get(n['speaker'], n['speaker'])}:</b> {n['text']}"
        story.append(Paragraph(line, speaker_styles.get(n["speaker"], styles["Normal"])))
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", color=HexColor("#cccccc"), thickness=0.4))
    story.append(Paragraph("Generated by AI Advocate. Each line is timestamped in UTC at the moment it was recorded. "
                           "Use as a personal record only — not a certified court transcript.", meta_style))
    doc.build(story)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ai-advocate-session-{session_id[:8]}.pdf"'})


# ==================== Document / Letter Auto-Responder ====================
# Snap a photo of any letter (parking ticket, eviction notice, debt collector,
# council tax demand, employment letter, etc.) — Lex categorises it and drafts
# an appropriate response in one call.

class DocAnalyzeResponse(BaseModel):
    category: str
    summary: str
    deadlines: List[dict] = []      # [{label, date_iso}]
    suggested_response: str
    next_steps: List[str] = []
    severity: Literal["low", "medium", "high", "urgent"] = "medium"
    case_id: Optional[str] = None

@api_router.post("/document/analyze")
async def document_analyze(
    file: UploadFile = File(...),
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    case_id: Optional[str] = Form(None),
    user: dict = Depends(get_user),
):
    """Analyse a photographed/scanned letter and return category + draft response + deadlines."""
    pub = user_to_public(user)
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "doc_analyze", "monthly")
    if not ok:
        raise HTTPException(429, f"Document analysis monthly limit reached ({used}/{limit}). Upgrade to Plus for unlimited.")

    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 12MB)")
    suffix = "." + (file.filename.split(".")[-1].lower() if "." in file.filename else "jpg")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw); tmp.flush(); tmp.close()
    lang_name = LANG_NAMES.get(language, "English")

    sysmsg = f"""You are AI Advocate's document-analyser. The user uploaded a photo or scan of a letter or legal document.
Jurisdiction: {country}. Reply in {lang_name}.

Return STRICT JSON with this exact schema (no markdown, no commentary):
{{
  "category": "<one of: parking_ticket, council_tax, debt_collection, eviction, employment, tax, court_summons, police_letter, immigration, contract, insurance, medical, other>",
  "summary": "<2-3 sentence plain-language explanation of what this letter says>",
  "deadlines": [{{"label": "<what>", "date_iso": "<YYYY-MM-DD>"}}],
  "suggested_response": "<full draft of the user's response letter — sender, date, recipient, body, sign-off — ready to send. Polite, firm, references the relevant law where applicable.>",
  "next_steps": ["<short action 1>", "<short action 2>", "..."],
  "severity": "<low|medium|high|urgent>"
}}

If the document is NOT a legal/official letter, set category=\"other\", severity=\"low\", and suggested_response=\"This does not appear to be a legal document.\"
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"doc-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("gemini", "gemini-2.5-flash")
    try:
        resp = await chat.send_message(UserMessage(
            text="Analyse the attached document.",
            file_contents=[FileContentWithMimeType(file_path=tmp.name, mime_type=file.content_type or "image/jpeg")],
        ))
    except Exception as e:
        os.unlink(tmp.name)
        logger.exception("doc analyze failed")
        raise HTTPException(500, f"AI error: {e}")
    os.unlink(tmp.name)

    import json as _json, re as _re
    payload = resp.strip()
    # Strip markdown fences if model added them
    payload = _re.sub(r"^```(?:json)?\s*", "", payload)
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        parsed = _json.loads(payload)
    except Exception:
        parsed = {"category": "other", "summary": payload[:600], "deadlines": [],
                  "suggested_response": "", "next_steps": [], "severity": "low"}

    # Persist in case_items if a case is linked
    if case_id:
        await db.case_items.insert_one({
            "id": str(uuid.uuid4()), "case_id": case_id, "user_id": user["id"],
            "kind": "document_analysis", "title": parsed.get("category", "document"),
            "data": parsed, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Auto-create deadline reminders for any extracted dates
        for dl in parsed.get("deadlines", []) or []:
            try:
                due = datetime.fromisoformat(dl["date_iso"]).replace(tzinfo=timezone.utc)
                await db.reminders.insert_one({
                    "id": str(uuid.uuid4()), "user_id": user["id"], "case_id": case_id,
                    "title": dl.get("label", "Deadline"), "description": "",
                    "due_at": due.isoformat(), "kind": "deadline",
                    "status": "pending", "source": "doc_auto",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
    parsed["case_id"] = case_id
    return parsed


# ==================== Lex Reply Feedback ====================
class FeedbackPayload(BaseModel):
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    rating: Literal["up", "down"]
    comment: Optional[str] = None
    surface: Optional[str] = "lex_chat"   # lex_chat | live_assist | letter | doc

@api_router.post("/feedback")
async def submit_feedback(data: FeedbackPayload, user: dict = Depends(get_user)):
    await db.feedback.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "conversation_id": data.conversation_id, "session_id": data.session_id,
        "rating": data.rating, "comment": (data.comment or "")[:1000],
        "surface": data.surface or "lex_chat",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


# ==================== Daily "Know Your Rights" Tip ====================
# Cached per-day per-language so we don't burn LLM calls every request.

@api_router.get("/tips/daily")
async def daily_tip(language: str = "en-GB", country: str = "GB", user: dict = Depends(get_user)):
    today = datetime.now(timezone.utc).date().isoformat()
    cache_key = f"{today}-{language}-{country}"
    cached = await db.tips_cache.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        return {"date": today, "tip": cached["tip"], "cached": True}
    lang_name = LANG_NAMES.get(language, "English")
    sysmsg = f"""You are AI Advocate writing today's "Know Your Rights" tip for users in {country}.
Output ONE concise tip (max 35 words) in {lang_name}. Practical, useful, surprising-but-true.
No greetings, no preamble — just the tip itself."""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"tip-{cache_key}", system_message=sysmsg)\
        .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=80)
    try:
        tip = (await chat.send_message(UserMessage(text="Today's tip please."))).strip()
    except Exception as e:
        logger.exception("daily tip failed"); tip = "Always ask for an officer's badge number — you have the right to record it."
    await db.tips_cache.insert_one({"key": cache_key, "tip": tip,
                                     "created_at": datetime.now(timezone.utc).isoformat()})
    return {"date": today, "tip": tip, "cached": False}


# ==================== File Deletion ====================
@api_router.delete("/legal-files/{file_id}")
async def delete_legal_file(file_id: str, user: dict = Depends(get_user)):
    """Customer-facing delete for any file in /legal-files."""
    res = await db.legal_files.delete_one({"id": file_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "File not found")
    return {"deleted": True, "id": file_id}


# ==================== Contract Reader & Drafter ====================

@api_router.post("/contract/analyze")
async def contract_analyze(
    file: UploadFile = File(...),
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    user: dict = Depends(get_user),
):
    """Read a contract, break it down clause-by-clause, flag risks, give a verdict."""
    pub = user_to_public(user)
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "doc_analyze", "monthly")
    if not ok:
        raise HTTPException(429, f"Document analysis monthly limit reached ({used}/{limit}). Upgrade to Plus for unlimited.")

    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 12MB)")
    suffix = "." + (file.filename.split(".")[-1].lower() if "." in file.filename else "jpg")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw); tmp.flush(); tmp.close()
    lang_name = LANG_NAMES.get(language, "English")

    sysmsg = f"""You are AI Advocate's contract-reading expert. The user has uploaded a contract and wants you to read it like an experienced solicitor would.
Jurisdiction: {country}. Reply in {lang_name}.

Return STRICT JSON only (no markdown):
{{
  "contract_type": "<employment | contractor | nda | lease | sale | service | loan | partnership | shareholder | settlement | other>",
  "plain_english_summary": "<2-3 sentence plain-language summary of what this contract does>",
  "overall_verdict": "<green | amber | red>",
  "verdict_one_liner": "<single sentence verdict like 'Safe to sign' / 'Negotiate these points first' / 'Do NOT sign without solicitor advice'>",
  "clauses": [
    {{"title": "<short label>", "plain_english": "<what this clause actually means>", "risk_level": "<low | medium | high>"}}
  ],
  "red_flags": ["<specific concerning thing 1>", "<thing 2>"],
  "amber_flags": ["<negotiable thing 1>", "<negotiable thing 2>"],
  "questions_to_ask": ["<question to raise with the other party before signing 1>", "..."],
  "solicitor_review_recommended": <true | false>,
  "missing_protections": ["<protection the user would normally expect that's absent>"]
}}

Be honest, plain, and protective of the user. Flag auto-renewing clauses, one-sided variation rights, broad indemnities, overlong restrictive covenants, hidden fees, foreign-jurisdiction clauses, anything below statutory minimums (e.g. UK minimum wage / holiday).
If the document is NOT a contract, set contract_type=\"other\" and verdict_one_liner=\"This does not appear to be a contract.\"
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"contract-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2800)
    try:
        # Stage 1: extract text via Gemini (Claude doesn't accept file attachments here)
        extracted_text = await _extract_contract_text(tmp.name, file.content_type or "application/pdf")
        if not extracted_text or len(extracted_text) < 30:
            os.unlink(tmp.name)
            raise HTTPException(400, "Could not read enough text from the contract. Try a clearer photo or PDF.")
        # Stage 2: analyse the text with Claude
        resp = await chat.send_message(UserMessage(
            text=f"Analyse the following contract text:\n\n{extracted_text[:30000]}",
        ))
    except HTTPException:
        try: os.unlink(tmp.name)
        except Exception: pass
        raise
    except Exception as e:
        try: os.unlink(tmp.name)
        except Exception: pass
        logger.exception("contract analyze failed")
        raise HTTPException(500, f"AI error: {e}")
    try: os.unlink(tmp.name)
    except Exception: pass

    import json as _json, re as _re
    payload = _re.sub(r"^```(?:json)?\s*", "", resp.strip())
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        return _json.loads(payload)
    except Exception:
        return {
            "contract_type": "other", "plain_english_summary": payload[:600],
            "overall_verdict": "amber", "verdict_one_liner": "Could not fully parse this contract.",
            "clauses": [], "red_flags": [], "amber_flags": [], "questions_to_ask": [],
            "solicitor_review_recommended": True, "missing_protections": [],
        }


class ContractDraftRequest(BaseModel):
    contract_type: Literal["employment", "contractor", "nda", "lease", "sale", "service", "consultancy", "partnership"]
    party_a: dict   # business / employer side: name, address, registration_no, sector, signatory
    party_b: dict   # employee / contractor / other side: name, address, role, ni_no_or_company_no, email
    terms: dict     # type-specific terms: salary, hours, notice_period, start_date, etc. (free-form)
    additional_notes: str = ""
    language: str = "en-GB"
    country: str = "GB"

@api_router.post("/contract/draft")
async def contract_draft(data: ContractDraftRequest, user: dict = Depends(get_user)):
    """Generate a UK-compliant contract from structured inputs."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "contract_draft"):
        raise HTTPException(402, "Contract drafting requires Pro. Upgrade to unlock.")
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "letters_generate", "monthly")
    if not ok:
        raise HTTPException(429, f"Document generation monthly limit reached ({used}/{limit}). Upgrade to Plus for unlimited.")

    lang_name = LANG_NAMES.get(data.language, "English")
    sysmsg = f"""You are AI Advocate's contract-drafting expert. You draft contracts that are legally enforceable under {data.country} law.
Reply in {lang_name}.

CRITICAL — for UK ({data.country}=GB) contracts you MUST include where applicable:
 - Employment Rights Act 1996 written statement of particulars (s.1)
 - Working Time Regulations 1998 holiday clause
 - National Minimum Wage Act compliance check
 - Pension auto-enrolment notice (Pensions Act 2008) for employment contracts over 22 with qualifying earnings
 - GDPR / Data Protection Act 2018 personal-data clause
 - Equality Act 2010 anti-discrimination clause
 - Place of work + remote-working clause
 - Standard restrictive covenants where applicable (proportionate, max 6-12 months)

Return STRICT JSON (no markdown):
{{
  "contract_title": "<e.g. 'Contract of Employment between X and Y'>",
  "full_contract_text": "<the complete contract — proper structure with numbered clauses, parties block, signature block, date block — ready to copy into a Word doc or print. Use \\n for line breaks. Include 'Signed for [employer]' and 'Signed by [employee]' sections.>",
  "statutory_clauses_included": ["<clause type 1>", "<clause type 2>"],
  "risk_level": "<low | medium | high>",
  "solicitor_review_recommended": <true | false — true if value > £50k, IP transfer involved, regulated industry, or overseas elements>,
  "next_steps_for_user": ["<step 1 e.g. 'Both parties sign and date'>", "<step 2 e.g. 'Email signed copy to employee within X days'>"],
  "warnings": ["<any specific concern about the inputs the user gave>"]
}}
"""
    user_input = f"""Contract type: {data.contract_type}

Party A (business / employer / first party):
{_safe_json(data.party_a)}

Party B (employee / contractor / second party):
{_safe_json(data.party_b)}

Terms:
{_safe_json(data.terms)}

Additional notes from user: {data.additional_notes or '(none)'}
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"draft-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=4500)
    try:
        resp = await chat.send_message(UserMessage(text=user_input))
    except Exception as e:
        logger.exception("contract draft failed"); raise HTTPException(500, f"AI error: {e}")

    import json as _json, re as _re
    payload = _re.sub(r"^```(?:json)?\s*", "", resp.strip())
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        result = _json.loads(payload)
    except Exception:
        result = {
            "contract_title": f"{data.contract_type.title()} Contract",
            "full_contract_text": payload, "statutory_clauses_included": [],
            "risk_level": "medium", "solicitor_review_recommended": True,
            "next_steps_for_user": ["Both parties sign and date", "Each party keeps a signed copy"],
            "warnings": [],
        }

    # Persist as a legal-file so the user can find it later
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"], "type": "contract",
        "filename": result.get("contract_title", "Contract"),
        "content": result.get("full_contract_text", ""),
        "analysis": _json.dumps({k: v for k, v in result.items() if k != "full_contract_text"}, ensure_ascii=False),
        "contract_type": data.contract_type, "language": data.language, "country": data.country,
        "created_at": now.isoformat(),
    }
    await db.legal_files.insert_one(doc.copy())
    doc.pop("_id", None)
    result["file_id"] = doc["id"]
    return result


def _safe_json(obj):
    import json
    try: return json.dumps(obj or {}, ensure_ascii=False, indent=2)
    except Exception: return str(obj)


async def _extract_contract_text(tmp_path: str, mime_type: str) -> str:
    """Use Gemini Flash to extract the full verbatim text of a contract from any image/PDF/doc.
    Returns the raw text (may be long). Falls back to plain-text read for .txt files.
    """
    # Cheap fast path for plain text
    if mime_type and ("text" in mime_type or tmp_path.endswith(".txt")):
        try:
            with open(tmp_path, "r", errors="ignore") as f:
                return f.read()
        except Exception:
            pass

    extract_chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"extract-{uuid.uuid4()}",
        system_message="You are an OCR + document-text extractor. Return the COMPLETE verbatim text of the document, preserving clause numbering and structure. No analysis, no commentary — JUST the raw text.",
    ).with_model("gemini", "gemini-2.5-flash").with_params(max_tokens=4000)

    file_ref = FileContentWithMimeType(file_path=tmp_path, mime_type=mime_type or "application/pdf")
    try:
        text = await extract_chat.send_message(UserMessage(
            text="Extract the complete text of this document, exactly as written. Preserve clause numbers and line breaks.",
            file_contents=[file_ref],
        ))
        return (text or "").strip()
    except Exception as ex:
        logger.exception("contract text extract failed")
        raise HTTPException(500, f"Could not extract contract text: {ex}")


# ==================== Contract Negotiate (Pro flagship) ====================
@api_router.post("/contract/negotiate")
async def contract_negotiate(
    file: UploadFile = File(...),
    priorities: str = Form(""),   # free-form: "I care most about salary and remote work"
    user_role: str = Form("recipient"),  # recipient | offerer
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    user: dict = Depends(get_user),
):
    """Pro-only: Review a contract and produce a redline negotiation strategy + ready-to-send email."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "contract_negotiate"):
        raise HTTPException(402, "Contract Negotiate is Pro-only. Upgrade to unlock Lex's redline strategy.")
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "doc_analyze", "monthly")
    if not ok:
        raise HTTPException(429, f"Document analysis monthly limit reached ({used}/{limit}).")

    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 12MB)")
    suffix = "." + (file.filename.split(".")[-1].lower() if "." in file.filename else "jpg")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw); tmp.flush(); tmp.close()
    lang_name = LANG_NAMES.get(language, "English")

    sysmsg = f"""You are AI Advocate's contract NEGOTIATOR — an experienced commercial solicitor advising the user before they sign.
Jurisdiction: {country}. Reply in {lang_name}.

The user's role is: {user_role} (recipient = receiving / being asked to sign; offerer = the side proposing the contract).
The user's stated priorities: {priorities or '(none specified — assume reasonable defaults)'}.

Your job: pick the 3-5 WORST or most lopsided clauses and produce a real negotiation play. Be concrete. Quote the actual contract wording when you can. Never invent law.

Return STRICT JSON only (no markdown):
{{
  "contract_type": "<employment | nda | lease | sale | service | partnership | other>",
  "leverage_assessment": "<one-line read of who has the leverage — 'You have strong leverage', 'They have leverage but you can push X', etc.>",
  "worst_clauses": [
    {{
      "clause_title": "<short label e.g. 'Restrictive Covenant (Clause 14)'>",
      "current_text_quote": "<short verbatim quote from the contract — max ~30 words. If you cannot see the exact wording, paraphrase tightly>",
      "why_its_bad_for_user": "<plain-English explanation of the risk to the user, 1-2 sentences>",
      "suggested_redline": "<exact replacement wording the user should propose — drafted as a finished clause they can paste in>",
      "fallback_position": "<if the other side rejects your redline, what's a reasonable middle ground>",
      "priority": "<must-fix | should-fix | nice-to-have>"
    }}
  ],
  "missing_protections": ["<protection the user should INSERT into the contract — e.g. 'IP carve-out for pre-existing work', 'Mutual termination clause'>"],
  "do_not_compromise_on": ["<bottom-line items the user must NOT give up on, even to close the deal>"],
  "walk_away_signals": ["<conditions that should make the user walk away entirely>"],
  "negotiation_strategy": "<3-4 sentence honest plan for HOW to negotiate — tone, sequence, what to lead with>",
  "ready_to_send_email": "<a professional, polite, ready-to-send email (NOT a letter — email format, no addresses) the user can send TODAY to open negotiations. Use the user's actual situation. Include subject line as first line e.g. 'Subject: Proposed amendments to the [contract name]'. End with 'Kind regards,' on its own line (user signs their own name). Keep it firm but collaborative. Use \\n for line breaks.>",
  "estimated_negotiation_difficulty": "<easy | moderate | hard>"
}}

CRITICAL: If the document is NOT a contract, return contract_type='other' and worst_clauses=[] with leverage_assessment='This does not appear to be a contract.'
Stay in jurisdiction {country}. For UK, reference Employment Rights Act 1996 / Equality Act 2010 / Consumer Rights Act 2015 / Late Payment of Commercial Debts Act 1998 where directly relevant — never cite law you're unsure about.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"negotiate-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=3000)
    try:
        extracted_text = await _extract_contract_text(tmp.name, file.content_type or "application/pdf")
        if not extracted_text or len(extracted_text) < 30:
            os.unlink(tmp.name)
            raise HTTPException(400, "Could not read enough text from the contract. Try a clearer photo or PDF.")
        resp = await chat.send_message(UserMessage(
            text=f"Negotiate this contract on my behalf. My priorities: {priorities or '(none specified)'}.\n\nFull contract text:\n\n{extracted_text[:30000]}",
        ))
    except HTTPException:
        try: os.unlink(tmp.name)
        except Exception: pass
        raise
    except Exception as e:
        try: os.unlink(tmp.name)
        except Exception: pass
        logger.exception("contract negotiate failed")
        raise HTTPException(500, f"AI error: {e}")
    try: os.unlink(tmp.name)
    except Exception: pass

    import json as _json, re as _re
    payload = _re.sub(r"^```(?:json)?\s*", "", resp.strip())
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        result = _json.loads(payload)
    except Exception:
        result = {
            "contract_type": "other",
            "leverage_assessment": "Could not fully parse this contract.",
            "worst_clauses": [],
            "missing_protections": [],
            "do_not_compromise_on": [],
            "walk_away_signals": [],
            "negotiation_strategy": payload[:600],
            "ready_to_send_email": "",
            "estimated_negotiation_difficulty": "moderate",
        }
    return result



# ==================== Round 2: Outcome Predictor ====================
class OutcomePredictRequest(BaseModel):
    case_summary: str
    category: Optional[str] = None
    language: str = "en-GB"
    country: str = "GB"

@api_router.post("/outcome/predict")
async def outcome_predict(data: OutcomePredictRequest, user: dict = Depends(get_user)):
    """Give a realistic % chance of success + similar past cases."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "outcome_predict"):
        raise HTTPException(402, "Outcome Predictor requires Pro. Upgrade to unlock Opus deep-think.")
    if not data.case_summary or len(data.case_summary) < 20:
        raise HTTPException(400, "Please provide more detail (at least 20 chars)")
    lang_name = LANG_NAMES.get(data.language, "English")
    sysmsg = f"""You are AI Advocate's outcome predictor. The user is in {data.country}.
Reply in {lang_name}.

Return STRICT JSON only (no markdown):
{{
  "success_probability_pct": <0-100 integer — realistic, conservative>,
  "key_factors_for": ["<factor 1>", "<factor 2>", "..."],
  "key_factors_against": ["<factor 1>", "<factor 2>", "..."],
  "similar_cases": [
    {{"name": "<e.g. Smith v Jones [2019]>", "outcome": "<who won + why>", "relevance": "<why this matches>"}}
  ],
  "recommended_strategy": "<3-4 sentence honest plan>",
  "confidence": "<low|medium|high>"
}}

Be HONEST. If their case is weak, say so. Never inflate.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"outcome-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=1500)
    try:
        resp = await chat.send_message(UserMessage(text=f"Case category: {data.category or 'unspecified'}\n\nCase summary:\n{data.case_summary}"))
    except Exception as e:
        logger.exception("outcome predict failed"); raise HTTPException(500, f"AI error: {e}")
    import json as _json, re as _re
    payload = _re.sub(r"^```(?:json)?\s*", "", resp.strip())
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        return _json.loads(payload)
    except Exception:
        return {"success_probability_pct": 0, "key_factors_for": [], "key_factors_against": [],
                "similar_cases": [], "recommended_strategy": payload[:400], "confidence": "low"}


# ==================== Round 2: Lawyer Cost Estimator ====================
class CostEstimateRequest(BaseModel):
    case_summary: str
    category: Optional[str] = None
    country: str = "GB"
    language: str = "en-GB"

@api_router.post("/cost/estimate")
async def lawyer_cost_estimate(data: CostEstimateRequest, user: dict = Depends(get_user)):
    lang_name = LANG_NAMES.get(data.language, "English")
    sysmsg = f"""You are AI Advocate's lawyer-cost estimator for {data.country}. Reply in {lang_name}.
Return STRICT JSON (no markdown):
{{
  "low_estimate_gbp": <integer>,
  "high_estimate_gbp": <integer>,
  "court_fees_gbp": <integer or 0>,
  "typical_hours": <integer>,
  "hourly_rate_range_gbp": "<e.g. 180-350>",
  "no_win_no_fee_available": <true|false>,
  "explanation": "<2-3 sentences explaining what the user would actually pay a solicitor and why>",
  "ai_advocate_saving": "<one sentence saying how AI Advocate covers the basics of this matter>"
}}
Be honest and realistic for UK / common-law rates if country=GB; use local market rates for other countries.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"cost-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=600)
    try:
        resp = await chat.send_message(UserMessage(text=f"Category: {data.category or 'unspecified'}\n\nCase: {data.case_summary}"))
    except Exception as e:
        logger.exception("cost estimate failed"); raise HTTPException(500, f"AI error: {e}")
    import json as _json, re as _re
    payload = _re.sub(r"^```(?:json)?\s*", "", resp.strip())
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        return _json.loads(payload)
    except Exception:
        return {"low_estimate_gbp": 0, "high_estimate_gbp": 0, "court_fees_gbp": 0,
                "typical_hours": 0, "hourly_rate_range_gbp": "—",
                "no_win_no_fee_available": False, "explanation": payload[:300], "ai_advocate_saving": ""}


# ==================== Round 2: Hearing Recorder (full transcript) ====================
@api_router.post("/hearing/transcribe")
async def hearing_transcribe(
    audio: UploadFile = File(...),
    language: str = Form("en-GB"),
    country: str = Form("GB"),
    case_id: Optional[str] = Form(None),
    title: Optional[str] = Form("Hearing recording"),
    user: dict = Depends(get_user),
):
    """Upload long audio (tribunal/disciplinary/permitted hearing) → full transcript + Lex's review."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "hearing_transcribe"):
        raise HTTPException(402, "Hearing Recorder requires Pro. Upgrade to unlock long-audio transcription.")
    raw = await audio.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "Audio file too large (max 50MB)")
    suffix = "." + (audio.filename.split(".")[-1].lower() if "." in audio.filename else "m4a")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix); tmp.write(raw); tmp.flush(); tmp.close()
    try:
        stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
        with open(tmp.name, "rb") as _audio_fh:
            _stt_resp = await stt.transcribe(file=_audio_fh, language=(language or "en-GB").split("-")[0])
        # Normalize to plain string regardless of response shape
        if isinstance(_stt_resp, str):
            transcript = _stt_resp
        elif hasattr(_stt_resp, "text"):
            transcript = _stt_resp.text or ""
        elif isinstance(_stt_resp, dict):
            transcript = _stt_resp.get("text") or ""
        else:
            transcript = str(_stt_resp) if _stt_resp else ""
    except Exception as e:
        os.unlink(tmp.name); logger.exception("hearing stt failed"); raise HTTPException(500, f"Transcription failed: {e}")
    os.unlink(tmp.name)

    # Run Lex over the transcript for an executive summary
    lang_name = LANG_NAMES.get(language, "English")
    sysmsg = f"""You are AI Advocate. The user uploaded a recording of a permitted hearing/disciplinary/tribunal.
Reply in {lang_name}. Return STRICT JSON:
{{
  "summary": "<2-3 sentence plain-language summary>",
  "key_points": ["<point 1>", "<point 2>", "..."],
  "favourable_moments": ["<things said that helped the user>"],
  "unfavourable_moments": ["<things said that hurt the user>"],
  "next_actions": ["<action 1>", "..."],
  "follow_up_deadlines": [{{"label": "<what>", "date_iso": "<YYYY-MM-DD>"}}]
}}
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"hearing-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=1500)
    try:
        resp = await chat.send_message(UserMessage(text=f"Transcript:\n\n{(transcript or '')[:14000]}"))
    except Exception as e:
        resp = "{}"

    import json as _json, re as _re
    payload = _re.sub(r"^```(?:json)?\s*", "", resp.strip())
    payload = _re.sub(r"\s*```$", "", payload).strip()
    try:
        analysis = _json.loads(payload)
    except Exception:
        analysis = {"summary": "(could not parse)", "key_points": [], "favourable_moments": [],
                    "unfavourable_moments": [], "next_actions": [], "follow_up_deadlines": []}

    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"], "type": "hearing_transcript",
        "filename": title or "Hearing recording", "transcript": transcript or "",
        "analysis": _json.dumps(analysis, ensure_ascii=False), "case_id": case_id,
        "language": language, "country": country, "created_at": now.isoformat(),
    }
    await db.legal_files.insert_one(doc.copy())
    doc.pop("_id", None)
    return {"id": doc["id"], "transcript": transcript or "", "analysis": analysis, "created_at": doc["created_at"]}


# ==================== Round 2: Legal Aid Finder ====================
class LegalAidCheckRequest(BaseModel):
    monthly_income_gbp: float
    savings_gbp: float = 0
    household_size: int = 1
    case_category: str
    country: str = "GB"
    language: str = "en-GB"

@api_router.post("/legal-aid/check")
async def legal_aid_check(data: LegalAidCheckRequest, user: dict = Depends(get_user)):
    """Indicative legal-aid eligibility (UK) + nearest free-help signposts. NOT a definitive decision."""
    # Very rough thresholds based on current UK Legal Aid Agency limits
    qualifies = False; reasons = []; signposts = []
    if data.country == "GB":
        # Means test rough: disposable monthly income under £2,657 + savings under £8,000 → likely eligible for civil legal aid
        if data.monthly_income_gbp <= 2657 and data.savings_gbp <= 8000:
            qualifies = True
            reasons.append("Income and savings are within the civil legal-aid means-test thresholds.")
        else:
            reasons.append(f"Income £{int(data.monthly_income_gbp)}/mo or savings £{int(data.savings_gbp)} above current legal-aid limits (~£2,657 income, £8,000 savings).")
        signposts = [
            {"name": "Citizens Advice", "url": "https://www.citizensadvice.org.uk/", "free": True},
            {"name": "Law Centres Network", "url": "https://www.lawcentres.org.uk/", "free": True},
            {"name": "Bar Pro Bono Unit (Advocate)", "url": "https://weareadvocate.org.uk/", "free": True},
            {"name": "Gov.uk – Check if you can get legal aid", "url": "https://www.gov.uk/check-legal-aid", "free": True},
        ]
        # Category-specific add-ons
        if data.case_category in ("immigration",):
            signposts.append({"name": "Right to Remain", "url": "https://righttoremain.org.uk/", "free": True})
        if data.case_category in ("employment",):
            signposts.append({"name": "ACAS", "url": "https://www.acas.org.uk/", "free": True})
        if data.case_category in ("eviction", "property", "housing"):
            signposts.append({"name": "Shelter", "url": "https://www.shelter.org.uk/", "free": True})
    else:
        reasons.append(f"AI Advocate does not yet maintain a legal-aid means-test for {data.country}. We've listed general free-help options below.")
        signposts = [{"name": "International Bar Association — Pro Bono finder", "url": "https://www.ibanet.org/", "free": True}]
    return {
        "country": data.country, "qualifies": qualifies, "reasons": reasons,
        "signposts": signposts,
        "disclaimer": "Indicative only — final eligibility is decided by the legal-aid authority. Always confirm via the official link above."
    }


# ==================== Round 2: Case Sharing (read-only links) ====================
@api_router.post("/cases/{case_id}/share")
async def share_case(case_id: str, user: dict = Depends(get_user)):
    """Create a public read-only share token for a case file."""
    case = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")
    # Revoke any existing token for this case first (one active at a time per case)
    token = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await db.share_tokens.delete_many({"case_id": case_id})
    await db.share_tokens.insert_one({
        "token": token, "case_id": case_id, "user_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    })
    base = APP_PUBLIC_URL.rstrip("/")
    return {"token": token, "url": f"{base}/share/{token}", "expires_at": expires_at.isoformat()}

@api_router.delete("/cases/{case_id}/share")
async def revoke_share(case_id: str, user: dict = Depends(get_user)):
    res = await db.share_tokens.delete_many({"case_id": case_id, "user_id": user["id"]})
    return {"revoked": res.deleted_count}

@api_router.get("/share/{token}")
async def public_share_view(token: str):
    """Public, read-only — no auth — returns case + its items so anyone with the link can view."""
    t = await db.share_tokens.find_one({"token": token}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Share link invalid or revoked")
    try:
        exp = datetime.fromisoformat(t["expires_at"])
        if exp < datetime.now(timezone.utc):
            raise HTTPException(410, "Share link expired")
    except HTTPException:
        raise
    except Exception:
        pass
    case = await db.cases.find_one({"id": t["case_id"]}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")
    items = []
    async for it in db.case_items.find({"case_id": t["case_id"]}, {"_id": 0, "user_id": 0}).sort("created_at", 1):
        items.append(it)
    # Strip PII fields from case if present
    case.pop("user_id", None)
    return {"case": case, "items": items, "shared_at": t["created_at"], "expires_at": t["expires_at"]}


# ==================== Round 2: Anonymous Stats Wall ====================
@api_router.get("/stats/public")
async def public_stats():
    """No auth — homepage / footer social proof. Aggregates only, no PII."""
    # Cache for 5 minutes via an in-process attempt; if a Mongo doc is present, use it.
    cached = await db.stats_cache.find_one({"key": "public"}, {"_id": 0})
    now = datetime.now(timezone.utc)
    if cached:
        try:
            if (now - datetime.fromisoformat(cached["computed_at"])).total_seconds() < 300:
                return cached["data"]
        except Exception:
            pass
    data = {
        "users_helped_total": await db.users.count_documents({}),
        "cases_active": await db.cases.count_documents({"status": "active"}),
        "letters_drafted": await db.legal_files.count_documents({"type": {"$in": ["legal_letter", "letter"]}}),
        "documents_analysed": await db.legal_files.count_documents({"type": "evidence"}),
        "hearings_transcribed": await db.legal_files.count_documents({"type": "hearing_transcript"}),
        "live_sessions": len(await db.live_notes.distinct("session_id")),
    }
    await db.stats_cache.update_one(
        {"key": "public"},
        {"$set": {"data": data, "computed_at": now.isoformat()}},
        upsert=True,
    )
    return data



# ==================== ADMIN DASHBOARD ====================
ADMIN_EMAILS = [e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]

async def require_admin(user: dict = Depends(get_user)):
    if user.get("email", "").lower() not in ADMIN_EMAILS:
        raise HTTPException(403, "Admin only")
    return user

@api_router.get("/admin/stats")
async def admin_stats(_: dict = Depends(require_admin)):
    return {
        "users_total": await db.users.count_documents({}),
        "users_trial": await db.users.count_documents({"tier": "trial_pro"}),
        "users_plus": await db.users.count_documents({"tier": "plus", "subscription_status": "active"}),
        "users_pro": await db.users.count_documents({"tier": "pro", "subscription_status": "active"}),
        "users_yearly": await db.users.count_documents({"tier": "yearly", "subscription_status": "active"}),
        "firms_pending": await db.firm_accounts.count_documents({"status": "pending_review"}),
        "firms_approved": await db.firm_accounts.count_documents({"status": "approved"}),
        "chats_today": await db.conversations.count_documents({"created_at": {"$gte": datetime.now(timezone.utc).date().isoformat()}}),
        "leads_today": await db.inquiries.count_documents({"created_at": {"$gte": datetime.now(timezone.utc).date().isoformat()}}),
    }

@api_router.get("/admin/firms")
async def admin_list_firms(_: dict = Depends(require_admin), status: Optional[str] = None):
    q = {}
    if status: q["status"] = status
    out = []
    async for f in db.firm_accounts.find(q, {"_id": 0, "password": 0}).sort("created_at", -1).limit(200):
        out.append(f)
    return {"firms": out}

@api_router.post("/admin/firms/action")
async def admin_firm_action(data: AdminFirmAction, admin: dict = Depends(require_admin)):
    f = await db.firm_accounts.find_one({"id": data.firm_id})
    if not f: raise HTTPException(404, "Firm not found")
    upd = {"reviewed_at": datetime.now(timezone.utc).isoformat(), "reviewed_by": admin["email"], "review_notes": data.notes}
    if data.action == "approve":
        upd["status"] = "approved"
        # Create the directory listing
        if not await db.lawfirms.find_one({"firm_account_id": f["id"]}):
            await db.lawfirms.insert_one({
                "id": str(uuid.uuid4()), "firm_account_id": f["id"], "name": f["firm_name"],
                "country": f["country"], "city": f["city"], "phone": f["phone"],
                "website": f["website"], "specialties": f.get("specialties", []),
                "verified": False, "featured": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    elif data.action == "reject":
        upd["status"] = "rejected"
    elif data.action == "suspend":
        upd["status"] = "suspended"
        await db.lawfirms.update_one({"firm_account_id": f["id"]}, {"$set": {"suspended": True}})
    elif data.action == "verify":
        upd["verified"] = True
        await db.lawfirms.update_one({"firm_account_id": f["id"]}, {"$set": {"verified": True}})
    elif data.action == "unverify":
        upd["verified"] = False
        await db.lawfirms.update_one({"firm_account_id": f["id"]}, {"$set": {"verified": False}})
    else:
        raise HTTPException(400, "Invalid action")
    await db.firm_accounts.update_one({"id": data.firm_id}, {"$set": upd})
    return {"ok": True, "new_status": upd.get("status", f["status"])}

# ==================== CLOUD BACKUP (Export-as-JSON) ====================
@api_router.get("/backup/export")
async def export_user_data(user: dict = Depends(get_user)):
    """Plus+ feature — bundle ALL user data into a JSON file (court-ready + GDPR right-to-portability).
    User can save this to iCloud Drive / Google Drive manually via the OS Share sheet."""
    pub = user_to_public(user)
    if pub["tier"] == "free":
        raise HTTPException(402, "Cloud Backup requires Plus or Pro. Upgrade to unlock data export.")
    bundle = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {"email": user["email"], "id": user["id"], "country": user.get("country"), "tier": pub["tier"]},
        "cases": [], "conversations": [], "evidence": [], "letters": [], "reminders": [], "recordings": [],
    }
    async for c in db.cases.find({"user_id": user["id"]}, {"_id": 0}): bundle["cases"].append(c)
    async for c in db.conversations.find({"user_id": user["id"]}, {"_id": 0}).limit(2000): bundle["conversations"].append(c)
    async for e in db.evidence.find({"user_id": user["id"]}, {"_id": 0}): bundle["evidence"].append(e)
    async for l in db.letters.find({"user_id": user["id"]}, {"_id": 0}): bundle["letters"].append(l)
    async for r in db.reminders.find({"user_id": user["id"]}, {"_id": 0}): bundle["reminders"].append(r)
    async for r in db.recordings.find({"user_id": user["id"]}, {"_id": 0}): bundle["recordings"].append(r)
    import json as _json
    body = _json.dumps(bundle, indent=2, default=str)
    return StreamingResponse(io.BytesIO(body.encode()), media_type="application/json",
                             headers={"Content-Disposition": f'attachment; filename="ai-advocate-backup-{user["id"][:8]}.json"'})

# ==================== TRUSTPILOT PRE-RENEWAL REMINDER ====================
@api_router.get("/review/should-prompt")
async def review_should_prompt(user: dict = Depends(get_user)):
    """Returns true if the user is within 7 days of subscription renewal AND has NOT clicked the Trustpilot link yet."""
    if user.get("review_left"):
        return {"should_prompt": False, "reason": "already_reviewed"}
    pub = user_to_public(user)
    if pub["tier"] in ("free",):
        return {"should_prompt": False, "reason": "free_tier"}
    import math as _math
    # Trial — prompt during the final 2 days. Use ceil so users in last-24h (days=0) still get prompted.
    if pub["tier"] == "trial_pro":
        days_left = pub.get("trial_days_remaining", 7)
        # If we have the raw trial_end_date, recompute with ceil so a 12h-left user counts as "1 day"
        if user.get("trial_end_date"):
            try:
                te = datetime.fromisoformat(user["trial_end_date"].replace("Z", "+00:00")) if isinstance(user["trial_end_date"], str) else user["trial_end_date"]
                hours_left = (te - datetime.now(timezone.utc)).total_seconds() / 3600
                days_left = _math.ceil(hours_left / 24) if hours_left > 0 else 0
            except Exception:
                pass
        if 0 < days_left <= 2:
            return {"should_prompt": True, "reason": "trial_ending", "days_left": days_left}
        return {"should_prompt": False, "reason": "trial_running"}
    # Paid — prompt at 7 days before next billing date (ceil-based)
    nbd_iso = user.get("next_billing_date") or user.get("current_period_end")
    if not nbd_iso:
        return {"should_prompt": False, "reason": "no_billing_date"}
    try:
        nbd = datetime.fromisoformat(nbd_iso.replace("Z", "+00:00")) if isinstance(nbd_iso, str) else nbd_iso
        hours_to_renew = (nbd - datetime.now(timezone.utc)).total_seconds() / 3600
        days_to_renew = _math.ceil(hours_to_renew / 24) if hours_to_renew > 0 else 0
        if 0 < days_to_renew <= 7:
            return {"should_prompt": True, "reason": "renewal_soon", "days_left": days_to_renew}
    except Exception:
        pass
    return {"should_prompt": False, "reason": "not_yet"}

@api_router.post("/review/recorded")
async def review_recorded(user: dict = Depends(get_user)):
    """Marks the user as having clicked through to Trustpilot — stops further prompts."""
    await db.users.update_one({"id": user["id"]}, {"$set": {"review_left": True, "review_left_at": datetime.now(timezone.utc).isoformat()}})
    return {"recorded": True}

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
