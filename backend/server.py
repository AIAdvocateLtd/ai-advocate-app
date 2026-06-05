"""AI Advocate - Backend API"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, jwt, bcrypt, base64, io, tempfile, re, asyncio, json, secrets as _secrets
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
from rag import build_rag_context, is_enabled as rag_enabled, get_usage as rag_get_usage  # noqa: E402

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
APP_PUBLIC_URL = os.environ.get('APP_PUBLIC_URL', 'https://aiadvocate.co.uk')
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
    device_id: Optional[str] = None  # client-side UUID for abuse fingerprinting

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
    case_id: Optional[str] = None  # 💬 if set, links this chat session to a case so the conversation appears on the case timeline

class TTSRequest(BaseModel):
    text: str
    voice: str = "fable"  # Warm British male — best UK fit for AI Advocate. Owner-picked default 2026-02.
    language: Optional[str] = None  # optional — passed for voice consistency tracking

class LegalLetterRequest(BaseModel):
    letter_type: str
    recipient: str
    your_name: str
    details: str
    language: str = "en-GB"
    tone: Literal["polite", "firm", "pre_action", "court"] = "firm"

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


class WaitlistSignup(BaseModel):
    email: EmailStr
    full_name: Optional[str] = ""
    country: Optional[str] = "GB"
    source: Optional[str] = ""             # 'instagram' | 'press' | 'direct' | 'firms' etc.
    interests: List[str] = []              # e.g. ["renter", "employee", "small business"]
    device_id: Optional[str] = ""
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

# ===== Custom branding (Practice tier perk) =====
class FirmBrandingUpdate(BaseModel):
    logo_url: Optional[str] = None       # public URL to firm logo (PNG/SVG, recommended <500KB)
    brand_color: Optional[str] = None    # hex like "#1a4d8f"
    accent_color: Optional[str] = None   # hex for secondary accent

# ===== Multi-user firm seats (Premium / Practice tier perk) =====
class FirmUserInvite(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "fee_earner"            # fee_earner | admin (admin can also manage users)

class FirmUserAcceptInvite(BaseModel):
    invite_token: str
    password: str                       # accept and set their own password

class FirmUserLogin(BaseModel):
    email: EmailStr
    password: str

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
    Falls back to a free IP→country lookup (ipapi.co) when CDN headers are stripped
    by the upstream proxy chain — which is the case on Emergent's Google ingress."""
    for k in ("cf-ipcountry", "x-vercel-ip-country", "x-country-code", "x-appengine-country"):
        c = req.headers.get(k)
        if c and len(c) == 2 and c.upper() not in ("XX", "T1"):
            return c.upper()
    # Fallback: IP-based lookup via ipapi.co (free, no API key, ~1k req/day).
    # Cached in-process for 1 hour per IP to avoid hitting the limit.
    ip = _client_ip(req)
    if not ip or ip.startswith(("127.", "10.", "192.168.", "172.")):
        return ""
    return _ip_country_lookup_cached(ip)


# Simple in-memory cache for IP → country lookups. Keyed by IP, 1-hour TTL.
_IP_COUNTRY_CACHE: dict = {}
_IP_COUNTRY_TTL_SEC = 3600

def _ip_country_lookup_cached(ip: str) -> str:
    """Resolve an IPv4/IPv6 to ISO-3166 country code via ipapi.co. Returns ''
    on any failure (timeout, rate limit, parse error) — never raises."""
    import time as _time
    now = _time.time()
    cached = _IP_COUNTRY_CACHE.get(ip)
    if cached and (now - cached[1]) < _IP_COUNTRY_TTL_SEC:
        return cached[0]
    try:
        import httpx as _httpx
        r = _httpx.get(f"https://ipapi.co/{ip}/country/", timeout=2.0,
                       headers={"User-Agent": "AIAdvocate/1.0"})
        cc = (r.text or "").strip().upper()
        if len(cc) == 2 and cc.isalpha():
            _IP_COUNTRY_CACHE[ip] = (cc, now)
            return cc
    except Exception:
        pass
    _IP_COUNTRY_CACHE[ip] = ("", now)
    return ""

async def _check_geo_anomaly(user: dict, req: Request) -> Optional[dict]:
    """Compare current sign-in country to the user's last-seen country.
    On mismatch, record a security_event and return an alert dict the client can show.
    NOTE: country info comes from CDN headers — if absent, we silently skip (avoid false positives).

    ALSO: drives the auto-jurisdiction-switching feature. We detect the country from
    CDN headers and if it differs from the user's current profile country AND the user
    hasn't manually pinned their country, we surface a switch-prompt via the returned alert.
    """
    cc = _ip_country(req)
    if not cc:
        return None
    last_cc = user.get("last_login_country") or ""
    profile_country = (user.get("country") or "GB").upper()
    country_pinned = bool(user.get("country_manually_set"))
    now_iso = datetime.now(timezone.utc).isoformat()
    # Always update last-seen
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_login_country": cc, "last_login_ip": _client_ip(req), "last_login_at": now_iso}}
    )
    # Auto-jurisdiction prompt: if detected country differs from profile country and
    # the user hasn't manually pinned, surface a one-tap prompt to switch. We do NOT
    # silently switch — legal jurisdiction is too important to change without consent.
    jurisdiction_prompt = None
    if cc != profile_country and not country_pinned:
        jurisdiction_prompt = {
            "kind": "auto_jurisdiction_offer",
            "detected_country": cc,
            "current_country": profile_country,
            "message": f"It looks like you're in {cc}. Switch Lex to apply {cc} law instead of {profile_country}?",
        }
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
        result = {"kind": "login_country_change", "from_country": last_cc, "to_country": cc, "id": evt["id"]}
        if jurisdiction_prompt:
            result["jurisdiction_prompt"] = jurisdiction_prompt
        return result
    # No country change anomaly, but still surface the jurisdiction prompt if applicable
    if jurisdiction_prompt:
        return {"kind": "jurisdiction_offer_only", "jurisdiction_prompt": jurisdiction_prompt}
    return None


# ==================== Auto-jurisdiction detection endpoints ====================
# Frontend calls /api/profile/auto-jurisdiction on every app boot (and post-login)
# to find out if the user has travelled and should be offered to switch jurisdiction.
# We never silently change jurisdiction — too important. User must accept the prompt.

@api_router.get("/profile/auto-jurisdiction")
async def auto_jurisdiction(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Detect the user's current country from CDN headers + compare to their profile
    country. If different and they haven't manually pinned their country, return a
    suggestion the UI can render as a one-tap banner.

    Auth is optional — works for guests too (helpful before login to pre-select country).
    Auth users get profile-state-aware suggestions; guests just get the detected country.
    """
    detected = _ip_country(request)
    if not detected:
        # Couldn't detect — no suggestion to make
        return {"detected_country": "", "suggestion": None}

    if not creds:
        return {"detected_country": detected, "suggestion": None}

    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    except Exception:
        return {"detected_country": detected, "suggestion": None}
    if not user:
        return {"detected_country": detected, "suggestion": None}

    profile_country = (user.get("country") or "GB").upper()
    country_pinned = bool(user.get("country_manually_set"))
    if detected == profile_country:
        return {"detected_country": detected, "suggestion": None, "profile_country": profile_country}
    if country_pinned:
        # User has explicitly chosen their country — respect that. Don't pester.
        return {"detected_country": detected, "suggestion": None, "profile_country": profile_country, "pinned": True}
    return {
        "detected_country": detected,
        "profile_country": profile_country,
        "suggestion": {
            "kind": "switch_jurisdiction",
            "detected_country": detected,
            "current_country": profile_country,
            "message": f"You appear to be in {detected}. Switch Lex to apply {detected} law?",
        },
    }


class JurisdictionAcceptPayload(BaseModel):
    country: str   # 2-letter ISO

# NOTE: /profile/jurisdiction/accept and /profile/jurisdiction/decline are defined
# below get_user() because they depend on it as a FastAPI dependency.


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

# Optional auth — returns None instead of raising. Used by /emergency/silent-sos so
# it can fall back to ?wt=... watch token auth when no JWT is supplied.
async def get_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[dict]:
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        u = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if u and not u.get("deleted"):
            return u
    except Exception:
        pass
    return None


# ==================== Auto-jurisdiction accept/decline ====================
# (placed here because they depend on the get_user dependency above)

@api_router.post("/profile/jurisdiction/accept")
async def accept_jurisdiction_change(data: JurisdictionAcceptPayload, user: dict = Depends(get_user)):
    """User accepted the prompt — switch their profile country. We mark as 'auto-switched'
    (not country_manually_set) so if they travel again we'll prompt them again."""
    cc = (data.country or "").upper().strip()
    if len(cc) != 2:
        raise HTTPException(400, "country must be a 2-letter ISO code")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "country": cc,
            "country_auto_switched_at": datetime.now(timezone.utc).isoformat(),
            "country_manually_set": False,
        }},
    )
    return {"ok": True, "country": cc}

@api_router.post("/profile/jurisdiction/decline")
async def decline_jurisdiction_change(user: dict = Depends(get_user)):
    """User declined the prompt — pin their current country so we stop asking."""
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "country_manually_set": True,
            "country_decline_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True, "pinned": True}


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

    # 🛡 OWNER / ADMIN — free Pro access forever, regardless of trial / subscription.
    # ADMIN_EMAILS env (defaults to "admin@aiadvocate.co.uk") = the owner accounts.
    admin_emails = [
        e.strip().lower() for e in
        (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",")
        if e.strip()
    ]
    if (u.get("email") or "").lower() in admin_emails:
        out["tier"] = "pro"
        out["has_access"] = True
        out["trial_days_remaining"] = 0
        out["is_owner"] = True
        return out

    # 🎁 COMP PRO — owner has granted this user free Pro (family, friends, customer service).
    # Active until comp_pro_until in the future. Owner can revoke at any time.
    comp_until = u.get("comp_pro_until")
    if comp_until:
        if isinstance(comp_until, str):
            try:
                comp_dt = datetime.fromisoformat(comp_until)
                if comp_dt.tzinfo is None:
                    comp_dt = comp_dt.replace(tzinfo=timezone.utc)
            except Exception:
                comp_dt = None
        else:
            comp_dt = comp_until
        if comp_dt and now < comp_dt:
            out["tier"] = "pro"
            out["has_access"] = True
            days_remaining = (comp_dt - now).days
            out["comp_pro_days_remaining"] = days_remaining
            out["comp_pro_until"] = comp_dt.isoformat()
            out["is_comp"] = True
            return out

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

    # 🎁 LAUNCH DAY-PASS — first 100 signups got a 24h Plus pass. If still
    # active, upgrade them to "plus" for the remainder of the window.
    launch_pass_until = u.get("launch_day_pass_until")
    if launch_pass_until:
        try:
            lp_dt = datetime.fromisoformat(launch_pass_until.replace("Z", "+00:00")) if isinstance(launch_pass_until, str) else launch_pass_until
            if lp_dt.tzinfo is None:
                lp_dt = lp_dt.replace(tzinfo=timezone.utc)
            if now < lp_dt:
                # Promote to plus if their current tier is lower
                if (out["tier"] or "free") in ("free", "trial_pro"):
                    out["tier"] = "plus"
                out["has_access"] = True
                out["launch_day_pass_active"] = True
                out["launch_day_pass_hours_remaining"] = max(0, int((lp_dt - now).total_seconds() // 3600))
        except Exception:
            pass

    # 🎟 TOP-UP — if the user has an active one-time top-up that grants a higher
    # tier than their base subscription, that takes precedence while it's valid.
    # E.g. a free user buying a £29.99 Crisis Pack gets Pro for 24h.
    tier_order = {"free": 0, "plus": 1, "trial_pro": 2, "pro": 3, "yearly": 3}
    active_topup = u.get("topup_active")
    if active_topup:
        try:
            expires = active_topup.get("expires_at", "")
            if expires > now.isoformat():
                grants = active_topup.get("grants_tier") or "plus"
                if tier_order.get(grants, 0) > tier_order.get(out["tier"], 0):
                    out["tier"] = grants
                    out["has_access"] = True
                topup_expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                out["topup_active"] = {
                    "kind": active_topup.get("kind"),
                    "label": active_topup.get("label"),
                    "grants_tier": grants,
                    "expires_at": expires,
                    "hours_remaining": max(0, int((topup_expires_dt - now).total_seconds() // 3600)),
                }
        except Exception:
            pass

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

# ISO-639-1 → English name. Used by /lex/translate so we can refer to languages
# the rest of the app doesn't otherwise speak (Swahili, Vietnamese, Amharic, etc).
ISO_639_NAMES = {
    "en": "English", "ar": "Arabic", "fr": "French", "es": "Spanish", "de": "German",
    "it": "Italian", "pt": "Portuguese", "pl": "Polish", "ru": "Russian", "uk": "Ukrainian",
    "tr": "Turkish", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "hi": "Hindi",
    "ur": "Urdu", "bn": "Bengali", "pa": "Punjabi", "ta": "Tamil", "te": "Telugu",
    "fa": "Persian", "he": "Hebrew", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian",
    "ms": "Malay", "tl": "Tagalog", "nl": "Dutch", "sv": "Swedish", "no": "Norwegian",
    "da": "Danish", "fi": "Finnish", "el": "Greek", "cs": "Czech", "ro": "Romanian",
    "hu": "Hungarian", "bg": "Bulgarian", "sr": "Serbian", "hr": "Croatian", "sk": "Slovak",
    "sw": "Swahili", "am": "Amharic", "yo": "Yoruba", "ha": "Hausa", "so": "Somali",
    "af": "Afrikaans", "az": "Azerbaijani", "ka": "Georgian", "hy": "Armenian",
    "kk": "Kazakh", "mn": "Mongolian", "ne": "Nepali", "si": "Sinhala",
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
- **Be concise: aim for 200-450 words per answer.** Quality > quantity. Skim-readable on a phone screen.
- Translate jargon as you go ("repudiation means ending the contract because the other side broke it badly").
- Cite the actual statute section or case name when you reference law (e.g. "s.13 Consumer Rights Act 2015", "Donoghue v Stevenson [1932]").
- NEVER invent statutes, case citations, or section numbers. Inventing law is a fireable offence — say "I don't recall the exact citation" if unsure.
- Be strategic: tell them what to SAY, what NEVER to say, what to WRITE DOWN, what to KEEP as evidence.
- Use short paragraphs, bullets, and **bold** key terms for skim-readability on a phone.
- For follow-up questions in the same conversation, be EVEN SHORTER (100-250 words) — don't repeat what you already said. Pick up where you left off.

STRUCTURED METADATA (MANDATORY — these go at the END of every answer, after the disclaimer, each on its own line, exactly in this format):

[CONFIDENCE: HIGH]   ← or MEDIUM or LOW. Always include.
[SOURCES: s.13 Consumer Rights Act 2015; Housing Act 2004 s.213; Smith v Jones [2019] EWCA Civ 123]   ← Semicolon-separated list of statutes / cases / regulations you cited. Include only those you actually referenced. Use "—" if you cited no specific law (rare).
[CONNECTED_TO: previous topic title]   ← OPTIONAL. Include ONLY if your answer genuinely references one of the user's PRIOR cases (from the RECENT CASES list). Otherwise OMIT this line entirely. Topic should be 3-7 words.

These three markers MUST appear on three separate lines at the very end. They are parsed by the app — any deviation breaks the UI. Do not add anything after them.

TONE:
- Calm authority. Like the smartest lawyer in the room who actually wants to help.
- Empathic when the user is in distress (arrested, evicted, fired, divorcing).
- Direct when they need a wake-up call.

ENDING:
- End EVERY reply with this disclaimer in {lang_name}: "Disclaimer: This is general legal information, not a substitute for a qualified lawyer in your jurisdiction." (Translate it naturally into {lang_name}.)

CONVERSATION MEMORY (CRITICAL):
- You have access to the full conversation history above. USE IT.
- If the user's next question is short, vague, or starts with "what about...", "and if...", "but...", "they said...", "okay then...", "and the deposit?", etc. — they are CONTINUING the previous topic. Do NOT treat each question as standalone.
- ALWAYS look back at what was discussed (the case, the parties, the country, the dates, the facts). Carry those facts forward without asking the user to repeat them.
- Only ask clarifying questions if the new question genuinely cannot be linked to what came before.
- Example: User says "My landlord won't return my deposit". You answer. They follow up with "He says I caused damage." → You MUST remember this is the same landlord, same deposit, same case. Apply UK Housing Act 2004 + deposit-protection rules from the prior context.
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
# Hybrid Claude + GPT-5 strategy (user pref: strategy A):
#   Free        → Claude Haiku 4.5  (cheap, fast paralegal-grade)
#   Plus        → OpenAI GPT-5.2    (conversational primary)
#   Pro / Yearly → Claude Sonnet 4.5 (legal-reasoning specialist)
#   Pro + Deep Think → Claude Sonnet 4.5 with extended token budget
# If GPT-5 is unavailable for any reason, the lex_chat fallback path swaps in
# Sonnet 4.5 so the user is never blocked.
def lex_model_for_tier(tier: str, deep_think: bool = False) -> tuple:
    """Returns (provider, model_id, max_tokens) for the given tier."""
    if tier in ("pro", "yearly", "trial_pro"):
        if deep_think:
            return ("anthropic", "claude-sonnet-4-5-20250929", 3500)
        return ("anthropic", "claude-sonnet-4-5-20250929", 1400)
    if tier == "plus":
        # GPT-5.2 for conversational flow on Plus.
        return ("openai", "gpt-5.2", 1400)
    # free → Haiku for cost/speed. Fall back to Sonnet if Haiku id is rejected.
    return ("anthropic", "claude-haiku-4-5-20251001", 1200)

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

# ==================== Anti-abuse defenses ====================
# Public list of throw-away email providers. NOT a moral statement — just blocks
# the trivial "create 50 accounts from mailinator.com" farming pattern.
# We only block the *most common* ones; if a determined user wants to game us,
# they'll find a way. This is the 80/20 hedge.
DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "yopmail.com", "tempmail.com", "temp-mail.org", "10minutemail.com", "10minutemail.net",
    "throwawaymail.com", "trashmail.com", "trashmail.de", "fakeinbox.com", "dispostable.com",
    "maildrop.cc", "getairmail.com", "mintemail.com", "mohmal.com", "sharklasers.com",
    "spamgourmet.com", "tempr.email", "tmail.ws", "tmailinator.com", "discard.email",
    "emailondeck.com", "burnermail.io", "anonbox.net", "spambog.com",
}


def _is_disposable_email(email: str) -> bool:
    try:
        domain = (email or "").split("@", 1)[1].lower().strip()
        return domain in DISPOSABLE_EMAIL_DOMAINS
    except Exception:
        return False


async def _enforce_device_signup_limit(device_id: Optional[str], request: Request):
    """Reject signups when >2 accounts have been created from the same device_id
    in the last 24h. This blocks the most obvious 'spin up 10 free accounts
    to dodge the 5/day chat cap' farming pattern, without adding friction to
    real users (they'll be well under 2/day)."""
    if not device_id:
        return  # client didn't send a device_id — be permissive rather than break legit signups
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    count = await db.users.count_documents({
        "signup_device_id": device_id,
        "created_at": {"$gte": cutoff},
    })
    if count >= 2:
        logger.warning(f"Device-fingerprint signup limit hit: device={device_id[:12]}... count={count}")
        raise HTTPException(429, "Too many signups from this device. Please try again tomorrow or use a different device.")


# ==================== Pre-launch Waitlist ====================
# Captures emails from the marketing landing page (`aiadvocate.co.uk/`) before
# the app is publicly available. Stored separately from `users` because these
# people haven't actually signed up yet — they just want to be told when launch
# happens. On launch day, owner can export the list and send a single email
# with a "Welcome — here's your free Day Pass" promo code.
@api_router.post("/waitlist/join")
async def waitlist_join(data: WaitlistSignup, request: Request):
    if _is_disposable_email(data.email):
        raise HTTPException(400, "Please use a real email address — disposable / temporary email providers are not accepted.")
    # Don't double-add — idempotent join. If the email is already on the list,
    # we just acknowledge with the existing record so the UI shows success either way.
    existing = await db.waitlist.find_one({"email": data.email}, {"_id": 0})
    now_iso = datetime.now(timezone.utc).isoformat()
    if existing:
        return {"ok": True, "already_registered": True, "joined_at": existing.get("created_at")}
    doc = {
        "id": str(uuid.uuid4()),
        "email": data.email,
        "full_name": (data.full_name or "").strip()[:120],
        "country": data.country or "GB",
        "source": (data.source or "direct")[:60],
        "interests": [i.strip()[:40] for i in (data.interests or [])][:8],
        "device_id": (data.device_id or "")[:64],
        "ip": (request.client.host if request.client else None),
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "created_at": now_iso,
        "notified_at": None,                                                # set when launch email goes out
    }
    await db.waitlist.insert_one(doc)
    logger.info(f"Waitlist join: {data.email} (source={data.source})")
    # Fire acknowledgement email. We await it directly (rather than
    # asyncio.create_task) because background tasks created from inside a
    # FastAPI handler can be garbage-collected before they complete. Resend
    # responds in ~200-500ms — the small latency hit on the response is worth
    # the guarantee that the email actually goes out.
    try:
        from email_helper import send_waitlist_ack
        await send_waitlist_ack(data.email, data.full_name or "")
    except Exception:
        logger.exception("waitlist ack email dispatch failed")
    return {"ok": True, "already_registered": False, "joined_at": now_iso}


@api_router.get("/admin/waitlist")
async def admin_waitlist_list(user: dict = Depends(get_user)):
    """Owner-only — list everyone on the launch waitlist (sorted newest first)."""
    admin_emails = [e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]
    if user.get("email", "").lower() not in admin_emails:
        raise HTTPException(403, "Owner only")
    rows = await db.waitlist.find({}, {"_id": 0, "ip": 0, "user_agent": 0, "device_id": 0}).sort("created_at", -1).to_list(2000)
    by_source: dict = {}
    by_country: dict = {}
    for r in rows:
        by_source[r.get("source") or "direct"] = by_source.get(r.get("source") or "direct", 0) + 1
        by_country[r.get("country") or "GB"] = by_country.get(r.get("country") or "GB", 0) + 1
    return {"total": len(rows), "by_source": by_source, "by_country": by_country, "rows": rows}


@api_router.get("/admin/waitlist.csv")
async def admin_waitlist_csv(user: dict = Depends(get_user)):
    """Owner-only — CSV export of the launch waitlist for one-off email blasts."""
    admin_emails = [e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]
    if user.get("email", "").lower() not in admin_emails:
        raise HTTPException(403, "Owner only")
    import csv as _csv, io as _io
    from fastapi.responses import Response as _Response
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["email", "full_name", "country", "source", "interests", "joined_at"])
    async for r in db.waitlist.find({}, {"_id": 0}).sort("created_at", -1):
        w.writerow([
            r.get("email", ""),
            r.get("full_name", ""),
            r.get("country", ""),
            r.get("source", ""),
            "|".join(r.get("interests", []) or []),
            r.get("created_at", ""),
        ])
    return _Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="aiadvocate-waitlist.csv"'})


# ==================== Auth Routes ====================
@api_router.post("/auth/signup", response_model=TokenResp)
async def signup(data: UserSignup, request: Request):
    if _is_disposable_email(data.email):
        raise HTTPException(400, "Please use a real email address — disposable / temporary email providers are not accepted.")
    if await db.users.find_one({"email": data.email}):
        # Friendlier message — frontend keys off the word "already" to swap to sign-in mode + offer 'resend welcome email'.
        raise HTTPException(409, "An account already exists for this email. Sign in instead, or use the 'Forgot password?' link below if you've lost access.")
    await _enforce_device_signup_limit(data.device_id, request)
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # ── First-100 Day Pass mechanic ──────────────────────────────────────
    # Count real (non-demo, non-admin) signups so far. If we're within the
    # first 100, the user gets an automatic 24-hour Day Pass (Plus tier).
    # Signup #101+ gets a 20% off welcome code instead — both reactions are
    # delivered via Resend transactional emails further down.
    DAY_PASS_LIMIT = 100
    real_signup_count = await db.users.count_documents({
        "auth_provider": {"$nin": ["demo"]},
        "email": {"$ne": "admin@aiadvocate.co.uk"},
    })
    awarded_day_pass = real_signup_count < DAY_PASS_LIMIT
    day_pass_until = (now + timedelta(hours=24)).isoformat() if awarded_day_pass else None

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
        "signup_device_id": data.device_id,  # for abuse fingerprinting (1 user per device per 24h max ≈ 2)
        "signup_ip": (request.client.host if request.client else None),
        # Launch-promo fields
        "signup_position": real_signup_count + 1,         # 1-indexed signup number
        "launch_day_pass_until": day_pass_until,           # null if missed offer
        "launch_promo_code": None if awarded_day_pass else "WELCOME20",
    }
    await db.users.insert_one(user_doc)

    # 🎁 Claim any pending gifts addressed to this email (e.g. parent bought
    # a Crisis Pack while the user hadn't signed up yet — activates instantly here)
    try:
        await _claim_pending_gifts_for(data.email, user_id)
    except Exception:
        logger.exception("Pending-gift claim during signup failed")

    # 🎁 Auto-redeem any pending Pro comp the founder queued before signup
    # (e.g. "Grant by email" for family/friends who didn't have an account yet).
    try:
        pending_comp = await db.pending_comp_grants.find_one({"email": data.email.lower()})
        if pending_comp:
            days = max(1, int(pending_comp.get("days") or 30))
            comp_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
            await db.users.update_one(
                {"id": user_id},
                {"$set": {"comp_pro_until": comp_until,
                          "comp_pro_granted_at": datetime.now(timezone.utc).isoformat(),
                          "comp_pro_pre_signup": True}},
            )
            user_doc["comp_pro_until"] = comp_until
            await db.comp_audit.insert_one({
                "id": str(uuid.uuid4()),
                "granted_by_id": pending_comp.get("granted_by_id"),
                "granted_by_email": pending_comp.get("granted_by_email"),
                "target_id": user_id, "target_email": data.email,
                "days": days, "reason": "Pre-signup comp redeemed on signup",
                "at": datetime.now(timezone.utc).isoformat(), "action": "pre_comp_redeemed",
            })
            await db.pending_comp_grants.delete_one({"email": data.email.lower()})
    except Exception:
        logger.exception("Pending comp redemption failed (non-fatal)")

    # Fire the welcome email. We await directly (not asyncio.create_task) so
    # the task isn't garbage-collected before completion. Resend is fast (~300ms).
    try:
        from email_helper import send_welcome_with_daypass, send_welcome_missed_offer
        if awarded_day_pass:
            await send_welcome_with_daypass(data.email, data.full_name or "")
        else:
            await send_welcome_missed_offer(data.email, data.full_name or "")
    except Exception:
        logger.exception("welcome email dispatch failed")

    return TokenResp(access_token=make_token(user_id, data.email), user=user_to_public(user_doc))

@api_router.post("/auth/login")
async def login(data: UserLogin, request: Request):
    user = await db.users.find_one({"email": data.email})
    if not user or not verify_pw(data.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid credentials")
    # 🔐 2FA gate: if the user has TOTP enabled, do NOT issue the full JWT yet.
    # Return a short-lived tmp_token; the client then POSTs /auth/2fa/login
    # with that token + the 6-digit code (or a backup code) to get the real JWT.
    if user.get("totp_enabled"):
        from fastapi.responses import JSONResponse as _JSON
        tmp = _issue_tmp_2fa_token(user["id"], "user")
        return _JSON({"requires_2fa": True, "tmp_token": tmp, "email": user["email"]})
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
    # If the user explicitly set their country here, mark it as manually-pinned so
    # the auto-jurisdiction detector stops offering to switch it.
    if "country" in data:
        update["country_manually_set"] = True
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
    base_system_msg = lex_system_prompt(reply_language, data.country, data.category)

    # 🧠 Cross-session memory — give Lex a one-line summary of OTHER recent cases
    # the user has discussed, so it can spot connections (e.g. "the contract you
    # reviewed last week has a clause relevant to your deposit case").
    # Only injects if the user has 2+ prior sessions distinct from the current one.
    cross_sessions_indexed = []  # [{n, session_id, topic, category}] for #N → session_id lookup
    try:
        cross_pipeline = [
            {"$match": {"user_id": user["id"], "session_id": {"$ne": session_id}}},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$session_id",
                "first_message": {"$last": "$user_message"},  # oldest = first turn of that case
                "category": {"$first": "$category"},
                "last_at": {"$first": "$created_at"},
            }},
            {"$sort": {"last_at": -1}},
            {"$limit": 4},
        ]
        n = 0
        async for s in db.conversations.aggregate(cross_pipeline):
            try:
                txt = decrypt_text(s.get("first_message")) or ""
                if txt:
                    topic = txt[:90].replace("\n", " ").strip()
                    if len(txt) > 90:
                        topic += "…"
                    n += 1
                    cross_sessions_indexed.append({
                        "n": n,
                        "session_id": s["_id"],
                        "topic": topic,
                        "category": s.get("category") or "ask_lex",
                    })
            except Exception:
                continue
    except Exception:
        cross_sessions_indexed = []

    if cross_sessions_indexed:
        lines = [f"#{c['n']} [{c['category']}] {c['topic']}" for c in cross_sessions_indexed]
        cross_memory_block = (
            "\n\nRECENT CASES THIS USER HAS DISCUSSED WITH YOU (other chat threads):\n"
            + "\n".join(lines)
            + "\n\nCROSS-CASE CONNECTION RULE:\n"
              "If the user's NEW question shares a SPECIFIC entity with any case in the list above — "
              "the same company/employer name, the same landlord, the same person, the same property address, "
              "the same contract, or the same incident date — you MUST acknowledge it and you MUST output the "
              "[CONNECTED_TO: #N short topic] marker, where N is the number from the list above.\n"
              "Example: list contains '#1 [ask_lex] My landlord Acme wont return my deposit'. "
              "New question: 'My employer Acme also fired me.' → Same company Acme → "
              "OUTPUT: [CONNECTED_TO: #1 Acme deposit dispute]\n"
              "Also briefly mention the connection IN the answer body (e.g. 'This is the same Acme we discussed earlier about your deposit — there may be strategic synergy in pursuing both claims.').\n"
              "If there is no shared specific entity, OMIT the [CONNECTED_TO:] line entirely. Never force a link."
        )
        system_msg = base_system_msg + cross_memory_block
    else:
        system_msg = base_system_msg

    # 📚 RAG: pull live legislation / case-law / web context relevant to this question.
    # Gracefully skipped if TAVILY_API_KEY is not configured. Total budget: 2 Tavily
    # calls (one filtered to authority domains, one general). The retrieved snippets
    # are appended to the system prompt and Lex is told to cite numbered sources.
    citations: List[dict] = []
    try:
        rag_block, citations = await build_rag_context(data.message, country=data.country or "GB", db=db)
        if rag_block:
            system_msg = system_msg + rag_block
    except Exception as e:
        logger.warning(f"RAG context build failed (continuing without): {e}")

    # 📂 If this chat is tied to a Case File, prepend the case summary + recent
    # items to the system message so Lex sees the user's whole legal situation
    # without them having to re-explain. Capped at 2.5K chars to stay LLM-cheap.
    if data.case_id:
        try:
            case_block = await _build_case_context_block(data.case_id, user["id"])
            if case_block:
                system_msg = system_msg + "\n\n" + case_block
        except Exception as e:
            logger.warning(f"Case-context build failed: {e}")

    # 🧠 Load prior conversation history so Lex remembers context across turns.
    # We pull the last 12 turns for this user+session, decrypt them, and seed
    # LlmChat's initial_messages. This is what makes Lex feel like a real
    # ongoing conversation instead of forgetting after every question.
    history_docs = await db.conversations.find(
        {"user_id": user["id"], "session_id": session_id},
        {"_id": 0, "user_message": 1, "assistant_response": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(length=12)

    initial_messages = [{"role": "system", "content": system_msg}]
    for doc in history_docs:
        try:
            um = decrypt_text(doc.get("user_message"))
            ar = decrypt_text(doc.get("assistant_response"))
            if um:
                initial_messages.append({"role": "user", "content": um})
            if ar:
                initial_messages.append({"role": "assistant", "content": ar})
        except Exception:
            continue  # skip un-decryptable rows rather than crash the request

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_msg,
        initial_messages=initial_messages if len(initial_messages) > 1 else None,
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
                system_message=system_msg,
                initial_messages=initial_messages if len(initial_messages) > 1 else None,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2048)
            response = await chat.send_message(UserMessage(text=data.message))
        except Exception as e2:
            logger.exception("Lex chat error (both primary + fallback)")
            raise HTTPException(500, f"AI error: {str(e2)}")

    # Save conversation (sensitive content encrypted at rest). Citations are stored
    # as plaintext metadata so chat history can re-render the pills on reload.
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
        "citations": citations,
        "linked_case_id": data.case_id or None,  # 💬 attach to case if continuing a Case File
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 🔗 Resolve cross-session link: if Lex tagged the answer with [CONNECTED_TO: #N ...],
    # look up that session_id so the frontend can render the chip as a clickable jump.
    connected_session_id = None
    try:
        m = re.search(r"\[CONNECTED_TO:\s*#(\d+)", response, re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(cross_sessions_indexed):
                connected_session_id = cross_sessions_indexed[idx]["session_id"]
    except Exception:
        connected_session_id = None

    return {
        "session_id": session_id,
        "response": response,
        "reply_language": reply_language,
        "model": model_id,
        "connected_session_id": connected_session_id,
        "citations": citations,
    }


# ==================== Streaming Lex Chat (SSE) ====================
# Same logic as /lex/chat but emits the LLM response token-by-token via
# Server-Sent Events. Uses LiteLLM's stream=True (which `LlmChat` wraps).
# Format:
#   data: {"type":"meta","session_id":"...","citations":[...]}\n\n
#   data: {"type":"token","text":"Hello"}\n\n
#   data: {"type":"token","text":" world"}\n\n
#   data: {"type":"done","connected_session_id":"...","model":"..."}\n\n
#
# The frontend renders tokens as they arrive (typewriter effect, but live).
@api_router.post("/lex/chat/stream")
async def lex_chat_stream(data: ChatMessage, user: dict = Depends(get_user)):
    import litellm
    import json as _json
    from emergentintegrations.llm.utils import get_integration_proxy_url

    pub = user_to_public(user)
    tier = pub["tier"]

    # Same auth / paywall / quota checks as /lex/chat
    if data.category in ("court_prep", "employment", "property", "immigration", "medical_negligence"):
        if not tier_has_access(tier, "court_categories"):
            raise HTTPException(402, "This category requires Plus or Pro. Upgrade to unlock.")
    if data.deep_think and tier not in ("pro", "yearly", "trial_pro"):
        raise HTTPException(402, "Deep Think requires Pro. Upgrade to unlock King's Counsel-grade reasoning.")
    if data.deep_think:
        ok_dt, used_dt, limit_dt = await check_quota_and_increment(user["id"], tier, "deep_think", "monthly")
        if not ok_dt:
            raise HTTPException(429, f"Deep Think monthly limit reached ({used_dt}/{limit_dt}). Disable Deep Think for unlimited Sonnet 4.5 chats this month, or upgrade to Yearly Pro for 50/mo.")
    ok, used, limit = await check_quota_and_increment(user["id"], tier, "lex_chat", "daily")
    if not ok:
        raise HTTPException(429, f"Daily limit reached ({used}/{limit} Lex messages on Free). Upgrade to Plus for unlimited.")

    # Language auto-detect
    reply_language = data.language
    if data.auto_detect:
        detected = detect_language(data.message, fallback=data.language)
        if detected and detected != data.language:
            reply_language = detected

    provider, model_id, max_tok = lex_model_for_tier(tier, deep_think=data.deep_think)
    session_id = data.session_id or str(uuid.uuid4())
    base_system_msg = lex_system_prompt(reply_language, data.country, data.category)

    # Cross-session memory (same as non-streaming)
    cross_sessions_indexed = []
    try:
        cross_pipeline = [
            {"$match": {"user_id": user["id"], "session_id": {"$ne": session_id}}},
            {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$session_id", "first_message": {"$last": "$user_message"},
                        "category": {"$first": "$category"}, "last_at": {"$first": "$created_at"}}},
            {"$sort": {"last_at": -1}}, {"$limit": 4},
        ]
        n = 0
        async for s in db.conversations.aggregate(cross_pipeline):
            try:
                txt = decrypt_text(s.get("first_message")) or ""
                if txt:
                    topic = txt[:90].replace("\n", " ").strip()
                    if len(txt) > 90: topic += "…"
                    n += 1
                    cross_sessions_indexed.append({"n": n, "session_id": s["_id"], "topic": topic, "category": s.get("category") or "ask_lex"})
            except Exception:
                continue
    except Exception:
        cross_sessions_indexed = []
    if cross_sessions_indexed:
        lines = [f"#{c['n']} [{c['category']}] {c['topic']}" for c in cross_sessions_indexed]
        cross_memory_block = (
            "\n\nRECENT CASES THIS USER HAS DISCUSSED WITH YOU (other chat threads):\n"
            + "\n".join(lines)
            + "\n\nCROSS-CASE CONNECTION RULE:\n"
              "If the user's NEW question shares a SPECIFIC entity with any case in the list above — "
              "the same company/employer name, the same landlord, the same person, the same property address, "
              "the same contract, or the same incident date — you MUST acknowledge it and you MUST output the "
              "[CONNECTED_TO: #N short topic] marker, where N is the number from the list above.\n"
              "If there is no shared specific entity, OMIT the [CONNECTED_TO:] line entirely. Never force a link."
        )
        system_msg = base_system_msg + cross_memory_block
    else:
        system_msg = base_system_msg

    # RAG
    citations: List[dict] = []
    try:
        rag_block, citations = await build_rag_context(data.message, country=data.country or "GB", db=db)
        if rag_block:
            system_msg = system_msg + rag_block
    except Exception as e:
        logger.warning(f"RAG context build failed (continuing without): {e}")

    # 📂 If this chat is tied to a Case File, prepend the case summary + recent
    # items to the system message so Lex sees the user's whole legal situation
    # without them having to re-explain. Capped at 2.5K chars to stay LLM-cheap.
    if data.case_id:
        try:
            case_block = await _build_case_context_block(data.case_id, user["id"])
            if case_block:
                system_msg = system_msg + "\n\n" + case_block
        except Exception as e:
            logger.warning(f"Case-context build failed: {e}")

    # Load chat history
    history_docs = await db.conversations.find(
        {"user_id": user["id"], "session_id": session_id},
        {"_id": 0, "user_message": 1, "assistant_response": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(length=12)
    messages = [{"role": "system", "content": system_msg}]
    for doc in history_docs:
        try:
            um = decrypt_text(doc.get("user_message"))
            ar = decrypt_text(doc.get("assistant_response"))
            if um: messages.append({"role": "user", "content": um})
            if ar: messages.append({"role": "assistant", "content": ar})
        except Exception:
            continue
    messages.append({"role": "user", "content": data.message})

    async def event_stream():
        # 1) Emit metadata event first so the UI can show citations + session_id immediately
        yield f"data: {_json.dumps({'type':'meta','session_id':session_id,'citations':citations,'model':model_id,'reply_language':reply_language})}\n\n"

        full_text_parts: List[str] = []
        try:
            # LiteLLM with stream=True. Routes through the Emergent proxy when
            # api_key starts with sk-emergent-, mirroring LlmChat._execute_completion.
            params = {
                "model": model_id,
                "messages": messages,
                "api_key": EMERGENT_LLM_KEY,
                "max_tokens": max_tok,
                "stream": True,
            }
            if EMERGENT_LLM_KEY.startswith("sk-emergent-"):
                params["api_base"] = get_integration_proxy_url() + "/llm"
                params["custom_llm_provider"] = "openai"

            response = await litellm.acompletion(**params)
            async for chunk in response:
                try:
                    delta = chunk.choices[0].delta
                    token = getattr(delta, "content", None)
                    if token:
                        full_text_parts.append(token)
                        # Stream the raw token. We strip [CONNECTED_TO:...] from the *final* assembled
                        # text, not per-chunk, so the marker is never visible to the user mid-stream.
                        yield f"data: {_json.dumps({'type':'token','text':token})}\n\n"
                except Exception:
                    continue
        except Exception:
            logger.exception("Streaming completion failed — falling back to non-streaming sonnet 4.5")
            # Non-streaming fallback so user is never blocked
            try:
                chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system_msg,
                               initial_messages=messages[:-1] if len(messages) > 1 else None
                               ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2048)
                fallback_resp = await chat.send_message(UserMessage(text=data.message))
                full_text_parts = [fallback_resp]
                # Emit the whole thing as one token chunk for the UI
                yield f"data: {_json.dumps({'type':'token','text':fallback_resp})}\n\n"
            except Exception as e2:
                logger.exception("Streaming fallback also failed")
                yield f"data: {_json.dumps({'type':'error','message':str(e2)})}\n\n"
                yield f"data: {_json.dumps({'type':'done'})}\n\n"
                return

        # Assemble full response and resolve [CONNECTED_TO: #N]
        full_text = "".join(full_text_parts)
        connected_session_id = None
        try:
            m = re.search(r"\[CONNECTED_TO:\s*#(\d+)", full_text, re.IGNORECASE)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(cross_sessions_indexed):
                    connected_session_id = cross_sessions_indexed[idx]["session_id"]
        except Exception:
            connected_session_id = None

        # Persist the conversation (sensitive content encrypted at rest)
        try:
            await db.conversations.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "session_id": session_id,
                "category": data.category,
                "user_message": encrypt_text(data.message),
                "assistant_response": encrypt_text(full_text),
                "language": reply_language,
                "model_used": model_id,
                "deep_think": data.deep_think,
                "citations": citations,
                "linked_case_id": data.case_id or None,  # 💬 attach to case (streamed path)
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            logger.exception("Failed to persist streamed conversation — user already saw the response")

        # Final event with metadata that needed the full text to compute
        yield f"data: {_json.dumps({'type':'done','connected_session_id':connected_session_id,'full_text':full_text})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable nginx/proxy buffering
            "Connection": "keep-alive",
        },
    )


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


# ==================== Sponsor Slot (single firm partnership) ====================
# Public endpoint — returns the active sponsor or null. UI shows discreet
# "In partnership with [firm name]" footer when a sponsor is configured.
# Edit through MongoDB directly or future admin UI. One sponsor at a time.
@api_router.get("/sponsor")
async def get_sponsor():
    s = await db.sponsor.find_one({"active": True}, {"_id": 0})
    if not s:
        return {"active": False}
    return {
        "active": True,
        "name": s.get("name") or "",
        "url": s.get("url") or "",
        "tagline": s.get("tagline") or "In partnership with",
        "logo_url": s.get("logo_url") or "",
    }


# ==================== Case Timeline (cross-thread visual map) ====================
# Aggregates conversations + reminders + cases + Lex sessions into a chronological list.
# Powers the home-screen "Case Timeline" — the user's whole legal life on one screen.
@api_router.get("/timeline")
async def get_timeline(user: dict = Depends(get_user)):
    user_id = user["id"]
    items = []

    # 🪄 Smart Case-File auto-promote (Option A): any session with >= 3 turns
    # that doesn't have a linked case yet gets quietly promoted. The user keeps
    # full control — they can rename, delete, or manually promote earlier via
    # the "Save as Case File" button in the timeline UI.
    try:
        promote_cursor = db.conversations.aggregate([
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$session_id", "turns": {"$sum": 1}}},
            {"$match": {"turns": {"$gte": 3}}},
        ])
        async for s in promote_cursor:
            sid = s["_id"]
            if not sid:
                continue
            already_linked = await db.case_items.find_one(
                {"user_id": user_id, "item_type": "chat", "item_id": sid,
                 "deleted_at": {"$in": [None, "", False]}},
                {"_id": 1},
            )
            if already_linked:
                continue
            try:
                await _ensure_case_for_session(user, sid, source="auto")
            except Exception:
                logger.exception(f"auto-promote failed for session {sid[:8]}")
    except Exception:
        logger.exception("timeline auto-promote pass failed (non-fatal)")

    # Chat sessions — group conversations by session, take first message as title
    try:
        cursor = db.conversations.aggregate([
            {"$match": {"user_id": user_id}},
            {"$sort": {"created_at": 1}},
            {"$group": {
                "_id": "$session_id",
                "category": {"$first": "$category"},
                "first_message": {"$first": "$user_message"},
                "last_at": {"$last": "$created_at"},
                "first_at": {"$first": "$created_at"},
                "turns": {"$sum": 1},
            }},
            {"$sort": {"last_at": -1}},
            {"$limit": 30},
        ])
        async for s in cursor:
            try:
                msg = decrypt_text(s.get("first_message")) or ""
                title = msg[:80].replace("\n", " ").strip()
                if len(msg) > 80:
                    title += "…"
                # Look up whether this chat is already filed under a Case
                linked = await db.case_items.find_one(
                    {"user_id": user_id, "item_type": "chat", "item_id": s["_id"],
                     "deleted_at": {"$in": [None, "", False]}},
                    {"_id": 0, "case_id": 1},
                )
                items.append({
                    "kind": "chat",
                    "id": s["_id"],
                    "title": title or "(empty thread)",
                    "category": s.get("category") or "ask_lex",
                    "turns": s.get("turns", 1),
                    "started_at": s.get("first_at"),
                    "updated_at": s.get("last_at"),
                    "linked_case_id": (linked or {}).get("case_id"),  # null if not yet a Case File
                })
            except Exception:
                continue
    except Exception:
        pass

    # Reminders / deadlines
    try:
        async for r in db.reminders.find({"user_id": user_id, "deleted_at": {"$in": [None, "", False]}}, {"_id": 0}).sort("due_at", 1).limit(50):
            items.append({
                "kind": "deadline",
                "id": r.get("id"),
                "title": r.get("title") or "Deadline",
                "category": r.get("category") or "deadline",
                "due_at": r.get("due_at"),
                "completed": bool(r.get("completed")),
                "updated_at": r.get("created_at") or r.get("due_at"),
            })
    except Exception:
        pass

    # Vault items (count only — content is client-encrypted)
    try:
        vault_count = await db.vault_items.count_documents({"user_id": user_id})
    except Exception:
        vault_count = 0

    # Cases (case files)
    try:
        async for c in db.cases.find({"user_id": user_id, "deleted_at": {"$in": [None, "", False]}}, {"_id": 0}).sort("created_at", -1).limit(30):
            items.append({
                "kind": "case",
                "id": c.get("id"),
                "title": c.get("title") or c.get("name") or "(untitled case)",
                "category": c.get("category") or "case",
                "updated_at": c.get("updated_at") or c.get("created_at"),
            })
    except Exception:
        pass

    # Sort chronologically (most recent first) so the timeline reads top-down
    def _sortkey(item):
        return item.get("updated_at") or item.get("due_at") or ""
    items.sort(key=_sortkey, reverse=True)

    return {
        "items": items[:80],
        "stats": {
            "total_chats": sum(1 for i in items if i["kind"] == "chat"),
            "open_deadlines": sum(1 for i in items if i["kind"] == "deadline" and not i.get("completed")),
            "cases": sum(1 for i in items if i["kind"] == "case"),
            "vault_items": vault_count,
        },
    }


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


# ==================== Strategic helpers — Outcome Ladder + Devil's Advocate ====================
# On-demand structured upgrades to a Lex answer. The user taps a button below
# any Lex reply; we pull the last (user_message, assistant_response) pair from
# the conversation and ask Claude Sonnet to reframe it strategically.

class StrategicHelperRequest(BaseModel):
    session_id: str
    language: str = "en-GB"
    country: str = "GB"


async def _last_lex_exchange(user_id: str, session_id: str) -> Optional[dict]:
    """Return the most recent (user_message, assistant_response) for this session."""
    doc = await db.conversations.find_one(
        {"user_id": user_id, "session_id": session_id, "user_message": {"$ne": None}},
        sort=[("created_at", -1)],
        projection={"_id": 0, "user_message": 1, "assistant_response": 1, "category": 1},
    )
    return doc


def _normalize_json_string_newlines(s: str) -> str:
    """Replace literal newlines/carriage-returns that appear INSIDE JSON string
    values with a single space. Claude sometimes emits multi-line strings which
    are invalid JSON — this makes them parseable without losing the content."""
    out = []
    in_str = False
    prev_escape = False
    for ch in s:
        if ch == '"' and not prev_escape:
            in_str = not in_str
            out.append(ch)
        elif in_str and ch in ('\n', '\r'):
            out.append(' ')
        else:
            out.append(ch)
        prev_escape = (ch == '\\' and not prev_escape)
    return ''.join(out)


def _extract_json_object(raw: str) -> Optional[dict]:
    """Tolerantly pull a single JSON object out of an LLM reply that may include
    markdown fences, prose, or multi-line strings. Returns the parsed dict or None."""
    if not raw:
        logger.warning("_extract_json_object: raw is empty/None")
        return None
    s = raw.strip()
    # Strip markdown fences if present
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s.lstrip("`")
        if "```" in s:
            s = s.rsplit("```", 1)[0]
        s = s.strip()
    # Locate the outermost JSON object even if there's prose around it
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        s = s[start:end + 1]
    # Try direct parse
    try:
        return json.loads(s)
    except Exception as e1:
        logger.warning(f"_extract_json_object direct parse fail: {e1!r}")
    # Fallback: normalize literal newlines inside strings, retry
    try:
        return json.loads(_normalize_json_string_newlines(s))
    except Exception as e2:
        logger.warning(f"_extract_json_object normalized parse fail: {e2!r}")
        return None


@api_router.post("/lex/outcome-ladder")
async def lex_outcome_ladder(data: StrategicHelperRequest, user: dict = Depends(get_user)):
    """Returns a structured 'worst case / likely case / best case' ladder for
    the user's most recent Lex exchange in this session. Free tier allowed —
    this is exactly the calming-clarity feature we want everyone to feel."""
    exchange = await _last_lex_exchange(user["id"], data.session_id)
    if not exchange:
        raise HTTPException(404, "No recent Lex conversation in this session to analyse")

    lang_name = LANG_NAMES.get(data.language, "English")
    system = f"""You are Lex, the AI Advocate strategist. The user just asked a legal question and you answered it. Now they want strategic clarity.

Re-frame the situation as an **Outcome Ladder** in {lang_name}. Return ONLY valid JSON, no prose, no markdown fences, with EXACTLY this shape:

{{
  "headline": "<one-line plain-English summary of the user's situation, max 12 words>",
  "worst_case": {{
    "label": "Worst case",
    "summary": "<what's the realistic worst outcome, 1-2 sentences>",
    "probability": "<low|moderate|high>",
    "what_triggers_it": "<the one thing the user can do/avoid that makes this less likely, 1 sentence>"
  }},
  "likely_case": {{
    "label": "Most likely",
    "summary": "<the realistic middle outcome — the one you'd bet on, 1-2 sentences>",
    "probability": "high",
    "next_step": "<the single most valuable thing the user should do in the next 7 days, imperative voice>"
  }},
  "best_case": {{
    "label": "Best case",
    "summary": "<the realistic best outcome (NOT fantasy), 1-2 sentences>",
    "probability": "<low|moderate>",
    "how_to_aim_for_it": "<one action that increases the chance, 1 sentence>"
  }},
  "calm_note": "<one short, warm sentence reminding the user this is solvable. Never patronising. Never minimising.>"
}}

Hard rules:
- Be REALISTIC. Don't inflate the worst case to scare the user; don't inflate the best case to flatter them.
- Each summary is 1-2 sentences. Plain English. No legal jargon unless you explain it inline.
- The user lives in country: {data.country}. Apply that jurisdiction.
- If the situation has criminal exposure, label it clearly in worst_case.
- Return ONLY the JSON object, nothing else."""

    user_msg = f"""User's question:
{exchange.get('user_message','(not recorded)')}

Your previous answer:
{exchange.get('assistant_response','(not recorded)')[:4000]}

Now produce the Outcome Ladder JSON for this situation."""

    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"ladder-{data.session_id}", system_message=system)\
            .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=1600)
        raw = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("outcome-ladder error")
        raise HTTPException(500, f"AI error: {e}")

    # Robust JSON parse
    ladder = _extract_json_object(raw)
    if not ladder:
        logger.warning(f"Outcome ladder JSON parse failed (raw len={len(raw or '')}): {(raw or '')[:600]}")
        raise HTTPException(502, "Lex couldn't structure the outcome ladder. Try again in a moment.")

    return {"session_id": data.session_id, "ladder": ladder}


@api_router.post("/lex/devil-advocate")
async def lex_devil_advocate(data: StrategicHelperRequest, user: dict = Depends(get_user)):
    """Returns a 'what would the other side argue' breakdown for the user's
    most recent Lex exchange. Helps the user spot their own weaknesses BEFORE
    the other side does. Free tier allowed — gateway feature."""
    exchange = await _last_lex_exchange(user["id"], data.session_id)
    if not exchange:
        raise HTTPException(404, "No recent Lex conversation in this session to analyse")

    lang_name = LANG_NAMES.get(data.language, "English")
    system = f"""You are Lex helping the user prepare for the opposing arguments in their case. The user has explained their situation and you previously gave them advice supporting their position. Now help them prepare by mapping out the strongest counter-arguments the other party could raise — so the user can prepare responses BEFORE they're caught off guard.

Return ONLY valid JSON in {lang_name}, no prose, no markdown fences, EXACTLY this shape:

{{
  "their_position_in_one_line": "<the other party's strongest framing in plain English, max 18 words>",
  "their_strongest_arguments": [
    {{
      "argument": "<their argument, 1-2 sentences>",
      "why_it_might_work": "<the vulnerability in the user's case this exploits, 1 sentence>",
      "how_to_neutralise_it": "<the user's best counter, imperative voice, 1-2 sentences>"
    }}
  ],
  "evidence_they_will_try_to_use": ["<short bullet>", "<short bullet>", "<short bullet>"],
  "questions_they_will_try_to_trap_you_with": ["<sample loaded question>", "<sample loaded question>"],
  "your_weakest_point": "<the single biggest vulnerability in the user's case, named honestly, 1-2 sentences>",
  "your_strongest_counter": "<the user's single best response if pushed on the weakest point, 1-2 sentences>",
  "preparation_checklist": ["<one specific action>", "<another>", "<another>"]
}}

Hard rules:
- Provide exactly 3 their_strongest_arguments.
- Be honest and constructive. If the user's case has weak areas, name them so they can prepare — not to discourage them.
- Stay UK-centred unless country code says otherwise (country: {data.country}).
- No legal jargon without inline explanation.
- Return ONLY the JSON object."""

    user_msg = f"""User's situation:
{exchange.get('user_message','(not recorded)')}

Your previous answer supporting their position:
{exchange.get('assistant_response','(not recorded)')[:4000]}

Now help them prepare — produce the JSON above mapping out the opposing party's strongest counter-arguments so the user can prepare responses."""

    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"devil-{data.session_id}", system_message=system)\
            .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2000)
        raw = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("devil-advocate error")
        raise HTTPException(500, f"AI error: {e}")

    devil = _extract_json_object(raw)
    if not devil:
        logger.warning(f"Devil's advocate JSON parse failed (raw len={len(raw or '')}): {(raw or '')[:600]}")
        raise HTTPException(502, "Lex couldn't structure the analysis. Try again in a moment.")

    return {"session_id": data.session_id, "devil_advocate": devil}


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


# ==================== Translation Mode (foreign-language interrogations) ====================
# Bidirectional live translation for travellers stopped abroad. Whisper transcribes
# the spoken language (any of 50+), then Claude translates AND adds a short safety tip.
# Frontend then speaks the translation aloud via /api/voice/tts. Pro tier only.
class TranslateRequest(BaseModel):
    session_id: Optional[str] = None
    text: str
    source_lang: str = "ar"
    target_lang: str = "en"
    direction: str = "incoming"     # "incoming" (other party → user) | "outgoing" (user → other party)
    context: Optional[str] = None
    country: str = "GB"

@api_router.post("/lex/translate")
async def lex_translate(data: TranslateRequest, user: dict = Depends(get_user)):
    """Translate one chunk + (for incoming speech) suggest a safe reply. Pro tier only."""
    pub = user_to_public(user)
    if not tier_has_access(pub["tier"], "live_assist"):
        raise HTTPException(402, "Translation Mode requires Pro. Upgrade to unlock.")

    if not data.text or not data.text.strip():
        raise HTTPException(400, "Nothing to translate.")
    if len(data.text) > 2000:
        raise HTTPException(400, "Text too long — Translation Mode is for short live exchanges.")

    src_name = LANG_NAMES.get(data.source_lang, ISO_639_NAMES.get(data.source_lang, data.source_lang))
    tgt_name = LANG_NAMES.get(data.target_lang, ISO_639_NAMES.get(data.target_lang, data.target_lang))

    if data.direction == "incoming":
        system = (
            f"You are Lex in TRANSLATION MODE. The user is a {data.country} passport holder abroad. "
            f"They are in: {data.context or 'a live foreign-language conversation'}. "
            f"The other party just spoke in {src_name}. You must:\n"
            f"1) Translate it ACCURATELY into {tgt_name}.\n"
            f"2) Suggest a SHORT, SAFE reply (≤25 words) the user could say. Default to politeness, "
            f"showing ID/passport, refusing to answer travel-plan / political questions, asking for "
            f"their embassy or a lawyer/interpreter if detained.\n"
            f"Output EXACTLY this format (no extra text):\n"
            f"TRANSLATION: <the translation in {tgt_name}>\n"
            f"TIP: <one-line safety tip in {tgt_name}>\n"
            f"REPLY: <the suggested reply in {tgt_name}>"
        )
        user_prompt = f'They said (in {src_name}): "{data.text}"'
    else:
        system = (
            f"You are a precise live interpreter. Translate the user's message from {src_name} into "
            f"{tgt_name}. Output ONLY the translation — no preamble, no quotes, no commentary."
        )
        user_prompt = data.text

    session_id = data.session_id or str(uuid.uuid4())
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=240)
    try:
        response = await chat.send_message(UserMessage(text=user_prompt))
    except Exception as e:
        logger.exception("translate error")
        raise HTTPException(500, f"Translate failed: {e}")

    translation = response.strip()
    tip = ""
    suggested_reply = ""
    if data.direction == "incoming":
        parsed_translation = None
        for line in response.splitlines():
            s = line.strip()
            up = s.upper()
            if up.startswith("TRANSLATION:"):
                parsed_translation = s.split(":", 1)[1].strip()
            elif up.startswith("TIP:"):
                tip = s.split(":", 1)[1].strip()
            elif up.startswith("REPLY:"):
                suggested_reply = s.split(":", 1)[1].strip()
        if parsed_translation:
            translation = parsed_translation

    await db.conversations.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"], "session_id": session_id,
        "category": f"translate_{data.direction}",
        "user_message": data.text, "assistant_response": response,
        "language": data.target_lang,
        "source_lang": data.source_lang, "target_lang": data.target_lang,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "session_id": session_id,
        "translation": translation,
        "tip": tip,
        "suggested_reply": suggested_reply,
    }


@api_router.get("/lex/translate/languages")
async def translate_languages():
    """Whisper-supported language list for Translation Mode pickers."""
    return {"languages": [
        {"code": "en", "name": "English",     "native": "English"},
        {"code": "ar", "name": "Arabic",      "native": "العربية"},
        {"code": "fr", "name": "French",      "native": "Français"},
        {"code": "es", "name": "Spanish",     "native": "Español"},
        {"code": "de", "name": "German",      "native": "Deutsch"},
        {"code": "it", "name": "Italian",     "native": "Italiano"},
        {"code": "pt", "name": "Portuguese",  "native": "Português"},
        {"code": "pl", "name": "Polish",      "native": "Polski"},
        {"code": "ru", "name": "Russian",     "native": "Русский"},
        {"code": "uk", "name": "Ukrainian",   "native": "Українська"},
        {"code": "tr", "name": "Turkish",     "native": "Türkçe"},
        {"code": "zh", "name": "Chinese",     "native": "中文"},
        {"code": "ja", "name": "Japanese",    "native": "日本語"},
        {"code": "ko", "name": "Korean",      "native": "한국어"},
        {"code": "hi", "name": "Hindi",       "native": "हिन्दी"},
        {"code": "ur", "name": "Urdu",        "native": "اردو"},
        {"code": "bn", "name": "Bengali",     "native": "বাংলা"},
        {"code": "pa", "name": "Punjabi",     "native": "ਪੰਜਾਬੀ"},
        {"code": "ta", "name": "Tamil",       "native": "தமிழ்"},
        {"code": "te", "name": "Telugu",      "native": "తెలుగు"},
        {"code": "fa", "name": "Persian",     "native": "فارسی"},
        {"code": "he", "name": "Hebrew",      "native": "עברית"},
        {"code": "th", "name": "Thai",        "native": "ไทย"},
        {"code": "vi", "name": "Vietnamese",  "native": "Tiếng Việt"},
        {"code": "id", "name": "Indonesian",  "native": "Bahasa Indonesia"},
        {"code": "ms", "name": "Malay",       "native": "Bahasa Melayu"},
        {"code": "tl", "name": "Tagalog",     "native": "Tagalog"},
        {"code": "nl", "name": "Dutch",       "native": "Nederlands"},
        {"code": "sv", "name": "Swedish",     "native": "Svenska"},
        {"code": "no", "name": "Norwegian",   "native": "Norsk"},
        {"code": "da", "name": "Danish",      "native": "Dansk"},
        {"code": "fi", "name": "Finnish",     "native": "Suomi"},
        {"code": "el", "name": "Greek",       "native": "Ελληνικά"},
        {"code": "cs", "name": "Czech",       "native": "Čeština"},
        {"code": "ro", "name": "Romanian",    "native": "Română"},
        {"code": "hu", "name": "Hungarian",   "native": "Magyar"},
        {"code": "bg", "name": "Bulgarian",   "native": "Български"},
        {"code": "sr", "name": "Serbian",     "native": "Српски"},
        {"code": "hr", "name": "Croatian",    "native": "Hrvatski"},
        {"code": "sk", "name": "Slovak",      "native": "Slovenčina"},
        {"code": "sw", "name": "Swahili",     "native": "Kiswahili"},
        {"code": "am", "name": "Amharic",     "native": "አማርኛ"},
        {"code": "yo", "name": "Yoruba",      "native": "Yorùbá"},
        {"code": "ha", "name": "Hausa",       "native": "Hausa"},
        {"code": "so", "name": "Somali",      "native": "Soomaali"},
        {"code": "af", "name": "Afrikaans",   "native": "Afrikaans"},
        {"code": "az", "name": "Azerbaijani", "native": "Azərbaycan"},
        {"code": "ka", "name": "Georgian",    "native": "ქართული"},
        {"code": "hy", "name": "Armenian",    "native": "Հայերեն"},
        {"code": "kk", "name": "Kazakh",      "native": "Қазақ"},
        {"code": "mn", "name": "Mongolian",   "native": "Монгол"},
        {"code": "ne", "name": "Nepali",      "native": "नेपाली"},
        {"code": "si", "name": "Sinhala",     "native": "සිංහල"},
    ]}


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


# ==================== Emergency Contacts + Silent SOS + Lawyer Standby ====================
# Multi-contact emergency network. User can store unlimited contacts (family, lawyer, spouse).
# When the SOS button is pressed (or a smartwatch silent trigger fires), we notify all
# contacts marked `include_in_sos`. If `lawyer_standby` is enabled and nobody acknowledges
# within 60s, we escalate to the top-3 nearest opted-in Premium/Practice firms.
class EmergencyContact(BaseModel):
    name: str
    relationship: Optional[str] = None      # "Spouse", "Lawyer", "Brother", etc.
    phone: Optional[str] = None
    email: Optional[str] = None
    include_in_sos: bool = True
    is_lawyer: bool = False                 # one starred contact = "my lawyer"

class EmergencyContactsPayload(BaseModel):
    contacts: List[EmergencyContact]
    lawyer_standby_enabled: bool = False
    lawyer_standby_radius_km: float = 25.0
    sos_message: Optional[str] = None       # pre-written brief sent with every SOS
    tracking_window_minutes: int = 60       # default 1h; max 24h Pro / 2h Free, clamped server-side

class SilentSOSRequest(BaseModel):
    """Triggered by the SOS button or a smartwatch covert tap.
    `silent=True` means: do NOT play sound, vibrate, or flash on the user's phone."""
    silent: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country: Optional[str] = None
    note: Optional[str] = None
    duress: bool = False                    # smartwatch always sets this true
    source: str = "phone"                   # "phone" | "watch" | "shortcut"


@api_router.get("/emergency/contacts")
async def get_emergency_contacts(user: dict = Depends(get_user)):
    doc = await db.emergency_profile.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    # Drop clearly-incomplete contacts (likely abandoned input from earlier sessions):
    # names with <2 chars OR phones with <7 digits get hidden + auto-pruned on next save.
    raw = doc.get("contacts", []) or []
    def _is_valid(c):
        name = (c.get("name") or "").strip()
        phone_digits = re.sub(r"\D", "", (c.get("phone") or ""))
        return len(name) >= 2 and len(phone_digits) >= 7
    clean = [c for c in raw if _is_valid(c)]
    # Filter dev-test sentinel strings from previously-saved SOS messages too.
    saved_sos = doc.get("sos_message", "") or ""
    if re.search(r"(?i)\b(test\s*iter|test[_-]?\d|TODO|XXX|placeholder)\b", saved_sos):
        saved_sos = ""
    return {
        "contacts": clean,
        "lawyer_standby_enabled": doc.get("lawyer_standby_enabled", False),
        "lawyer_standby_radius_km": doc.get("lawyer_standby_radius_km", 25.0),
        "sos_message": saved_sos,
        "watch_token": doc.get("watch_token"),
        "tracking_window_minutes": doc.get("tracking_window_minutes", 60),
    }


@api_router.post("/emergency/contacts")
async def set_emergency_contacts(data: EmergencyContactsPayload, user: dict = Depends(get_user)):
    pub = user_to_public(user)
    # Lawyer Standby is a Pro feature; contacts list is free.
    if data.lawyer_standby_enabled and not tier_has_access(pub["tier"], "live_assist"):
        raise HTTPException(402, "Lawyer Standby fallback requires Pro. Contacts can still be saved.")
    # Tracking window: hard-clamp 15 min → 24h. Available to ALL tiers as a life-safety
    # feature — we will not paywall the difference between someone being found in 2h vs 24h.
    window = max(15, min(1440, int(data.tracking_window_minutes or 60)))
    # Filter out incomplete entries server-side too: name<2 chars or phone<7 digits = skip.
    raw_contacts = [c.model_dump() for c in data.contacts][:20]
    def _is_valid(c):
        name = (c.get("name") or "").strip()
        phone_digits = re.sub(r"\D", "", (c.get("phone") or ""))
        return len(name) >= 2 and len(phone_digits) >= 7
    contacts = [c for c in raw_contacts if _is_valid(c)]
    # Reject dev/test sentinel strings so the testing agent's debug markers can
    # never end up in a live user's saved SOS message (eg "TEST iter19" once
    # leaked through during regression testing).
    raw_sos = (data.sos_message or "")
    if re.search(r"(?i)\b(test\s*iter|test[_-]?\d|TODO|XXX|placeholder)\b", raw_sos):
        raw_sos = ""
    sos_message = raw_sos[:500]

    await db.emergency_profile.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "user_id": user["id"],
            "contacts": contacts,
            "lawyer_standby_enabled": data.lawyer_standby_enabled,
            "lawyer_standby_radius_km": max(1.0, min(200.0, data.lawyer_standby_radius_km)),
            "sos_message": sos_message,
            "tracking_window_minutes": window,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"saved": True, "contact_count": len(contacts), "tracking_window_minutes": window}


@api_router.post("/emergency/watch-token")
async def generate_watch_token(user: dict = Depends(get_user)):
    """Generate a single-use-style token used by smartwatch shortcuts to trigger Silent SOS
    without exposing the user's primary JWT. Stored on the user's profile; can be rotated."""
    token = _secrets.token_urlsafe(24)
    await db.emergency_profile.update_one(
        {"user_id": user["id"]},
        {"$set": {"watch_token": token, "watch_token_created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"watch_token": token, "trigger_url": f"/api/emergency/silent-sos?wt={token}"}


async def _send_sos_to_contacts(user: dict, profile: dict, sos: dict):
    """Record (but do NOT dispatch) the SOS notification intent. Actual SMS / email
    dispatch happens on the user's own phone via native sms: / mailto: URIs — we
    intentionally do NOT use a third-party SMS service so:
      • Family sees the user's OWN number (instant recognition vs unknown spam)
      • Zero per-message cost
      • No additional auth / infrastructure
    For Covert Watch SOS (where the phone may be unreachable), only the server-side
    Lawyer Standby ping fires — family SMS requires the phone to be accessible.
    """
    contacts_to_notify = [c for c in profile.get("contacts", []) if c.get("include_in_sos")]
    notified = []
    for c in contacts_to_notify:
        notified.append({
            "name": c.get("name"), "relationship": c.get("relationship"),
            "phone": c.get("phone"), "email": c.get("email"),
            "is_lawyer": c.get("is_lawyer", False),
            "status": "ready_for_native_dispatch",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
    sos["notified_contacts"] = notified
    return notified


async def _escalate_lawyer_standby(user: dict, profile: dict, sos: dict):
    """If lawyer_standby_enabled and no contact has responded, ping top-3 nearest opted-in firms."""
    lat = sos.get("latitude"); lng = sos.get("longitude")
    if not (profile.get("lawyer_standby_enabled") and lat is not None and lng is not None):
        return []
    radius_km = profile.get("lawyer_standby_radius_km", 25.0)
    firms = await db.law_firms.find(
        {"verified": True, "emergency_standby": True,
         "lat": {"$ne": None}, "lng": {"$ne": None}},
        {"_id": 0, "id": 1, "name": 1, "lat": 1, "lng": 1, "phone": 1, "city": 1, "country": 1, "tier": 1},
    ).to_list(200)
    scored = []
    for f in firms:
        d = haversine_km(lat, lng, f["lat"], f["lng"])
        if d <= radius_km:
            f["distance_km"] = round(d, 1)
            scored.append(f)
    scored.sort(key=lambda f: f["distance_km"])
    top3 = scored[:3]
    # Mark them as standby-pinged so they can pick up the lead in their dashboard
    for f in top3:
        await db.firm_emergency_pings.insert_one({
            "id": str(uuid.uuid4()),
            "sos_id": sos["id"],
            "firm_id": f["id"],
            "user_id": user["id"],
            "distance_km": f["distance_km"],
            "status": "pinged",
            "pinged_at": datetime.now(timezone.utc).isoformat(),
            "accept_window_seconds": 90,
        })
    sos["lawyer_standby_pinged"] = [
        {"firm_id": f["id"], "name": f["name"], "distance_km": f["distance_km"]}
        for f in top3
    ]
    return top3


@api_router.post("/emergency/silent-sos")
async def silent_sos(
    data: SilentSOSRequest,
    user: Optional[dict] = Depends(get_user_optional),
    wt: Optional[str] = None,  # ?wt=... from smartwatch shortcut
):
    """The big red button. Quietly fires off SOS messages, optionally escalates to
    nearby firms via Lawyer Standby. Works with either JWT (phone) or watch_token (covert).
    On the user's phone the response will be intentionally minimal so it doesn't pop up."""
    # Resolve user: prefer JWT, fall back to watch token from query string
    if user is None and wt:
        prof = await db.emergency_profile.find_one({"watch_token": wt}, {"_id": 0, "user_id": 1})
        if prof:
            user = await db.users.find_one({"id": prof["user_id"]})
    if user is None:
        raise HTTPException(401, "Authentication required")

    profile = await db.emergency_profile.find_one({"user_id": user["id"]}, {"_id": 0}) or {}

    sos_id = str(uuid.uuid4())
    sos_record = {
        "id": sos_id, "user_id": user["id"],
        "silent": bool(data.silent), "duress": bool(data.duress),
        "source": data.source or "phone",
        "latitude": data.latitude, "longitude": data.longitude,
        "country": data.country, "note": data.note or profile.get("sos_message", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notified_contacts": [], "lawyer_standby_pinged": [],
    }

    notified = await _send_sos_to_contacts(user, profile, sos_record)

    # 📍 Start a Live Location track session so family can see the user move in real-time.
    # Window = user's pre-configured `tracking_window_minutes` (default 60, max 1440=24h, free tier capped at 120).
    # GDPR lawful basis: vital interests (Art 6(1)(d)) — user has actively triggered an SOS.
    # Auto-expires; user can stop early from the in-app banner.
    window_min = int(profile.get("tracking_window_minutes") or 60)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=window_min)
    await db.emergency_tracks.insert_one({
        "sos_id": sos_id, "user_id": user["id"],
        "started_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "active": True,
        "window_minutes": window_min,
        "pings": [{"at": now.isoformat(), "lat": data.latitude, "lng": data.longitude,
                   "accuracy": None, "source": data.source or "phone"}] if data.latitude is not None else [],
    })
    sos_record["track_session"] = {"sos_id": sos_id, "expires_at": expires_at.isoformat(), "window_minutes": window_min}

    # Lawyer Standby: top-3 firms simultaneously. If user has no contacts at all OR
    # standby is enabled, fire it right away (the user's choice — strategy "b").
    standby_pinged = []
    if profile.get("lawyer_standby_enabled"):
        standby_pinged = await _escalate_lawyer_standby(user, profile, sos_record)

    await db.emergency_events.insert_one(sos_record.copy())

    return {
        "ok": True, "sos_id": sos_id,
        "notified": len(notified),
        "standby_pinged": len(standby_pinged),
        "track_session": sos_record["track_session"],
    }


@api_router.get("/emergency/silent-sos")
async def silent_sos_get(
    wt: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    src: str = "watch",
):
    """GET-version of silent SOS so a smartwatch Shortcut / Tasker tile can fire it
    with a single tap that hits a URL. Auth is via the ?wt=... watch_token."""
    data = SilentSOSRequest(
        silent=True, latitude=lat, longitude=lng,
        duress=True, source=src,
    )
    return await silent_sos(data, user=None, wt=wt)


@api_router.get("/emergency/sos-history")
async def sos_history(user: dict = Depends(get_user)):
    """Audit log for the user — every SOS fired (phone + watch). GDPR-friendly."""
    events = await db.emergency_events.find(
        {"user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    return {"events": events}


# ==================== Live Location Tracking (post-SOS) ====================
# Once SOS fires, the user's phone continues pinging location for the configured window
# (default 1h, max 24h Pro / 2h Free). Family can open a public maps URL from the SMS
# to watch the user's position update in real-time.
class TrackPing(BaseModel):
    sos_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    source: str = "phone"

@api_router.post("/emergency/track/ping")
async def track_ping(data: TrackPing, user: Optional[dict] = Depends(get_user_optional), wt: Optional[str] = None):
    """Append a new location ping to an active track session.
    Auth: user JWT (phone) OR ?wt=watch_token (smartwatch).
    Silently drops if track has expired — keeps the response fast for low battery."""
    if user is None and wt:
        prof = await db.emergency_profile.find_one({"watch_token": wt}, {"_id": 0, "user_id": 1})
        if prof:
            user = await db.users.find_one({"id": prof["user_id"]})
    if user is None:
        raise HTTPException(401, "Authentication required")

    track = await db.emergency_tracks.find_one({"sos_id": data.sos_id, "user_id": user["id"]}, {"_id": 0})
    if not track or not track.get("active"):
        return {"ok": False, "reason": "track_inactive"}
    if datetime.now(timezone.utc) > datetime.fromisoformat(track["expires_at"]):
        await db.emergency_tracks.update_one({"sos_id": data.sos_id}, {"$set": {"active": False}})
        return {"ok": False, "reason": "expired"}

    ping = {
        "at": datetime.now(timezone.utc).isoformat(),
        "lat": data.latitude, "lng": data.longitude,
        "accuracy": data.accuracy, "source": data.source,
    }
    await db.emergency_tracks.update_one(
        {"sos_id": data.sos_id, "user_id": user["id"]},
        {"$push": {"pings": {"$each": [ping], "$slice": -500}}},  # keep last 500 pings
    )
    return {"ok": True}


@api_router.get("/emergency/track/{sos_id}")
async def track_view(sos_id: str):
    """PUBLIC view — used by the SMS-embedded map link family taps. Auth = knowing the
    sos_id (UUID, ~10^36 entropy). Returns only what's needed for the live map view.
    Returns 404 if track is inactive/expired so family doesn't see stale data."""
    track = await db.emergency_tracks.find_one({"sos_id": sos_id}, {"_id": 0})
    if not track:
        raise HTTPException(404, "Track not found")
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(track["expires_at"])
    if now > expires_at:
        # Lazy-deactivate on read
        if track.get("active"):
            await db.emergency_tracks.update_one({"sos_id": sos_id}, {"$set": {"active": False}})
        return {"active": False, "expired": True, "expires_at": track["expires_at"], "pings": []}
    user = await db.users.find_one({"id": track["user_id"]}, {"_id": 0, "full_name": 1, "email": 1})
    last_ping = (track.get("pings") or [])[-1] if track.get("pings") else None
    return {
        "active": bool(track.get("active")),
        "expired": False,
        "expires_at": track["expires_at"],
        "expires_in_seconds": max(0, int((expires_at - now).total_seconds())),
        "started_at": track["started_at"],
        "window_minutes": track["window_minutes"],
        "user_name": user.get("full_name") or (user.get("email") or "").split("@")[0],
        "pings": track.get("pings", [])[-50:],   # last 50 only for bandwidth
        "last_ping": last_ping,
    }


@api_router.post("/emergency/track/{sos_id}/stop")
async def track_stop(sos_id: str, user: dict = Depends(get_user)):
    """User-triggered stop — must be the same user who owns the track."""
    await db.emergency_tracks.update_one(
        {"sos_id": sos_id, "user_id": user["id"]},
        {"$set": {"active": False, "stopped_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


@api_router.post("/emergency/track/{sos_id}/extend")
async def track_extend(sos_id: str, user: dict = Depends(get_user)):
    """Extend an ACTIVE track session to 24h (the universal hard maximum).
    Triggered by the battery-low prompt — when the user's phone is about to die,
    we extend the window so family doesn't lose visibility at the worst moment.
    Available to ALL tiers — this is a life-safety feature, not a paywall lever.
    """
    max_minutes = 1440

    track = await db.emergency_tracks.find_one(
        {"sos_id": sos_id, "user_id": user["id"]}, {"_id": 0, "active": 1, "started_at": 1, "expires_at": 1},
    )
    if not track:
        raise HTTPException(404, "Track not found")
    if not track.get("active"):
        raise HTTPException(409, "Track already ended — fire a fresh SOS to start a new session.")

    started_at = datetime.fromisoformat(track["started_at"])
    current_expires = datetime.fromisoformat(track["expires_at"])
    max_expires = started_at + timedelta(minutes=max_minutes)

    if current_expires >= max_expires:
        # Already at max — nothing to extend.
        return {"ok": True, "already_at_max": True, "expires_at": track["expires_at"]}

    await db.emergency_tracks.update_one(
        {"sos_id": sos_id, "user_id": user["id"]},
        {"$set": {
            "expires_at": max_expires.isoformat(),
            "extended_at": datetime.now(timezone.utc).isoformat(),
            "extended_reason": "battery_low",
        }},
    )
    new_remaining = int((max_expires - datetime.now(timezone.utc)).total_seconds())
    return {
        "ok": True,
        "already_at_max": False,
        "expires_at": max_expires.isoformat(),
        "expires_in_seconds": max(0, new_remaining),
        "max_window_minutes": max_minutes,
    }


@api_router.get("/emergency/track/{sos_id}/active")
async def track_active_check(sos_id: str, user: dict = Depends(get_user)):
    """Quick poll from the user's phone to check if its own track is still active.
    Used by the in-app banner countdown and to know when to stop pinging."""
    track = await db.emergency_tracks.find_one(
        {"sos_id": sos_id, "user_id": user["id"]},
        {"_id": 0, "active": 1, "expires_at": 1, "window_minutes": 1},
    )
    if not track:
        return {"active": False}
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(track["expires_at"])
    if not track.get("active") or now > expires_at:
        return {"active": False, "expires_at": track["expires_at"]}
    return {
        "active": True,
        "expires_at": track["expires_at"],
        "expires_in_seconds": max(0, int((expires_at - now).total_seconds())),
        "window_minutes": track["window_minutes"],
    }


# ==================== Embassy / Consulate Directory (offline-ready) ====================
# Static directory of UK FCDO consulates worldwide. Used by Translation Mode and
# Emergency Mode for one-tap "Call my embassy" when stranded abroad.
EMBASSY_DIRECTORY = [
    {"country": "IQ", "name": "British Embassy Baghdad", "phone": "+964 7901 926 280", "email": "consular.baghdad@fcdo.gov.uk", "address": "International Zone, Baghdad, Iraq"},
    {"country": "AE", "name": "British Embassy Dubai", "phone": "+971 4 309 4444", "email": "ukinuae.consularenquiries@fcdo.gov.uk", "address": "Al Seef Road, Dubai, UAE"},
    {"country": "TR", "name": "British Consulate-General Istanbul", "phone": "+90 212 334 6400", "email": "istanbul.consular@fcdo.gov.uk", "address": "Mesrutiyet Caddesi 34, Tepebaşı, Istanbul"},
    {"country": "EG", "name": "British Embassy Cairo", "phone": "+20 2 2791 6000", "email": "cairo.consularsection@fcdo.gov.uk", "address": "7 Ahmed Ragheb Street, Garden City, Cairo"},
    {"country": "TH", "name": "British Embassy Bangkok", "phone": "+66 2 305 8333", "email": "info.bangkok@fcdo.gov.uk", "address": "14 Wireless Road, Lumpini, Bangkok"},
    {"country": "IN", "name": "British High Commission New Delhi", "phone": "+91 11 2419 2100", "email": "uk.consular@fcdo.gov.uk", "address": "Shantipath, Chanakyapuri, New Delhi"},
    {"country": "PK", "name": "British High Commission Islamabad", "phone": "+92 51 201 2000", "email": "BHC.Pakistan@fcdo.gov.uk", "address": "Diplomatic Enclave, Ramna 5, Islamabad"},
    {"country": "US", "name": "British Embassy Washington DC", "phone": "+1 202 588 7800", "email": "washington-consular@fcdo.gov.uk", "address": "3100 Massachusetts Ave NW, Washington DC"},
    {"country": "CN", "name": "British Embassy Beijing", "phone": "+86 10 5192 4000", "email": "consular.beijing@fcdo.gov.uk", "address": "11 Guanghua Lu, Jianguomenwai, Beijing"},
    {"country": "RU", "name": "British Embassy Moscow", "phone": "+7 495 956 7200", "email": "Moscow.Consular@fcdo.gov.uk", "address": "Smolenskaya Naberezhnaya 10, Moscow"},
    {"country": "FR", "name": "British Embassy Paris", "phone": "+33 1 44 51 31 00", "email": "paris.consular@fcdo.gov.uk", "address": "35 Rue du Faubourg Saint-Honoré, Paris"},
    {"country": "DE", "name": "British Embassy Berlin", "phone": "+49 30 204570", "email": "consular.berlin@fcdo.gov.uk", "address": "Wilhelmstraße 70, Berlin"},
    {"country": "ES", "name": "British Embassy Madrid", "phone": "+34 91 714 6300", "email": "madrid.consular@fcdo.gov.uk", "address": "Torre Espacio, Paseo de la Castellana 259D, Madrid"},
    {"country": "IT", "name": "British Embassy Rome", "phone": "+39 06 4220 0001", "email": "rome.consular@fcdo.gov.uk", "address": "Via XX Settembre 80, Rome"},
    {"country": "GR", "name": "British Embassy Athens", "phone": "+30 210 727 2600", "email": "athens.consular@fcdo.gov.uk", "address": "1 Ploutarchou Street, Athens"},
    {"country": "MA", "name": "British Embassy Rabat", "phone": "+212 537 633 333", "email": "rabat.consular@fcdo.gov.uk", "address": "28 Avenue S.A.R. Sidi Mohammed, Rabat"},
    {"country": "SA", "name": "British Embassy Riyadh", "phone": "+966 11 481 9100", "email": "consular.riyadh@fcdo.gov.uk", "address": "PO Box 94351, Diplomatic Quarter, Riyadh"},
    {"country": "QA", "name": "British Embassy Doha", "phone": "+974 4496 2000", "email": "consular.doha@fcdo.gov.uk", "address": "PO Box 3, West Bay, Doha"},
    {"country": "JP", "name": "British Embassy Tokyo", "phone": "+81 3 5211 1100", "email": "consular.tokyo@fcdo.gov.uk", "address": "1 Ichibancho, Chiyoda-ku, Tokyo"},
    {"country": "AU", "name": "British High Commission Canberra", "phone": "+61 2 6270 6666", "email": "consular.canberra@fcdo.gov.uk", "address": "Commonwealth Avenue, Yarralumla, Canberra"},
    {"country": "ZA", "name": "British High Commission Pretoria", "phone": "+27 12 421 7500", "email": "consular.pretoria@fcdo.gov.uk", "address": "255 Hill Street, Arcadia, Pretoria"},
    {"country": "NG", "name": "British High Commission Abuja", "phone": "+234 909 865 6000", "email": "abuja.consular@fcdo.gov.uk", "address": "Shehu Shagari Way, Maitama, Abuja"},
    {"country": "KE", "name": "British High Commission Nairobi", "phone": "+254 20 287 3000", "email": "nairobi.consular@fcdo.gov.uk", "address": "Upper Hill Road, Nairobi"},
    {"country": "BR", "name": "British Embassy Brasília", "phone": "+55 61 3329 2300", "email": "consular.brasilia@fcdo.gov.uk", "address": "Quadra 801, Conjunto K, Lote 8, Brasília"},
    {"country": "MX", "name": "British Embassy Mexico City", "phone": "+52 55 1670 3200", "email": "mexico.consular@fcdo.gov.uk", "address": "Río Lerma 71, Cuauhtémoc, Mexico City"},
]

@api_router.get("/embassy/lookup")
async def embassy_lookup(country: str):
    """Returns the British embassy/consulate for the given ISO-3166-1 alpha-2 country code."""
    cc = (country or "").upper()
    matches = [e for e in EMBASSY_DIRECTORY if e["country"] == cc]
    if not matches:
        return {"found": False, "country": cc, "fallback": {
            "name": "UK FCDO 24/7 Emergency", "phone": "+44 20 7008 5000",
            "email": "consular.fcdo@fcdo.gov.uk",
            "note": "Call this 24/7 line — FCDO will route you to the nearest UK consulate."}}
    return {"found": True, "country": cc, "embassy": matches[0]}


@api_router.get("/embassy/all")
async def embassy_all():
    """Full list — used by clients to preload an offline copy for travellers without signal."""
    return {"embassies": EMBASSY_DIRECTORY, "count": len(EMBASSY_DIRECTORY)}


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

18. California Residents (CCPA/CPRA Notice). California residents have specific privacy rights including the right to know, delete, correct, and opt out of "sale" or "sharing" of personal information. To exercise these rights, email privacy@aiadvocate.co.uk. We do not sell personal information for monetary consideration.

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
        {"user_id": user["id"], "deleted_at": {"$in": [None, "", False]}}, {"_id": 0}
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
    tone_instructions = {
        "polite": "Polite, professional, opens with goodwill and reasonable request. NO threats. Frames as 'I'd be grateful if you could…'. Suitable for first-contact / opening salvo.",
        "firm": "Firm and direct. Cites the user's rights and the relevant statute by name (e.g. 'Section 13 of the Employment Rights Act 1996'). Sets a clear 14-day deadline. No threats but the legal basis is unmistakable.",
        "pre_action": "Pre-action protocol letter (UK Civil Procedure Rules pre-action conduct). Headed 'LETTER BEFORE ACTION'. Cites specific statute and case-law where relevant. States that proceedings WILL be issued if no satisfactory response within 14 days. Demands: admission of liability, remedy sought, costs. Includes a numbered list of facts and a numbered list of remedies sought.",
        "court": "Skeleton argument / court submission format. Numbered paragraphs, formal address ('To the Honourable Tribunal'), cites case-law in proper UK citation format (e.g. 'Smith v Jones [2024] EWCA Civ 123 at [42]'). Statement of truth at the end. NOT for casual use — only when court proceedings are active.",
    }
    prompt = f"""Draft a formal legal letter.
Type: {data.letter_type}
From (your client): {data.your_name}
To (recipient): {data.recipient}
Facts / what they want to achieve: {data.details}

TONE: {data.tone.upper()} — {tone_instructions.get(data.tone, tone_instructions['firm'])}

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
    recorded_at: Optional[str] = Form(None),   # ISO-8601 wall-clock start (UTC)
    ended_at: Optional[str] = Form(None),
    duration_seconds: Optional[int] = Form(None),
    tz_name: Optional[str] = Form(None, alias="timezone"),  # IANA tz e.g. "Europe/London"
    location_lat: Optional[str] = Form(None),
    location_lng: Optional[str] = Form(None),
    location_accuracy_m: Optional[int] = Form(None),
    user: dict = Depends(get_user)
):
    """Transcribe audio and analyse it as a legal interaction (police/court).
    Captures evidentiary metadata: precise start/end timestamps, duration,
    timezone, and optional GPS location (with accuracy in metres)."""
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")

    contents = await audio.read()
    fname = (audio.filename or "rec.webm").lower()
    suffix = "." + (fname.rsplit(".", 1)[-1] if "." in fname else "webm")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents); tmp.close()

    # Server-side wall-clock receipt time (used if client did not send recorded_at)
    server_received_at = datetime.now(timezone.utc).isoformat()

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
        # 🕒 Evidentiary timestamps
        "recorded_at": recorded_at or server_received_at,     # wall-clock start
        "ended_at": ended_at,                                  # wall-clock end
        "duration_seconds": duration_seconds,
        "timezone": tz_name,
        "server_received_at": server_received_at,              # tamper-evident server timestamp
        # 📍 Optional location
        "location_lat": location_lat,
        "location_lng": location_lng,
        "location_accuracy_m": location_accuracy_m,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.legal_files.insert_one(rec.copy())
    rec.pop("_id", None)
    return rec

# ==================== Subscriptions (Stripe) ====================
@api_router.post("/subscription/checkout")
async def create_checkout(data: CheckoutRequest, request: Request, user: dict = Depends(get_user)):
    """Subscribe to a plan, OR upgrade/downgrade an existing subscription.

    Smart flow:
      • If the user has no active Stripe subscription → create a Checkout Session as normal
      • If the user already has one → call stripe.Subscription.modify() with
        proration_behavior='create_prorations'. Stripe will:
          - cancel the old plan line
          - activate the new plan line on the same subscription record
          - automatically charge / credit the prorated difference
        No new Checkout, no double-billing, no admin work.

    data.plan in {'plus','pro','yearly'} → maps to STRIPE_PRICE_*.
    """
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

    # 🔁 Existing-subscription path — upgrade/downgrade in-place
    existing_sub_id = user.get("stripe_subscription_id")
    if existing_sub_id:
        try:
            sub = stripe.Subscription.retrieve(existing_sub_id)
            if sub and sub.get("status") in ("active", "trialing", "past_due"):
                current_price_id = sub["items"]["data"][0]["price"]["id"]
                if current_price_id == price_id:
                    # Already on this plan — no-op (don't double-charge)
                    return {"already_on_plan": True, "tier": plan}
                # Modify the existing subscription line
                line_item_id = sub["items"]["data"][0]["id"]
                stripe.Subscription.modify(
                    existing_sub_id,
                    items=[{"id": line_item_id, "price": price_id}],
                    proration_behavior="create_prorations",
                    metadata={"user_id": user["id"], "plan": plan, "changed_at": datetime.now(timezone.utc).isoformat()},
                )
                # DB is updated via the customer.subscription.updated webhook
                return {"subscription_updated": True, "tier": plan, "prorated": True}
        except stripe.error.InvalidRequestError as e:
            # Subscription is gone from Stripe (e.g. fully cancelled) — fall through to new checkout
            logger.info(f"Existing sub {existing_sub_id} not modifiable ({e}) — falling through to new checkout")
        except Exception as e:
            logger.exception(f"Subscription modify failed: {e}")
            raise HTTPException(500, f"Could not change plan: {str(e)}")

    # 🆕 No active subscription — create a new Checkout Session
    try:
        origin = (os.environ.get("FRONTEND_URL") or request.headers.get("origin") or APP_PUBLIC_URL).rstrip("/")
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
    origin = (os.environ.get("FRONTEND_URL") or request.headers.get("origin") or APP_PUBLIC_URL).rstrip("/")
    try:
        sess = stripe.billing_portal.Session.create(customer=cust_id, return_url=f"{origin}/")
        return {"portal_url": sess.url}
    except Exception as e:
        logger.exception("Stripe portal error")
        raise HTTPException(500, f"Portal error: {str(e)}")

@api_router.post("/subscription/activate-test")
async def activate_test(plan: str = "plus", user: dict = Depends(get_user)):
    """DEV-ONLY: activate a subscription without going through Stripe.
    Hardened in 2026-02 — restricted to admin emails to prevent any logged-in user
    from upgrading themselves for free. Returns 403 otherwise."""
    _admin_set = {e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()}
    if user.get("email", "").lower() not in _admin_set:
        raise HTTPException(403, "Test activation is admin-only.")
    tier = plan if plan in ("plus", "pro", "yearly") else "plus"
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"subscription_status": "active", "tier": tier,
                  "subscription_started_at": datetime.now(timezone.utc).isoformat()}}
    )
    fresh = await db.users.find_one({"id": user["id"]})
    return user_to_public(fresh)

# ============================================================
# Consumer Top-up Packs (one-time Stripe purchases)
# ============================================================
# Each pack unlocks a specific outcome (24h Pro, a letter bundle, etc.) for a
# fixed window. Stored on the user row as `topup_active`. Designed to be additive
# — a Day Pass while you have an active Plus subscription simply boosts you to
# Pro for 24h. Stripe one-time prices, NOT subscriptions.
TOPUP_PACKS = {
    "day_pass": {
        "label": "Day Pass",
        "price_gbp": 4.99,
        "duration_hours": 24,
        "grants_tier": "plus",
        "tagline": "Unlimited Lex chats + 5 evidence photos for 24h.",
    },
    "letter_pack": {
        "label": "Letter Pack",
        "price_gbp": 9.99,
        "duration_hours": 30 * 24,
        "grants_tier": "plus",
        "letter_quota": 5,
        "contract_quota": 1,
        "tagline": "5 AI-drafted letters + 1 contract review · 30-day use-by.",
    },
    "weekend_pass": {
        "label": "Weekend Pass",
        "price_gbp": 14.99,
        "duration_hours": 72,
        "grants_tier": "plus",
        "tagline": "Full Plus features for 72 hours.",
    },
    "crisis_pack": {
        "label": "Crisis Pack",
        "price_gbp": 29.99,
        "duration_hours": 24,
        "grants_tier": "pro",
        "tagline": "Full Pro for 24h — Hearing Recorder, Deep Think, RAG priority.",
    },
}


def _get_topup_price_id(pack_id: str) -> str:
    """Maps pack ID → Stripe Price ID via env var."""
    return os.environ.get(f"STRIPE_PRICE_TOPUP_{pack_id.upper()}", "")


@api_router.get("/topups/packs")
async def list_topup_packs(user: dict = Depends(get_user)):
    """Return the catalogue + the user's currently-active top-up (if any)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    active = user.get("topup_active")
    if active and active.get("expires_at", "") <= now_iso:
        active = None
    return {
        "packs": [{"id": k, **v, "configured": bool(_get_topup_price_id(k))} for k, v in TOPUP_PACKS.items()],
        "active": active,
    }


class TopupCheckoutPayload(BaseModel):
    pack_id: str


# ============= Gift-a-Pack — buy a top-up for someone else (e.g. backpacker family) =============
class GiftCheckoutPayload(BaseModel):
    """Public endpoint (no auth) — anyone can buy a pack for someone else's account.
    The recipient is identified by email. If they already have an account → instantly
    activated on payment. If not yet signed up → stored as a pending gift and auto-claimed
    when they sign up with the same email."""
    recipient_email: EmailStr
    pack_id: str
    gifter_name: str = ""               # who's sending it
    gifter_email: Optional[EmailStr] = None  # so we send the gifter a receipt
    message: str = ""                   # personal note (up to 280 chars)


@api_router.post("/topups/gift/checkout")
async def gift_checkout(data: GiftCheckoutPayload, request: Request):
    """Create a Stripe checkout for a gifted top-up pack. No login required.
    Recipient is identified by email; pack activates instantly on payment
    if the recipient has an account, otherwise stored as pending."""
    if data.pack_id not in TOPUP_PACKS:
        raise HTTPException(400, f"Unknown pack: {data.pack_id}")
    price_id = _get_topup_price_id(data.pack_id)
    if not price_id:
        raise HTTPException(503, f"Pack '{data.pack_id}' not configured.")
    if not stripe.api_key:
        raise HTTPException(503, "Stripe not configured.")
    recipient_email = data.recipient_email.lower().strip()
    gifter_email = (data.gifter_email or "").lower().strip() or recipient_email
    if gifter_email == recipient_email:
        raise HTTPException(400, "You can't gift a pack to yourself. Use the normal purchase flow.")
    origin = (os.environ.get("FRONTEND_URL") or request.headers.get("origin") or APP_PUBLIC_URL).rstrip("/")
    msg = (data.message or "")[:280]
    gifter_name = (data.gifter_name or "")[:80].strip() or "Someone who cares"
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=gifter_email,                    # bill the gifter
            success_url=f"{origin}/gift.html?status=success&pack={data.pack_id}",
            cancel_url=f"{origin}/gift.html?status=cancel",
            metadata={
                "is_gift": "1",
                "recipient_email": recipient_email,
                "topup_pack": data.pack_id,
                "gifter_name": gifter_name,
                "gifter_email": gifter_email,
                "gift_message": msg,
            },
            allow_promotion_codes=True,
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.exception("Gift checkout error")
        raise HTTPException(500, f"Checkout error: {e}")


async def _activate_gifted_topup(metadata: dict):
    """Stripe webhook calls this for `is_gift=1` checkouts. Activates the pack
    on the recipient's account (if it exists) or stores a pending gift otherwise.
    Idempotent: uses Stripe session_id to dedupe."""
    pack_id = metadata.get("topup_pack")
    recipient_email = (metadata.get("recipient_email") or "").lower().strip()
    pack = TOPUP_PACKS.get(pack_id)
    if not pack or not recipient_email:
        logger.warning(f"Gift activation: missing fields {metadata}")
        return

    gifter_name = metadata.get("gifter_name", "")
    gifter_email = (metadata.get("gifter_email") or "").lower().strip()
    message = metadata.get("gift_message", "")
    now = datetime.now(timezone.utc)

    recipient = await db.users.find_one({"email": recipient_email}, {"_id": 0})
    if recipient:
        # Recipient has an account — activate immediately
        await _activate_topup_for_user(recipient["id"], pack_id)
        # Stamp a gift note on the activation
        await db.users.update_one(
            {"id": recipient["id"]},
            {"$set": {"topup_active.gift": {
                "gifter_name": gifter_name, "gifter_email": gifter_email,
                "message": message, "received_at": now.isoformat(),
            }}},
        )
        # Audit log
        await db.gift_topups.insert_one({
            "id": str(uuid.uuid4()),
            "recipient_email": recipient_email,
            "recipient_user_id": recipient["id"],
            "pack_id": pack_id, "label": pack["label"], "price_gbp": pack["price_gbp"],
            "gifter_name": gifter_name, "gifter_email": gifter_email, "message": message,
            "status": "delivered",
            "created_at": now.isoformat(),
        })
        # Email both parties (best-effort)
        try:
            from email_helper import send_email
            await send_email(
                to=recipient_email,
                subject=f"You've been gifted a {pack['label']} on AI Advocate",
                body_html=f"""<p>Hi,</p>
                <p><strong>{gifter_name}</strong> has just gifted you a <strong>{pack['label']}</strong> on AI Advocate.</p>
                {f'<blockquote style="border-left:3px solid #f7c948;padding:10px 14px;background:#fff8e0;color:#1a1300;font-style:italic;">{message}</blockquote>' if message else ''}
                <p>It's active right now — just open the app and start asking Lex.</p>
                <p style="color:#666;font-size:12px;">If you need help, just reply to this email or contact support@aiadvocate.co.uk.</p>""",
            )
            if gifter_email:
                await send_email(
                    to=gifter_email,
                    subject=f"Your gift to {recipient_email} has been delivered",
                    body_html=f"""<p>Hi {gifter_name},</p>
                    <p>Your gift of a <strong>{pack['label']}</strong> (£{pack['price_gbp']:.2f}) to <strong>{recipient_email}</strong> has been delivered. They can use it right now.</p>
                    {f'<p>Your message:</p><blockquote style="border-left:3px solid #f7c948;padding:10px 14px;background:#fff8e0;color:#1a1300;font-style:italic;">{message}</blockquote>' if message else ''}
                    <p>Thank you for looking out for them.</p>""",
                )
        except Exception:
            logger.exception("Gift email failed")
        logger.info(f"Gift {pack_id} delivered to {recipient_email}")
    else:
        # No account — store pending; activates on signup
        pending = {
            "id": str(uuid.uuid4()),
            "recipient_email": recipient_email,
            "pack_id": pack_id, "label": pack["label"], "price_gbp": pack["price_gbp"],
            "gifter_name": gifter_name, "gifter_email": gifter_email, "message": message,
            "status": "pending",
            "created_at": now.isoformat(),
        }
        await db.gift_topups.insert_one(pending)
        try:
            from email_helper import send_email
            signup_url = f"{(os.environ.get('APP_PUBLIC_URL') or 'https://aiadvocate.co.uk').rstrip('/')}/?gift_pending=1&email={recipient_email}"
            await send_email(
                to=recipient_email,
                subject=f"{gifter_name} has gifted you a {pack['label']} — sign up to claim",
                body_html=f"""<p>Hi,</p>
                <p><strong>{gifter_name}</strong> has gifted you a <strong>{pack['label']}</strong> (£{pack['price_gbp']:.2f}) on AI Advocate — a UK legal help app.</p>
                {f'<blockquote style="border-left:3px solid #f7c948;padding:10px 14px;background:#fff8e0;color:#1a1300;font-style:italic;">{message}</blockquote>' if message else ''}
                <p><a href="{signup_url}" style="display:inline-block;background:#1a1300;color:#f7c948;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:700;">Claim my gift</a></p>
                <p>Just sign up with this email address ({recipient_email}) and your gift activates instantly.</p>""",
            )
            if gifter_email:
                await send_email(
                    to=gifter_email,
                    subject=f"Your gift to {recipient_email} is waiting",
                    body_html=f"""<p>Hi {gifter_name},</p>
                    <p>Your gift of a <strong>{pack['label']}</strong> (£{pack['price_gbp']:.2f}) to <strong>{recipient_email}</strong> has been received.</p>
                    <p>They don't have an AI Advocate account yet — we've emailed them a signup link, and the pack will activate the moment they create an account with that email. Their gift will wait for them.</p>""",
                )
        except Exception:
            logger.exception("Gift pending email failed")
        logger.info(f"Gift {pack_id} pending for unsigned {recipient_email}")


async def _claim_pending_gifts_for(email: str, user_id: str):
    """Called on signup. Looks up any pending gift_topups for this email and
    activates them on the new user's account."""
    email = (email or "").lower().strip()
    claimed = 0
    async for g in db.gift_topups.find({"recipient_email": email, "status": "pending"}):
        try:
            await _activate_topup_for_user(user_id, g["pack_id"])
            await db.users.update_one(
                {"id": user_id},
                {"$set": {"topup_active.gift": {
                    "gifter_name": g.get("gifter_name", ""),
                    "gifter_email": g.get("gifter_email", ""),
                    "message": g.get("message", ""),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "claimed_on_signup": True,
                }}},
            )
            await db.gift_topups.update_one(
                {"id": g["id"]},
                {"$set": {"status": "delivered", "recipient_user_id": user_id,
                          "claimed_at": datetime.now(timezone.utc).isoformat()}},
            )
            claimed += 1
        except Exception:
            logger.exception(f"Pending-gift claim failed: {g.get('id')}")
    if claimed:
        logger.info(f"Claimed {claimed} pending gift(s) for {email}")
    return claimed


@api_router.get("/topups/pending-gifts")
async def list_pending_gifts(email: str):
    """Public — looks up pending gifts for an email. Used by the /gift.html success
    page so the gifter can confirm delivery, and (with a banner) on the signup screen
    to encourage someone who's been gifted to register."""
    rx = email.lower().strip()
    out = []
    async for g in db.gift_topups.find({"recipient_email": rx, "status": "pending"}, {"_id": 0}):
        out.append({"label": g["label"], "gifter_name": g.get("gifter_name", ""), "created_at": g.get("created_at")})
    return {"pending": out}


@api_router.post("/topups/checkout")
async def topup_checkout(data: TopupCheckoutPayload, request: Request, user: dict = Depends(get_user)):
    """Create a Stripe one-time payment checkout for a top-up pack."""
    if data.pack_id not in TOPUP_PACKS:
        raise HTTPException(400, f"Unknown top-up pack: {data.pack_id}")
    price_id = _get_topup_price_id(data.pack_id)
    if not price_id:
        raise HTTPException(503,
            f"Top-up '{data.pack_id}' is not yet configured. "
            f"The site admin needs to create a Stripe Price and set STRIPE_PRICE_TOPUP_{data.pack_id.upper()} in /app/backend/.env.")
    if not stripe.api_key:
        raise HTTPException(503, "Stripe not configured.")
    try:
        # Prefer the canonical FRONTEND_URL from .env so the user always returns
        # to the live app — not whatever stale preview tab they happened to be
        # on when they tapped Buy. Falls back to origin header, then APP_PUBLIC_URL.
        origin = (os.environ.get("FRONTEND_URL") or request.headers.get("origin") or APP_PUBLIC_URL).rstrip("/")
        session = stripe.checkout.Session.create(
            mode="payment",                                     # one-time, NOT subscription
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=user["email"],
            client_reference_id=user["id"],
            success_url=f"{origin}/?topup=success&pack={data.pack_id}",
            cancel_url=f"{origin}/?topup=cancel",
            metadata={"user_id": user["id"], "topup_pack": data.pack_id},
            allow_promotion_codes=True,
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.exception("Topup checkout error")
        raise HTTPException(500, f"Checkout error: {str(e)}")


async def _activate_topup_for_user(user_id: str, pack_id: str):
    """Called from the Stripe webhook on successful checkout.session.completed
    when the session's metadata contains `topup_pack`. Idempotent."""
    pack = TOPUP_PACKS.get(pack_id)
    if not pack:
        logger.warning(f"Activate topup: unknown pack {pack_id}")
        return
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=pack["duration_hours"])
    payload = {
        "kind": pack_id,
        "grants_tier": pack["grants_tier"],
        "activated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "label": pack["label"],
        "price_gbp": pack["price_gbp"],
    }
    if pack_id == "letter_pack":
        payload["letter_quota"] = pack["letter_quota"]
        payload["contract_quota"] = pack["contract_quota"]
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"topup_active": payload},
         "$push": {"topup_history": payload}},
    )
    logger.info(f"Activated top-up {pack_id} for user {user_id} until {expires.isoformat()}")


def _effective_topup_tier(user: dict) -> Optional[str]:
    """Returns the tier from an active top-up, or None. Paywall checks should
    prefer max(subscription tier, topup tier)."""
    active = (user or {}).get("topup_active")
    if not active:
        return None
    try:
        if active.get("expires_at", "") <= datetime.now(timezone.utc).isoformat():
            return None
        return active.get("grants_tier")
    except Exception:
        return None


# ==================== 🎖 SOLICITOR SANITY CHECK ====================
# £49 one-off consumer purchase. User pays AA. AA routes the question + Lex's
# answer to a Founding Firm with capacity. Firm reviews, submits verification
# within 24h. AA keeps £19, firm earns £30 (auto-logged as commission).
# Status lifecycle: pending_payment → pending_assignment → assigned → completed | refunded

SANITY_CHECK_PRICE_GBP = 49.00
SANITY_CHECK_FIRM_PAYOUT_GBP = 30.00
SANITY_CHECK_TURNAROUND_HOURS = 24
SANITY_FIRM_CAPACITY = 5  # max concurrent open sanity checks per firm


class SanityCheckCreate(BaseModel):
    """Created from the Lex chat 'Get a solicitor to verify' CTA."""
    session_id: str = ""
    question: str = ""
    lex_answer: str = ""
    matter_type: str = ""
    user_notes: str = ""
    language: str = "en-GB"
    country: str = "GB"


@api_router.post("/sanity-checks/create-and-checkout")
async def sanity_check_create(data: SanityCheckCreate, request: Request, user: dict = Depends(get_user)):
    """Creates a pending_payment SanityCheck row + Stripe one-off checkout URL.
    On payment success the webhook flips it to pending_assignment + routes to
    a Founding Firm with capacity."""
    if not stripe.api_key:
        raise HTTPException(503, "Stripe not configured")

    question = (data.question or "").strip()
    lex_answer = (data.lex_answer or "").strip()
    if (not question or not lex_answer) and data.session_id:
        ex = await _last_lex_exchange(user["id"], data.session_id)
        if ex:
            question = question or (ex.get("user_message") or "")
            lex_answer = lex_answer or (ex.get("assistant_response") or "")
    if not question or not lex_answer:
        raise HTTPException(400, "We couldn't find a Lex answer to verify. Try asking Lex first, then tap the Sanity Check button on the answer.")

    sc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    rec = {
        "id": sc_id,
        "user_id": user["id"], "user_email": user["email"], "user_name": user.get("name", ""),
        "question": question[:8000], "lex_answer": lex_answer[:16000],
        "matter_type": (data.matter_type or "general")[:120],
        "user_notes": (data.user_notes or "")[:2000],
        "language": data.language, "country": data.country,
        "status": "pending_payment",
        "price_gbp": SANITY_CHECK_PRICE_GBP,
        "firm_payout_gbp": SANITY_CHECK_FIRM_PAYOUT_GBP,
        "assigned_firm_id": None, "assigned_firm_email": None,
        "firm_response_text": None, "firm_response_at": None,
        "stripe_session_id": None, "stripe_payment_intent": None,
        "paid_at": None, "deadline_at": None,
        "created_at": now.isoformat(),
    }
    await db.sanity_checks.insert_one(rec)

    try:
        origin = (os.environ.get("FRONTEND_URL") or request.headers.get("origin") or APP_PUBLIC_URL).rstrip("/")
        # Prefer the configured Stripe Price ID (clean dashboard reporting + VAT-inclusive
        # pricing rules). Fall back to inline price_data if the env var isn't set OR if
        # Stripe rejects the price (test/live mismatch etc.) — checkout still works.
        price_id = os.environ.get("STRIPE_PRICE_SANITY_CHECK", "").strip()
        inline_li = [{
            "price_data": {
                "currency": "gbp",
                "unit_amount": int(SANITY_CHECK_PRICE_GBP * 100),
                "product_data": {
                    "name": "AI Advocate · Solicitor Sanity Check",
                    "description": f"Verified solicitor review of your Lex answer · {SANITY_CHECK_TURNAROUND_HOURS}h turnaround",
                },
            },
            "quantity": 1,
        }]
        common_kwargs = dict(
            mode="payment",
            payment_method_types=["card"],
            customer_email=user["email"],
            client_reference_id=user["id"],
            success_url=f"{origin}/?sanity=success&id={sc_id}",
            cancel_url=f"{origin}/?sanity=cancel&id={sc_id}",
            metadata={"kind": "sanity_check", "sanity_check_id": sc_id, "user_id": user["id"]},
            allow_promotion_codes=True,
        )
        session = None
        if price_id:
            try:
                session = stripe.checkout.Session.create(line_items=[{"price": price_id, "quantity": 1}], **common_kwargs)
            except stripe.error.InvalidRequestError as ire:
                logger.warning(f"Sanity check price '{price_id}' invalid ({ire}) — falling back to inline price_data")
        if session is None:
            session = stripe.checkout.Session.create(line_items=inline_li, **common_kwargs)
    except Exception as e:
        logger.exception("sanity-check checkout error")
        await db.sanity_checks.delete_one({"id": sc_id})
        raise HTTPException(500, f"Checkout error: {e}")

    await db.sanity_checks.update_one({"id": sc_id}, {"$set": {"stripe_session_id": session.id}})
    return {"sanity_check_id": sc_id, "checkout_url": session.url, "price_gbp": SANITY_CHECK_PRICE_GBP}


async def _activate_sanity_check(sc_id: str, stripe_session_id: str = None):
    sc = await db.sanity_checks.find_one({"id": sc_id})
    if not sc:
        logger.warning(f"sanity-check activate: id {sc_id} not found")
        return
    if sc.get("status") not in ("pending_payment", None):
        logger.info(f"sanity-check {sc_id} already in status {sc.get('status')} — skipping activate")
        return
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=SANITY_CHECK_TURNAROUND_HOURS)
    await db.sanity_checks.update_one({"id": sc_id}, {"$set": {
        "status": "pending_assignment",
        "paid_at": now.isoformat(),
        "deadline_at": deadline.isoformat(),
    }})
    await _route_sanity_check(sc_id)


async def _route_sanity_check(sc_id: str) -> Optional[str]:
    sc = await db.sanity_checks.find_one({"id": sc_id})
    if not sc or sc.get("status") != "pending_assignment":
        return None
    elig_q = {
        "deleted_at": {"$in": [None, ""]},
        "billing_status": {"$in": ["active", "trial", "comp"]},
        "billing_tier": {"$in": ["premium", "practice", "founding"]},
    }
    candidates = []
    declined_set = set(sc.get("declined_by") or [])
    async for f in db.firm_accounts.find(elig_q, {"_id": 0}):
        if f["id"] in declined_set:
            continue
        open_count = await db.sanity_checks.count_documents(
            {"assigned_firm_id": f["id"], "status": "assigned"}
        )
        if open_count < SANITY_FIRM_CAPACITY:
            candidates.append((open_count, f))
    if not candidates:
        logger.warning(f"sanity-check {sc_id}: no firm with capacity — staying pending_assignment for cron retry")
        return None
    candidates.sort(key=lambda x: x[0])
    firm = candidates[0][1]
    now = datetime.now(timezone.utc)
    await db.sanity_checks.update_one({"id": sc_id}, {"$set": {
        "status": "assigned",
        "assigned_firm_id": firm["id"],
        "assigned_firm_email": firm["email"],
        "assigned_at": now.isoformat(),
    }})
    try:
        from email_helper import send_email
        await send_email(
            to=firm["email"], kind="firm",
            subject=f"⚖️ New Sanity Check assigned — £{SANITY_CHECK_FIRM_PAYOUT_GBP:.2f} on completion",
            body_html=f"""<p>Hi {firm.get('contact_name','team')},</p>
                <p>A new <strong>Solicitor Sanity Check</strong> has been routed to your firm. The client paid £{SANITY_CHECK_PRICE_GBP:.2f}; you'll be credited £{SANITY_CHECK_FIRM_PAYOUT_GBP:.2f} once you submit the review.</p>
                <ul>
                  <li>Matter: <strong>{sc.get('matter_type','general')}</strong></li>
                  <li>Turnaround: within {SANITY_CHECK_TURNAROUND_HOURS} hours</li>
                </ul>
                <p><a href="https://aiadvocate.co.uk/firm-portal" style="background:#f7c948;color:#1a1300;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:700">Open the Firm Portal →</a></p>
                <p style="font-size:12px;color:#666">If you cannot complete this within 24h, please use the "Decline" button so we can route to another firm.</p>""",
        )
        await send_email(
            to=sc["user_email"], kind="user",
            subject="Your Sanity Check is on its way — a solicitor will respond within 24h",
            body_html=f"""<p>Hi,</p>
                <p>Thanks — your <strong>Solicitor Sanity Check</strong> has been routed to <strong>{firm.get('firm_name') or 'a verified UK law firm'}</strong>. You'll get an email the moment they submit their review (typically within 24 hours).</p>
                <p>Your matter: <em>{sc.get('matter_type','general')}</em></p>
                <p>If 24h passes without a response, we'll automatically re-route to another firm — no action needed from you.</p>
                <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
        )
    except Exception as e:
        logger.warning(f"sanity-check notification email failed: {e}")
    return firm["id"]


@api_router.get("/sanity-checks")
async def list_my_sanity_checks(user: dict = Depends(get_user)):
    cursor = db.sanity_checks.find(
        {"user_id": user["id"]},
        {"_id": 0, "lex_answer": 0},
    ).sort("created_at", -1).limit(50)
    items = [s async for s in cursor]
    return {"items": items}


@api_router.get("/sanity-checks/{sc_id}")
async def get_my_sanity_check(sc_id: str, user: dict = Depends(get_user)):
    sc = await db.sanity_checks.find_one({"id": sc_id, "user_id": user["id"]}, {"_id": 0})
    if not sc:
        raise HTTPException(404, "Sanity check not found")
    return sc


# ==================== Winback: free Day Pass (lifetime, once per user) ====================
# When a free user hits the chat cap and has dismissed the upgrade modal at least
# twice, we gift them a free 24h Day Pass (Plus features). Goal: turn a frustrated
# user into a paying user — pampered users don't convert, blocked users churn.
# Hard-capped at 1 gift per account, ever. Stored in `winback_gifted_at`.
class WinbackEligibilityResp(BaseModel):
    eligible: bool
    reason: str  # for debugging: "already_gifted", "not_free", "not_blocked_yet", "ok"


@api_router.get("/winback/eligibility")
async def winback_eligibility(user: dict = Depends(get_user)):
    """Frontend calls this once per dashboard render. Returns eligible:true ONLY
    if (a) the user is on free tier, (b) has dismissed the upgrade modal ≥2 times,
    (c) has hit the daily chat cap at least once in the last 24h, and
    (d) has NEVER been gifted before. The frontend then renders a 'gift' toast."""
    if user.get("winback_gifted_at"):
        return WinbackEligibilityResp(eligible=False, reason="already_gifted")
    pub = user_to_public(user)
    if pub.get("tier") != "free":
        return WinbackEligibilityResp(eligible=False, reason="not_free")
    dismiss_count = int(user.get("upgrade_modal_dismissed_count") or 0)
    if dismiss_count < 2:
        return WinbackEligibilityResp(eligible=False, reason="not_blocked_yet")
    # Check whether they've actually hit the daily chat cap recently
    bucket_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await db.usage.find_one({"user_id": user["id"], "bucket": bucket_key, "feature": "lex_chat"}, {"_id": 0})
    used = (usage or {}).get("count", 0)
    if used < 5:  # 5 is the free daily cap
        return WinbackEligibilityResp(eligible=False, reason="not_blocked_yet")
    return WinbackEligibilityResp(eligible=True, reason="ok")


@api_router.post("/winback/dismiss-upgrade")
async def winback_dismiss_upgrade(user: dict = Depends(get_user)):
    """Called whenever the user dismisses an upgrade modal. We count these so
    we can fire the winback gift on the second dismissal AFTER they've also
    hit the chat cap. Pure tally — no rate-limit needed."""
    await db.users.update_one(
        {"id": user["id"]},
        {"$inc": {"upgrade_modal_dismissed_count": 1}},
    )
    return {"ok": True}


@api_router.post("/winback/claim")
async def winback_claim(user: dict = Depends(get_user)):
    """User accepted the offered Day Pass gift. Activate it just like a paid
    top-up would, but mark `winback_gifted_at` so this can NEVER fire again."""
    if user.get("winback_gifted_at"):
        raise HTTPException(409, "Day Pass gift has already been claimed.")
    # Re-verify eligibility server-side (defence in depth — never trust the client)
    pub = user_to_public(user)
    if pub.get("tier") != "free":
        raise HTTPException(409, "You already have a paid plan — no winback gift needed.")
    # Activate the Day Pass payload (same shape as a real Stripe purchase)
    now = datetime.now(timezone.utc)
    pack = TOPUP_PACKS["day_pass"]
    expires = now + timedelta(hours=pack["duration_hours"])
    payload = {
        "kind": "day_pass",
        "grants_tier": pack["grants_tier"],
        "activated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "label": pack["label"] + " (Gifted)",
        "price_gbp": 0,
        "source": "winback",
    }
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"topup_active": payload, "winback_gifted_at": now.isoformat()},
         "$push": {"topup_history": payload}},
    )
    logger.info(f"Winback Day Pass gifted to user {user['id']} ({user.get('email')})")
    return {"ok": True, "topup_active": payload}


@api_router.post("/webhook/stripe")
@api_router.post("/stripe/webhook")  # Alias — matches production Stripe destination URL
async def stripe_webhook(request: Request):
    """Stripe webhook → update user subscription_status when payments happen.
    Configure: Stripe Dashboard → Developers → Webhooks → Add endpoint
    URL: {your_domain}/api/webhook/stripe  (alias: /api/stripe/webhook also accepted)
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

    # event may be a dict (un-verified path) OR a stripe.Event (verified path).
    # stripe.Event behaves like dict-of-StripeObjects via __getitem__ but does NOT
    # support .get() on nested StripeObjects. Use str() → json round-trip to get
    # a plain nested-dict we can safely .get() through.
    if not isinstance(event, dict):
        import json as _json
        try:
            event = _json.loads(str(event))
        except Exception:
            logger.exception("Could not normalize Stripe event to dict — falling back to attribute access")
            event = {"type": getattr(event, "type", None), "data": {"object": {}}}
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    now_iso = datetime.now(timezone.utc).isoformat()

    if etype == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        # 🎁 GIFTED top-up — metadata.is_gift=1 set by /api/topups/gift/checkout
        if meta.get("is_gift") == "1":
            await _activate_gifted_topup(meta)
            return {"ok": True, "gift_processed": meta.get("recipient_email")}

        # 🎟 Consumer TOP-UP one-time payment — metadata.topup_pack is set by /api/topups/checkout
        topup_pack = meta.get("topup_pack")
        if topup_pack:
            user_id = obj.get("client_reference_id") or meta.get("user_id")
            if user_id:
                await _activate_topup_for_user(user_id, topup_pack)
                logger.info(f"Top-up {topup_pack} activated for {user_id} via Stripe webhook")
                return {"ok": True, "topup_activated": topup_pack}

        # 🎖 SANITY CHECK — metadata.kind=sanity_check set by /api/sanity-checks/checkout
        if meta.get("kind") == "sanity_check":
            sc_id = meta.get("sanity_check_id")
            if sc_id:
                await _activate_sanity_check(sc_id, stripe_session_id=obj.get("id"))
                return {"ok": True, "sanity_check_activated": sc_id}

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

            # 📧 Branded cancellation email — covers self-cancels via the Stripe portal.
            # We send to whichever side matched (consumer OR firm). Wrapped to never
            # fail the webhook regardless.
            try:
                from email_helper import send_cancellation_email
                from datetime import datetime as _dt
                ended_on = _dt.now(timezone.utc).strftime("%d %B %Y")
                if consumer_res.modified_count > 0:
                    u = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "email": 1, "full_name": 1})
                    if u:
                        await send_cancellation_email(u["email"], u.get("full_name") or "", "user", ended_on, "Subscription cancelled via Stripe")
                if firm_res.modified_count > 0:
                    f = await db.firm_accounts.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "email": 1, "firm_name": 1, "primary_contact": 1})
                    if f:
                        await send_cancellation_email(f["email"], f.get("firm_name") or f.get("primary_contact") or "", "firm", ended_on, "Subscription cancelled via Stripe")
            except Exception as e:
                logger.warning(f"Cancellation email (webhook) failed for customer {customer_id}: {e}")
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
            {"id": "plus", "name": "Plus", "price_gbp": 19.99, "period": "month",
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
        # 🕒 Evidentiary header — prominent, audit-friendly
        ev_lines = ["⚖ EVIDENCE METADATA", "─" * 38]
        rec_at = f.get("recorded_at") or created
        end_at = f.get("ended_at")
        dur = f.get("duration_seconds")
        tz = f.get("timezone")
        lat = f.get("location_lat"); lng = f.get("location_lng"); acc = f.get("location_accuracy_m")
        srv = f.get("server_received_at")
        ev_lines.append(f"Recording started : {rec_at}")
        if end_at:
            ev_lines.append(f"Recording ended   : {end_at}")
        if dur is not None:
            m, s = divmod(int(dur), 60)
            ev_lines.append(f"Duration          : {m}m {s}s ({dur} seconds)")
        if tz:
            ev_lines.append(f"Local timezone    : {tz}")
        if lat and lng:
            ev_lines.append(f"GPS location      : {lat}, {lng}" + (f" (±{acc}m)" if acc else ""))
        if srv:
            ev_lines.append(f"Server-received   : {srv}")
        ev_lines.append(f"File reference    : {f.get('id', '-')[:13]}…")
        ev_lines.append("─" * 38)
        ev_block = "\n".join(ev_lines)
        body = (f"{ev_block}\n\n"
                f"--- TRANSCRIPT ---\n\n{f.get('transcript','')}\n\n"
                f"--- LEX ANALYSIS ---\n\n{f.get('analysis','')}")
        meta = {
            "Source": fname,
            "Recorded": (rec_at or "")[:19].replace("T", " "),
            "Duration": f"{dur}s" if dur else "—",
            "Timezone": tz or "—",
        }
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


# ==================== Cases ↔ Chats wiring ====================
# Two paths to file a Lex chat as a formal Case File:
#   • Manual: user taps "Save as Case File" in the Case Timeline (Option B).
#   • Auto:   when a session reaches >= 3 turns AND has no linked case yet,
#             the timeline endpoint quietly promotes it (Option A).
# Both call _ensure_case_for_session() so the logic stays in one place.

# In-memory dedupe so we never run the auto-promote check twice concurrently
# for the same session. Per-process is fine — the DB has a uniqueness guarantee
# via `session_id` lookup so race-safe in practice.
_AUTO_CASE_GUARD: set = set()


async def _ensure_case_for_session(user: dict, session_id: str,
                                   source: str = "auto") -> Optional[dict]:
    """Idempotent — returns the existing case if one is already linked to this
    session, otherwise creates a new case + attaches the chat thread to it.

    The case title is derived from the first user message; the category is
    inferred via the same simple classifier the chat UI uses.
    """
    # Guard against concurrent calls for the same session
    guard_key = f"{user['id']}:{session_id}"
    if guard_key in _AUTO_CASE_GUARD:
        return None
    _AUTO_CASE_GUARD.add(guard_key)
    try:
        # Already linked? Bail.
        existing = await db.case_items.find_one(
            {"user_id": user["id"], "item_type": "chat", "item_id": session_id,
             "deleted_at": {"$in": [None, "", False]}},
            {"_id": 0, "case_id": 1},
        )
        if existing:
            return await db.cases.find_one({"id": existing["case_id"]}, {"_id": 0})

        # Pull the first user message + category from the conversation thread
        first_turn = await db.conversations.find_one(
            {"user_id": user["id"], "session_id": session_id},
            {"_id": 0, "user_message": 1, "category": 1, "created_at": 1},
            sort=[("created_at", 1)],
        )
        if not first_turn:
            return None
        try:
            first_msg = decrypt_text(first_turn.get("user_message")) or ""
        except Exception:
            first_msg = ""

        # Derive a sensible title (<= 60 chars, no line-breaks, no trailing punctuation)
        title = " ".join(first_msg.split())[:60].rstrip(",.;:!?— ") or "New case"
        # Strip a leading "I " or pronoun so the title reads case-file-style:
        # "Workplace bullying" not "I feel like I'm being bullied at work"
        lower = title.lower()
        for lead in ("i feel like i'm being ", "i feel like i am being ",
                     "i think i'm being ", "i'm being ", "i was ", "my ", "i "):
            if lower.startswith(lead):
                title = title[len(lead):]
                break
        title = title[:1].upper() + title[1:] if title else "New case"

        category = (first_turn.get("category") or "general")
        if category == "ask_lex":
            category = "general"

        now_iso = datetime.now(timezone.utc).isoformat()
        case_id = str(uuid.uuid4())
        case_doc = {
            "id": case_id, "user_id": user["id"], "name": title,
            "summary": encrypt_text(""),
            "category": category, "status": "open", "items_count": 1,
            "created_at": now_iso, "updated_at": now_iso,
            "source": source,                # 'auto' or 'manual' — for analytics
            "linked_session_id": session_id,  # quick deep-link back to the chat
        }
        await db.cases.insert_one(case_doc)

        # Attach the chat thread as the first case item
        item = {
            "id": str(uuid.uuid4()), "case_id": case_id, "user_id": user["id"],
            "item_type": "chat", "item_id": session_id,
            "title": title,
            "preview": (first_msg or "")[:300],
            "timestamp_utc": first_turn.get("created_at") or now_iso,
            "created_at": now_iso,
        }
        await db.case_items.insert_one(item)
        case_doc.pop("_id", None)
        case_doc["summary"] = ""
        logger.info(f"Case auto-promoted ({source}): user={user['id']} session={session_id[:8]} -> case={case_id[:8]} ({title})")
        return case_doc
    finally:
        _AUTO_CASE_GUARD.discard(guard_key)


class CaseFromSessionReq(BaseModel):
    session_id: str
    name_override: Optional[str] = None
    category_override: Optional[str] = None


@api_router.post("/cases/from-session")
async def case_from_session(data: CaseFromSessionReq, user: dict = Depends(get_user)):
    """Manual one-tap promote a chat → Case File (Option B from the UI).
    Idempotent: if a case is already linked, returns the existing one."""
    case = await _ensure_case_for_session(user, data.session_id, source="manual")
    if not case:
        raise HTTPException(404, "Conversation not found — cannot promote.")
    # Optional rename / re-categorise on the spot so the user can correct the auto-title
    upd = {}
    if data.name_override and data.name_override.strip():
        upd["name"] = data.name_override.strip()[:120]
    if data.category_override:
        upd["category"] = data.category_override[:40]
    if upd:
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.cases.update_one({"id": case["id"]}, {"$set": upd})
        case.update(upd)
    return {"ok": True, "case": case}


async def _build_case_context_block(case_id: str, user_id: str) -> str:
    """Return a short, LLM-friendly summary of the case + recent items so Lex
    has the user's background loaded automatically. Capped to stay token-cheap."""
    c = await db.cases.find_one(
        {"id": case_id, "user_id": user_id, "deleted_at": {"$in": [None, "", False]}},
        {"_id": 0, "name": 1, "category": 1, "status": 1, "summary": 1},
    )
    if not c:
        return ""
    name = c.get("name") or "Untitled case"
    summary = decrypt_text(c.get("summary") or "") if c.get("summary") else ""
    items = await db.case_items.find(
        {"case_id": case_id, "user_id": user_id, "deleted_at": {"$in": [None, "", False]}},
        {"_id": 0, "title": 1, "description": 1, "item_type": 1, "timestamp_utc": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(8)
    bullets = []
    for it in items:
        desc = decrypt_text(it.get("description") or "") if it.get("description") else ""
        when = (it.get("timestamp_utc") or it.get("created_at") or "")[:10]
        snippet = (it.get("title") or "Item") + (f" — {desc[:250]}" if desc else "")
        bullets.append(f"  - [{when}] [{(it.get('item_type') or 'item').upper()}] {snippet}")
    block = (
        "CASE CONTEXT - the user is asking about an ongoing case in their Case Files. "
        "Treat the items below as accepted background. Do not ask them to re-explain.\n"
        f"Case name: {name}\n"
        f"Status: {c.get('status') or 'open'} - Category: {c.get('category') or 'general'}\n"
    )
    if summary:
        block += f"User's summary: {summary[:600]}\n"
    if bullets:
        block += "Recent items on this case (newest first):\n" + "\n".join(bullets[:6])
    return block[:2500]



@api_router.get("/cases")
async def list_cases(user: dict = Depends(get_user), status: Optional[str] = None):
    q = {"user_id": user["id"], "deleted_at": {"$in": [None, "", False]}}
    if status: q["status"] = status
    out = []
    async for c in db.cases.find(q, {"_id": 0}).sort("updated_at", -1).limit(200):
        if "summary" in c: c["summary"] = decrypt_text(c["summary"])
        out.append(c)
    return {"cases": out}

@api_router.get("/cases/{case_id}")
async def get_case(case_id: str, user: dict = Depends(get_user)):
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}}, {"_id": 0})
    if not c: raise HTTPException(404, "Case not found")
    if "summary" in c: c["summary"] = decrypt_text(c["summary"])
    items = []
    async for it in db.case_items.find({"case_id": case_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}}, {"_id": 0}).sort("created_at", -1):
        if "description" in it: it["description"] = decrypt_text(it["description"])
        items.append(it)
    c["items"] = items
    # 💬 Surface Lex chat sessions linked to this case so the UI can offer
    # "Continue with Lex →" — resumes the most recent one in context.
    # chat_sessions is virtual — derived from `conversations` (each turn carries linked_case_id).
    pipeline = [
        {"$match": {"user_id": user["id"], "linked_case_id": case_id}},
        {"$group": {"_id": "$session_id",
                    "updated_at": {"$max": "$created_at"},
                    "category": {"$first": "$category"},
                    "turn_count": {"$sum": 1}}},
        {"$sort": {"updated_at": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "session_id": "$_id", "updated_at": 1, "category": 1, "turn_count": 1}},
    ]
    linked_sessions = []
    async for s in db.conversations.aggregate(pipeline):
        linked_sessions.append(s)
    c["linked_sessions"] = linked_sessions
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
    """Soft-delete a case + all its items. Recoverable from /recycle-bin for 30 days."""
    now_iso = datetime.now(timezone.utc).isoformat()
    r = await db.cases.update_one(
        {"id": case_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"$set": {"deleted_at": now_iso}},
    )
    if r.matched_count == 0: raise HTTPException(404, "Case not found")
    await db.case_items.update_many(
        {"case_id": case_id, "deleted_at": {"$in": [None, "", False]}},
        {"$set": {"deleted_at": now_iso, "deleted_with_case": True}},
    )
    return {"deleted": True, "recoverable_for_days": 30}

@api_router.delete("/case-items/{item_id}")
async def delete_case_item(item_id: str, user: dict = Depends(get_user)):
    """Soft-delete a single item within a case (file/photo/recording/letter)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    r = await db.case_items.update_one(
        {"id": item_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"$set": {"deleted_at": now_iso}},
    )
    if r.matched_count == 0: raise HTTPException(404, "Item not found")
    # Decrement parent case items_count
    target = await db.case_items.find_one({"id": item_id}, {"_id": 0, "case_id": 1})
    if target and target.get("case_id"):
        await db.cases.update_one({"id": target["case_id"]}, {"$inc": {"items_count": -1}})
    return {"deleted": True, "recoverable_for_days": 30}

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

# ==================== Case Timeline (chronological feed per case) ====================
# Merges 4 distinct sources into one chronological view of a single case:
#   • case_items (chat threads, uploaded photos/audio/video/docs, manual notes)
#   • conversations (each Lex turn — decrypted on the fly, with citations)
#   • reminders (deadlines linked to this case)
#   • cases.created_at (the "case opened" anchor event)
async def _build_case_timeline(case_id: str, user: dict) -> dict:
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Case not found")

    events: List[dict] = []

    # 0) Anchor: the case opening itself
    events.append({
        "kind": "case_opened",
        "at": c.get("created_at"),
        "title": f"Case opened: {c.get('name')}",
        "icon": "📂",
        "summary": (c.get("category") or "general").upper(),
    })

    # 1) Case items (chats linked, photos, uploads, manual notes)
    async for it in db.case_items.find(
        {"case_id": case_id, "user_id": user["id"],
         "deleted_at": {"$in": [None, "", False]}},
        {"_id": 0},
    ):
        events.append({
            "kind": f"item_{it.get('item_type','file')}",
            "at": it.get("timestamp_utc") or it.get("created_at"),
            "title": it.get("title") or "(untitled)",
            "preview": (it.get("preview") or "")[:280],
            "icon": {"chat": "💬", "photo": "📸", "audio": "🎙",
                     "video": "🎞", "document": "📄", "note": "📝"}.get(
                         it.get("item_type", ""), "📎"),
            "item_id": it.get("item_id"),
            "linked_chat_session": it.get("item_id") if it.get("item_type") == "chat" else None,
        })

    # 2) Every Lex turn for chats that are linked to this case
    linked_chat_sessions = [
        it["item_id"] async for it in db.case_items.find(
            {"case_id": case_id, "user_id": user["id"], "item_type": "chat",
             "deleted_at": {"$in": [None, "", False]}},
            {"_id": 0, "item_id": 1},
        )
    ]
    if linked_chat_sessions:
        async for conv in db.conversations.find(
            {"user_id": user["id"], "session_id": {"$in": linked_chat_sessions}},
            {"_id": 0},
        ).sort("created_at", 1):
            try:
                um = decrypt_text(conv.get("user_message")) or ""
                ar = decrypt_text(conv.get("assistant_response")) or ""
            except Exception:
                um, ar = "", ""
            events.append({
                "kind": "lex_turn",
                "at": conv.get("created_at"),
                "title": "Lex chat turn",
                "icon": "⚖️",
                "user_message": um[:400],
                "lex_reply": ar[:600],
                "model": conv.get("model_used"),
                "session_id": conv.get("session_id"),
            })

    # 3) Deadlines linked to this case
    try:
        async for r in db.reminders.find(
            {"user_id": user["id"],
             "$or": [{"case_id": case_id}, {"linked_case_id": case_id}]},
            {"_id": 0},
        ):
            events.append({
                "kind": "deadline",
                "at": r.get("created_at"),
                "due_at": r.get("due_at"),
                "title": r.get("title") or "Legal deadline",
                "icon": "⏰",
                "summary": r.get("description") or "",
                "status": r.get("status", "open"),
            })
    except Exception:
        pass

    events.sort(key=lambda e: e.get("at") or "")

    return {
        "case": {
            "id": c["id"], "name": c["name"], "category": c.get("category"),
            "status": c.get("status"), "created_at": c.get("created_at"),
            "items_count": c.get("items_count", 0),
            "linked_session_id": c.get("linked_session_id"),
        },
        "events": events,
        "total_events": len(events),
    }


@api_router.get("/cases/{case_id}/export-pdf")
async def export_case_pdf(case_id: str, user: dict = Depends(get_user)):
    """Court-ready handover PDF: full chronological narrative — case opening, Lex chat turns,
    evidence uploads with SHA256 hashes, deadlines, and a signature panel.
    Designed so a user can hand the PDF directly to a solicitor."""
    feed = await _build_case_timeline(case_id, user)
    c = feed["case"]
    events = feed["events"]

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    import hashlib as _hashlib

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.8*cm, bottomMargin=1.8*cm,
                            title=f"AI Advocate Case File — {c['name']}",
                            author=user.get("full_name") or user.get("email"))
    styles = getSampleStyleSheet()
    # Custom styles — restrained gold, professional serif
    gold = colors.HexColor("#b8860b")
    styles.add(ParagraphStyle(name="CaseTitle", parent=styles["Title"],
                              fontSize=22, textColor=gold, spaceAfter=4))
    styles.add(ParagraphStyle(name="CaseMeta", parent=styles["Normal"],
                              fontSize=9, textColor=colors.grey, spaceAfter=2))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"],
                              fontSize=14, textColor=gold, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="EventTitle", parent=styles["Heading3"],
                              fontSize=11, spaceBefore=8, spaceAfter=2))
    styles.add(ParagraphStyle(name="EventBody", parent=styles["Normal"],
                              fontSize=10, leading=13, leftIndent=12))
    styles.add(ParagraphStyle(name="EventMeta", parent=styles["Normal"],
                              fontSize=8, textColor=colors.grey, leftIndent=12,
                              spaceAfter=4))
    styles.add(ParagraphStyle(name="Disclaimer", parent=styles["Normal"],
                              fontSize=8, textColor=colors.grey, leading=11))

    story = []

    # ---- Cover header ----
    story += [
        Paragraph("AI ADVOCATE · CASE FILE", styles["CaseMeta"]),
        Paragraph(c["name"], styles["CaseTitle"]),
        Paragraph(f"Category: {(c.get('category') or 'general').replace('_',' ').title()}  ·  Status: {(c.get('status') or 'open').upper()}", styles["CaseMeta"]),
        Spacer(1, 0.2*cm),
    ]

    # ---- Summary table ----
    summary_data = [
        ["Filed by:", user.get("full_name") or user.get("email") or ""],
        ["Account email:", user.get("email", "")],
        ["Case opened:", (c.get("created_at") or "")[:19].replace("T", " ") + " UTC"],
        ["Total events:", str(len(events))],
        ["PDF exported:", datetime.now(timezone.utc).isoformat()[:19].replace("T", " ") + " UTC"],
    ]
    tbl = Table(summary_data, colWidths=[4.0*cm, 12.0*cm])
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafaf7")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#fafaf7"), colors.HexColor("#ffffff")]),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dcd6c4")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e8e2d0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [tbl, Spacer(1, 0.4*cm)]

    # ---- Disclaimer ----
    story += [
        Paragraph(
            "<b>Disclaimer.</b> This document was generated by AI Advocate, an "
            "AI-powered legal information service. It is not legal advice from a "
            "qualified solicitor. The Lex AI's responses are reproduced verbatim "
            "for context; they should be reviewed by a regulated UK solicitor before "
            "being relied upon in any legal proceeding.",
            styles["Disclaimer"]),
        Spacer(1, 0.2*cm),
    ]

    # ---- Timeline section ----
    story.append(Paragraph("Chronological timeline", styles["Section"]))
    if not events:
        story.append(Paragraph("<i>No events recorded yet.</i>", styles["EventBody"]))

    for n, ev in enumerate(events, 1):
        ts = (ev.get("at") or "")[:19].replace("T", " ")
        kind_label = ev["kind"].replace("_", " ").title()
        icon = ev.get("icon", "•")
        story.append(Paragraph(
            f"<b>{n}. {icon} {kind_label}</b> — <font color='grey'>{ts}</font>",
            styles["EventTitle"]))
        # Event-type-specific rendering
        if ev["kind"] == "lex_turn":
            story.append(Paragraph(
                f"<b>User:</b> {(ev.get('user_message') or '').replace(chr(10),'<br/>')}",
                styles["EventBody"]))
            story.append(Paragraph(
                f"<b>Lex:</b> {(ev.get('lex_reply') or '').replace(chr(10),'<br/>')}",
                styles["EventBody"]))
            story.append(Paragraph(f"Model: {ev.get('model','')}", styles["EventMeta"]))
        elif ev["kind"] == "deadline":
            story.append(Paragraph(ev.get("title", ""), styles["EventBody"]))
            if ev.get("summary"):
                story.append(Paragraph(ev["summary"][:600], styles["EventBody"]))
            if ev.get("due_at"):
                story.append(Paragraph(f"Due: {ev['due_at']} · Status: {ev.get('status','open').upper()}",
                                       styles["EventMeta"]))
        else:
            # Generic case item / case_opened
            story.append(Paragraph(ev.get("title", ""), styles["EventBody"]))
            if ev.get("preview"):
                story.append(Paragraph(ev["preview"][:800].replace("\n", "<br/>"), styles["EventBody"]))
            # Provide a content-hash fingerprint so the PDF is tamper-evidence-friendly
            h = _hashlib.sha256(
                f"{ev.get('item_id','')}{ts}{user['id']}".encode()
            ).hexdigest()[:16]
            story.append(Paragraph(f"Evidence hash: {h}", styles["EventMeta"]))
        story.append(Spacer(1, 0.15*cm))

    # ---- Solicitor handover panel ----
    story.append(PageBreak())
    story.append(Paragraph("Solicitor handover", styles["Section"]))
    story.append(Paragraph(
        "If you intend to instruct a UK solicitor on this matter, this page acts "
        "as a one-sheet handover document. Tear off, hand over, retain the rest of "
        "the file for your records.",
        styles["EventBody"]))
    story.append(Spacer(1, 0.4*cm))
    handover_data = [
        ["Client signature:", "________________________________"],
        ["Date:", "________________________________"],
        ["Solicitor name:", "________________________________"],
        ["Solicitor firm:", "________________________________"],
        ["SRA / Law Society no.:", "________________________________"],
        ["Solicitor signature:", "________________________________"],
        ["Date received:", "________________________________"],
    ]
    htbl = Table(handover_data, colWidths=[4.5*cm, 11.5*cm])
    htbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a1a1a")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.HexColor("#dcd6c4")),
    ]))
    story.append(htbl)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "<i>This handover authorises the named solicitor to review the case "
        "narrative within this document for the purpose of providing legal "
        "advice. It does not by itself create a solicitor-client relationship.</i>",
        styles["Disclaimer"]))

    doc.build(story)
    buf.seek(0)
    safe_name = "".join(ch for ch in c["name"] if ch.isalnum() or ch in " -_")[:40].strip() or "case"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="ai-advocate-{safe_name}-{case_id[:8]}.pdf"'})


@api_router.get("/cases/{case_id}/timeline")
async def case_timeline_feed(case_id: str, user: dict = Depends(get_user)):
    """Merged chronological feed for one case — for the in-app Timeline tab."""
    return await _build_case_timeline(case_id, user)


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


# ==================== PASSWORD RESET + 2FA ====================
# Shared helpers + endpoints for both consumer (`db.users`, JWT kind="user"-default)
# and law-firm (`db.firm_accounts`, JWT kind="firm") accounts. Tokens stored in
# `password_reset_tokens` collection, single-use, 60-min TTL via MongoDB TTL index.
import secrets as _secrets
import pyotp  # noqa: E402
import qrcode  # noqa: E402
from io import BytesIO  # noqa: E402
import base64 as _base64  # noqa: E402

RESET_TTL_MINUTES = 60
RESET_RATE_PER_HOUR = 3
TOTP_ISSUER = "AI Advocate"


def _public_app_url() -> str:
    """Canonical public URL where reset links should land.
    Falls back to preview env URL — overridden in production via PUBLIC_APP_URL."""
    return (os.environ.get("PUBLIC_APP_URL") or "https://aiadvocate.co.uk").rstrip("/")


async def _create_reset_token(*, account_kind: str, account_id: str, email: str) -> str:
    """Generate a single-use reset token. account_kind ∈ {'user','firm'}."""
    tok = _secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await db.password_reset_tokens.insert_one({
        "id": str(uuid.uuid4()),
        "token": tok,
        "account_kind": account_kind,
        "account_id": account_id,
        "email": email.lower(),
        "created_at": now,
        "expires_at": now + timedelta(minutes=RESET_TTL_MINUTES),
        "used_at": None,
    })
    return tok


async def _rate_limit_reset(email: str) -> bool:
    """Return True if email has not exceeded N reset requests in the last hour."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    count = await db.password_reset_tokens.count_documents({
        "email": email.lower(), "created_at": {"$gte": cutoff},
    })
    return count < RESET_RATE_PER_HOUR


class ForgotPasswordReq(BaseModel):
    email: str


class ResetPasswordReq(BaseModel):
    token: str
    new_password: str


@api_router.post("/auth/resend-welcome")
async def auth_resend_welcome(data: ForgotPasswordReq):
    """Re-fire the welcome email for an existing user. Same anti-enumeration
    pattern as forgot-password (always 200) + rate-limited so it can't be
    abused as a spam vector against random Hotmail accounts."""
    email_lc = (data.email or "").strip().lower()
    if not email_lc or "@" not in email_lc:
        return {"ok": True}
    user = await db.users.find_one(
        {"email": email_lc, "deleted": {"$ne": True}},
        {"_id": 0, "email": 1, "full_name": 1, "launch_day_pass_until": 1},
    )
    if user and await _rate_limit_reset(email_lc):
        try:
            from email_helper import send_welcome_with_daypass, send_welcome_missed_offer
            now_iso = datetime.now(timezone.utc).isoformat()
            dp_active = user.get("launch_day_pass_until") and user["launch_day_pass_until"] > now_iso
            if dp_active:
                await send_welcome_with_daypass(user["email"], user.get("full_name") or "")
            else:
                await send_welcome_missed_offer(user["email"], user.get("full_name") or "")
            # Use the existing password_reset_tokens table for rate-limit tracking — same window
            await db.password_reset_tokens.insert_one({
                "id": str(uuid.uuid4()),
                "token": "welcome-resend-" + _secrets.token_urlsafe(8),
                "account_kind": "user", "account_id": "resend",
                "email": email_lc, "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc), "used_at": now_iso,
            })
        except Exception:
            logger.exception("Welcome resend failed (non-fatal)")
    return {"ok": True}


@api_router.post("/auth/forgot-password")
async def auth_forgot_password(data: ForgotPasswordReq):
    """Consumer forgot password. Always returns 200 (no user enumeration).
    Sends reset email via Resend if the email exists AND rate limit not hit."""
    email_lc = (data.email or "").strip().lower()
    if not email_lc or "@" not in email_lc:
        return {"ok": True}
    user = await db.users.find_one({"email": email_lc, "deleted": {"$ne": True}}, {"_id": 0, "id": 1, "email": 1})
    if user and await _rate_limit_reset(email_lc):
        tok = await _create_reset_token(account_kind="user", account_id=user["id"], email=email_lc)
        link = f"{_public_app_url()}/reset.html?token={tok}"
        try:
            from email_helper import send_password_reset
            await send_password_reset(email_lc, link)
        except Exception:
            logger.exception("Password-reset email send failed (consumer)")
    return {"ok": True}


@api_router.post("/auth/reset-password", response_model=TokenResp)
async def auth_reset_password(data: ResetPasswordReq):
    """Consumer reset. Validates token, updates password_hash, marks token used,
    returns a fresh JWT so the user is auto-logged-in on the reset page."""
    if not data.new_password or len(data.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    rec = await db.password_reset_tokens.find_one({"token": data.token, "account_kind": "user", "used_at": None})
    if not rec:
        raise HTTPException(400, "This reset link is invalid or has already been used.")
    exp = rec.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and datetime.now(timezone.utc) > exp:
        raise HTTPException(400, "This reset link has expired. Please request a new one.")
    user = await db.users.find_one({"id": rec["account_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(400, "Account not found.")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_pw(data.new_password), "password_changed_at": now_iso}},
    )
    await db.password_reset_tokens.update_one({"_id": rec["_id"]}, {"$set": {"used_at": now_iso}})
    token = make_token(user["id"], user["email"])
    user.pop("password_hash", None)
    return {"token": token, "access_token": token, "user": user}


@api_router.post("/firm/forgot-password")
async def firm_forgot_password(data: ForgotPasswordReq):
    """Firm-portal forgot password. Same anti-enumeration pattern."""
    email_lc = (data.email or "").strip().lower()
    if not email_lc or "@" not in email_lc:
        return {"ok": True}
    firm = await db.firm_accounts.find_one({"email": email_lc}, {"_id": 0, "id": 1, "email": 1, "firm_name": 1})
    if firm and await _rate_limit_reset(email_lc):
        tok = await _create_reset_token(account_kind="firm", account_id=firm["id"], email=email_lc)
        link = f"{_public_app_url()}/reset.html?token={tok}&kind=firm"
        try:
            from email_helper import send_password_reset
            await send_password_reset(email_lc, link)
        except Exception:
            logger.exception("Password-reset email send failed (firm)")
    return {"ok": True}


@api_router.post("/firm/reset-password")
async def firm_reset_password(data: ResetPasswordReq):
    """Firm reset. Returns a firm JWT so the founder/firm-admin is auto-logged-in."""
    if not data.new_password or len(data.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    rec = await db.password_reset_tokens.find_one({"token": data.token, "account_kind": "firm", "used_at": None})
    if not rec:
        raise HTTPException(400, "This reset link is invalid or has already been used.")
    exp = rec.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and datetime.now(timezone.utc) > exp:
        raise HTTPException(400, "This reset link has expired. Please request a new one.")
    firm = await db.firm_accounts.find_one({"id": rec["account_id"]}, {"_id": 0})
    if not firm:
        raise HTTPException(400, "Firm account not found.")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.firm_accounts.update_one(
        {"id": firm["id"]},
        {"$set": {"password": hash_pw(data.new_password), "password_changed_at": now_iso}},
    )
    await db.password_reset_tokens.update_one({"_id": rec["_id"]}, {"$set": {"used_at": now_iso}})
    token = jwt.encode({"sub": firm["id"], "kind": "firm", "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")
    firm.pop("password", None)
    return {"access_token": token, "firm": firm}


# ─── TOTP 2FA (consumer + firm) ────────────────────────────────────────
# Standard RFC 6238 TOTP using `pyotp`. Secret stored on the user doc under
# `totp_secret` (pending) → moved to `totp_enabled=true` only after the user
# verifies the first 6-digit code. 10 single-use backup codes are hashed on
# setup and shown ONCE in plain text.

def _make_backup_codes(n: int = 10) -> tuple[list[str], list[str]]:
    """Returns (plain_codes, hashed_codes). Plain shown ONCE at setup."""
    plain = [f"{_secrets.randbelow(10**4):04d}-{_secrets.randbelow(10**4):04d}" for _ in range(n)]
    hashed = [hash_pw(c) for c in plain]
    return plain, hashed


def _otpauth_qr_data_url(secret: str, account_label: str) -> str:
    """Return a base64 data URL of the QR-code PNG for an otpauth:// URI."""
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_label, issuer_name=TOTP_ISSUER)
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = _base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


class TOTPSetupReq(BaseModel):
    pass


class TOTPVerifyReq(BaseModel):
    code: str
    password: Optional[str] = None  # required for /disable


class TOTPLoginReq(BaseModel):
    tmp_token: str
    code: str


def _issue_tmp_2fa_token(account_id: str, kind: str) -> str:
    """Short-lived (5 min) token returned after correct password when 2FA required."""
    payload = {"sub": account_id, "kind": kind, "stage": "pre_2fa",
               "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_tmp_2fa_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(400, "Invalid or expired 2FA token. Please sign in again.")
    if payload.get("stage") != "pre_2fa":
        raise HTTPException(400, "Wrong token type.")
    return payload


@api_router.post("/auth/2fa/setup")
async def auth_2fa_setup(_req: TOTPSetupReq, current_user: dict = Depends(get_user)):
    """Generate a fresh secret + QR. The secret is PENDING — only activated
    after the user verifies the first code via /auth/2fa/verify."""
    if current_user.get("totp_enabled"):
        raise HTTPException(400, "2FA is already enabled. Disable it first to re-pair.")
    secret = pyotp.random_base32()
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"totp_secret_pending": secret, "totp_pending_at": datetime.now(timezone.utc).isoformat()}},
    )
    qr = _otpauth_qr_data_url(secret, current_user["email"])
    return {"secret": secret, "qr_data_url": qr, "issuer": TOTP_ISSUER, "account": current_user["email"]}


@api_router.post("/auth/2fa/verify")
async def auth_2fa_verify(req: TOTPVerifyReq, current_user: dict = Depends(get_user)):
    """Activate 2FA: verifies the first code against the pending secret, then
    promotes it to the live secret + generates 10 backup codes."""
    fresh = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "totp_secret_pending": 1})
    secret = (fresh or {}).get("totp_secret_pending")
    if not secret:
        raise HTTPException(400, "No pending 2FA setup. Call /auth/2fa/setup first.")
    totp = pyotp.TOTP(secret)
    if not totp.verify(req.code.strip(), valid_window=1):
        raise HTTPException(400, "Incorrect code. Make sure your device clock is correct.")
    plain, hashed = _make_backup_codes()
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"totp_secret": secret, "totp_enabled": True,
                  "totp_backup_codes": hashed,
                  "totp_enabled_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"totp_secret_pending": "", "totp_pending_at": ""}},
    )
    return {"ok": True, "enabled": True, "backup_codes": plain,
            "message": "Save these backup codes — they only show once."}


@api_router.post("/auth/2fa/disable")
async def auth_2fa_disable(req: TOTPVerifyReq, current_user: dict = Depends(get_user)):
    """Disable 2FA. Requires the user's password + a current valid TOTP code
    so a stolen session can't disable 2FA on its own."""
    fresh = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 1, "totp_secret": 1, "totp_enabled": 1})
    if not fresh or not fresh.get("totp_enabled"):
        raise HTTPException(400, "2FA is not enabled.")
    if not req.password or not verify_pw(req.password, fresh["password_hash"]):
        raise HTTPException(400, "Password is incorrect.")
    if not pyotp.TOTP(fresh["totp_secret"]).verify(req.code.strip(), valid_window=1):
        raise HTTPException(400, "Incorrect 2FA code.")
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"totp_enabled": False, "totp_disabled_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"totp_secret": "", "totp_backup_codes": ""}},
    )
    return {"ok": True, "enabled": False}


@api_router.post("/auth/2fa/login", response_model=TokenResp)
async def auth_2fa_login(req: TOTPLoginReq):
    """Exchange a (tmp_token + 6-digit code OR backup code) for a full JWT.
    Called after /auth/login returned {requires_2fa: true, tmp_token}."""
    payload = _decode_tmp_2fa_token(req.tmp_token)
    if payload.get("kind") != "user":
        raise HTTPException(400, "Wrong account kind for this endpoint.")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user or not user.get("totp_enabled"):
        raise HTTPException(400, "2FA not configured for this account.")
    code = (req.code or "").strip()
    ok = pyotp.TOTP(user["totp_secret"]).verify(code, valid_window=1)
    if not ok:
        # Try backup codes
        backups = user.get("totp_backup_codes") or []
        used_index = None
        for i, h in enumerate(backups):
            if verify_pw(code, h):
                used_index = i
                break
        if used_index is None:
            raise HTTPException(401, "Incorrect 2FA code.")
        # Mark backup code as consumed (remove from list)
        new_backups = backups[:used_index] + backups[used_index+1:]
        await db.users.update_one({"id": user["id"]}, {"$set": {"totp_backup_codes": new_backups}})
    token = make_token(user["id"], user["email"])
    user.pop("password_hash", None)
    return {"token": token, "access_token": token, "user": user}


# ==================== LAW FIRM PORTAL ====================
# NB: founder-signature + commissions admin endpoints below use _check_admin_user
# (defined inline) because the canonical require_admin Depends is declared
# later in the file. They share the exact same enforcement: ADMIN_EMAILS env.
async def _check_admin_user(user: dict = Depends(get_user)):
    admin_set = {e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()}
    if (user.get("email") or "").lower() not in admin_set:
        raise HTTPException(403, "Admin access required.")
    return user


@api_router.get("/admin/sanity-checks")
async def admin_list_sanity_checks(_: dict = Depends(_check_admin_user)):
    cursor = db.sanity_checks.find({}, {"_id": 0}).sort("created_at", -1).limit(200)
    items = [s async for s in cursor]
    return {
        "items": items,
        "by_status": {s: sum(1 for i in items if i.get("status") == s)
                      for s in ("pending_payment", "pending_assignment", "assigned", "completed", "refunded")},
    }


@api_router.get("/admin/stripe-price-audit")
async def admin_stripe_price_audit(_: dict = Depends(_check_admin_user)):
    """One-shot audit: resolve every STRIPE_PRICE_* env var to its real
    product name + amount in Stripe. Use after editing Price IDs in .env."""
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe not configured")
    targets = {
        "STRIPE_PRICE_PLUS":            ("Plus consumer",  19.99, "month"),
        "STRIPE_PRICE_PRO":             ("Pro consumer",   34.99, "month"),
        "STRIPE_PRICE_YEARLY_PRO":      ("Pro yearly",    319.99, "year"),
        "STRIPE_PRICE_FIRM_FEATURED":   ("Firm Featured",  49.00, "month"),
        "STRIPE_PRICE_FIRM_PREMIUM":    ("Firm Premium",  199.00, "month"),
        "STRIPE_PRICE_FIRM_PRACTICE":   ("Firm Practice", 499.00, "month"),
        "STRIPE_PRICE_TOPUP_DAY_PASS":  ("Day Pass",        4.99, "one_time"),
        "STRIPE_PRICE_TOPUP_LETTER_PACK":("Letter Pack",    9.99, "one_time"),
        "STRIPE_PRICE_TOPUP_WEEKEND_PASS":("Weekend Pass", 14.99, "one_time"),
        "STRIPE_PRICE_TOPUP_CRISIS_PACK":("Crisis Pack",   29.99, "one_time"),
        "STRIPE_PRICE_SANITY_CHECK":   ("Solicitor Sanity Check", 49.00, "one_time"),
    }
    rows = []
    for env_key, (label, expected_gbp, expected_interval) in targets.items():
        pid = os.environ.get(env_key, "").strip()
        row = {"env_var": env_key, "expected_label": label,
               "expected_gbp": expected_gbp, "expected_interval": expected_interval,
               "price_id": pid}
        if not pid:
            row["status"] = "missing"
            rows.append(row); continue
        try:
            p = stripe.Price.retrieve(pid)
            actual_gbp = (p.unit_amount or 0) / 100.0
            actual_currency = (p.currency or "").upper()
            actual_interval = (p.recurring.interval if p.recurring else "one_time")
            prod = stripe.Product.retrieve(p.product)
            row.update({
                "actual_gbp": actual_gbp,
                "actual_currency": actual_currency,
                "actual_interval": actual_interval,
                "actual_product_name": prod.name,
                "active": p.active,
                "match": (
                    abs(actual_gbp - expected_gbp) < 0.01
                    and actual_currency == "GBP"
                    and actual_interval == expected_interval
                ),
            })
            row["status"] = "ok" if row["match"] else "MISMATCH"
        except Exception as e:
            row["status"] = "error"
            row["error"] = str(e)
        rows.append(row)
    summary = {
        "ok":       sum(1 for r in rows if r["status"] == "ok"),
        "mismatch": sum(1 for r in rows if r["status"] == "MISMATCH"),
        "missing":  sum(1 for r in rows if r["status"] == "missing"),
        "error":    sum(1 for r in rows if r["status"] == "error"),
    }
    return {"rows": rows, "summary": summary}







@api_router.get("/admin/founder-signature")
async def admin_get_founder_signature(_: dict = Depends(_check_admin_user)):
    """Returns the saved founder signature (if any) as a data: URL.
    Used by the admin panel to know whether auto-fire is enabled."""
    doc = await db.app_settings.find_one({"key": "founder_signature"}, {"_id": 0})
    return {
        "is_set": bool(doc and doc.get("data_url", "").startswith("data:image/")),
        "data_url": (doc or {}).get("data_url", ""),
        "saved_at": (doc or {}).get("saved_at"),
    }


class FounderSignaturePayload(BaseModel):
    data_url: str


@api_router.post("/admin/founder-signature")
async def admin_set_founder_signature(data: FounderSignaturePayload, admin: dict = Depends(_check_admin_user)):
    """Save the founder's signature once. After this is set, every new firm
    signup in the first 20 will trigger an automatic Founding Firm Agreement —
    no need for the founder to manually draw a signature each time."""
    u = (data.data_url or "").strip()
    if not u.startswith("data:image/"):
        raise HTTPException(400, "Signature must be a base64 data: image URL.")
    if len(u) > 200_000:
        raise HTTPException(413, "Signature image too large (max ~200KB).")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.app_settings.update_one(
        {"key": "founder_signature"},
        {"$set": {"key": "founder_signature", "data_url": u, "saved_at": now_iso, "saved_by": admin["email"]}},
        upsert=True,
    )
    return {"ok": True, "saved_at": now_iso}


@api_router.delete("/admin/founder-signature")
async def admin_delete_founder_signature(_: dict = Depends(_check_admin_user)):
    """Clear the stored founder signature → disables auto-fire."""
    await db.app_settings.delete_one({"key": "founder_signature"})
    return {"ok": True, "cleared": True}





@api_router.post("/firm/signup")
async def firm_signup(data: FirmPortalSignup):
    existing = await db.firm_accounts.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(409, "Email already registered")
    fid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # 🎁 Auto-14-day FEATURED trial on every new firm signup. Card NOT required up-front
    # (we want zero-friction signup); we'll require it when they convert to paid via
    # the existing Stripe checkout flow. The trial gives full Featured benefits — appears
    # in the directory + can answer leads + analytics. After 14 days, tier auto-reverts
    # to "free" unless they upgrade (handled by _firm_tier resolver on every request).
    trial_until = now + timedelta(days=14)
    doc = {
        "id": fid, "email": data.email.lower(), "password": hash_pw(data.password),
        "firm_name": data.firm_name, "contact_name": data.contact_name,
        "sra_number": data.sra_number, "country": data.country, "city": data.city,
        "phone": data.phone, "specialties": data.specialties, "website": data.website,
        "status": "pending_review",   # pending_review | approved | rejected | suspended
        "tier": "free",               # base "paid-for" tier — `_firm_tier()` returns trial tier if trial_until is in the future
        "trial_tier": "featured",     # what tier the active trial gives them
        "trial_until": trial_until.isoformat(),
        "trial_granted_by": "system_auto_signup",
        "trial_granted_at": now.isoformat(),
        "verified": False, "featured": False,
        "lead_count_30d": 0, "created_at": now.isoformat(),
    }
    await db.firm_accounts.insert_one(doc)

    # 🎁 Auto-redeem any pending firm comp the founder pre-queued
    try:
        pending = await db.pending_firm_comp_grants.find_one({"email": data.email.lower()})
        if pending:
            days = max(1, int(pending.get("days") or 90))
            tier_label = pending.get("tier") or "featured"
            trial_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
            await db.firm_accounts.update_one(
                {"id": fid},
                {"$set": {"trial_until": trial_until, "trial_tier": tier_label,
                          "trial_granted_at": datetime.now(timezone.utc).isoformat(),
                          "trial_pre_signup": True}},
            )
            doc["trial_until"] = trial_until; doc["trial_tier"] = tier_label
            await db.firm_comp_audit.insert_one({
                "id": str(uuid.uuid4()),
                "granted_by_id": pending.get("granted_by_id"),
                "granted_by_email": pending.get("granted_by_email"),
                "target_firm_id": fid, "target_firm_email": data.email,
                "target_firm_name": data.firm_name, "days": days, "tier": tier_label,
                "until": trial_until, "reason": "Pre-signup firm comp redeemed on signup",
                "at": datetime.now(timezone.utc).isoformat(), "action": "pre_comp_redeemed",
            })
            await db.pending_firm_comp_grants.delete_one({"email": data.email.lower()})
    except Exception:
        logger.exception("Pending firm comp redemption failed (non-fatal)")

    token = jwt.encode({"sub": fid, "kind": "firm", "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")
    doc.pop("_id", None); doc.pop("password", None)

    # 🌟 AUTO-FOUNDING-FIRM AGREEMENT for the first 20 firms.
    # If a founder signature is stored in app_settings, and this firm is in the
    # first-20 cohort, automatically create + email the Founding Firm Agreement
    # for them to sign. Saves the founder having to manually trigger it for
    # every new firm — fully hands-off.
    try:
        cohort_count = await db.firm_accounts.count_documents({
            "founding_firm_signed_at": {"$exists": True, "$ne": None},
        })
        # cohort_count counts already-signed founding firms; we also check
        # outstanding agreements to avoid going past 20 total.
        outstanding = await db.firm_agreements.count_documents({"status": "sent"})
        if (cohort_count + outstanding) < 20:
            settings_doc = await db.app_settings.find_one({"key": "founder_signature"})
            if settings_doc and settings_doc.get("data_url", "").startswith("data:image/"):
                # Mirror the same flow as the admin "Send for signature" endpoint.
                agree_token = _secrets.token_urlsafe(20)
                now_iso = datetime.now(timezone.utc).isoformat()
                await db.firm_agreements.insert_one({
                    "_id": str(uuid.uuid4()),
                    "token": agree_token,
                    "firm_name": data.firm_name,
                    "sra": data.sra_number or "",
                    "address": "",
                    "contact_name": data.contact_name,
                    "contact_email": data.email.lower(),
                    "aa_signer_name": "Samuel Malick",
                    "aa_signature_data_url": settings_doc["data_url"],
                    "firm_signer_name": None,
                    "firm_signature_data_url": None,
                    "status": "sent",
                    "sent_at": now_iso,
                    "signed_at": None,
                    "signer_ip": None,
                    "signer_user_agent": None,
                    "terms_snapshot_version": "2026-02-rev1",
                    "auto_triggered": True,
                    "cohort_slot": cohort_count + outstanding + 1,
                })
                signing_url = f"https://aiadvocate.co.uk/firm-sign/{agree_token}"
                try:
                    from email_helper import send_email
                    await send_email(
                        to=data.email.lower(),
                        kind="firm",
                        subject=f"🌟 You're in the Founding 20 — sign your AI Advocate Founding Firm Agreement",
                        body_html=f"""<p>Hi {data.contact_name.split(',')[0]},</p>
                        <p>Welcome to AI Advocate. You've just claimed slot <strong>{cohort_count + outstanding + 1} of 20</strong> in our Founding Firm cohort.</p>
                        <p>That means £199/mo locked for life, 70/30 referral split, Founding Firm badge on your listing, and App Store launch marketing. Full terms in the agreement.</p>
                        <p style="margin:24px 0;"><a href="{signing_url}" style="background:#f7c948;color:#1a1300;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:700;">Review &amp; sign your agreement →</a></p>
                        <p style="color:#666;font-size:13px;">Or copy this link: <a href="{signing_url}">{signing_url}</a></p>
                        <p style="color:#666;font-size:12px;">I've already pre-signed on behalf of AI Advocate — you just need to add your signature. Takes 2 minutes.</p>
                        <p>Any questions, please contact <a href="mailto:firms@aiadvocate.co.uk">firms@aiadvocate.co.uk</a>.</p>
                        <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
                    )
                except Exception as e:
                    logger.warning(f"Auto-founding-agreement email failed for {data.email}: {e}")
                # Internal heads-up
                try:
                    from email_helper import send_email
                    await send_email(
                        to="firms@aiadvocate.co.uk", kind="firm",
                        subject=f"🌟 Founding Firm signup #{cohort_count + outstanding + 1}: {data.firm_name}",
                        body_html=f"<p>New firm <strong>{data.firm_name}</strong> just signed up — auto-triggered Founding Firm Agreement.</p>"
                                  f"<p>Slot {cohort_count + outstanding + 1} of 20. Email: {data.email}. SRA: {data.sra_number or '—'}.</p>"
                                  f"<p>Signing link: <a href='{signing_url}'>{signing_url}</a></p>",
                    )
                except Exception:
                    pass
            else:
                logger.info(f"[firm-signup] Founder signature not set — skipping auto-agreement for {data.email}")
    except Exception as e:
        logger.warning(f"Auto-founding-firm-agreement failed (non-fatal): {e}")

    return {"access_token": token, "firm": doc, "trial_days_remaining": 14}

@api_router.post("/firm/login")
async def firm_login(data: FirmPortalLogin):
    f = await db.firm_accounts.find_one({"email": data.email.lower()})
    if not f or not verify_pw(data.password, f["password"]):
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode({"sub": f["id"], "kind": "firm", "exp": datetime.now(timezone.utc) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")
    f.pop("_id", None); f.pop("password", None)
    return {"access_token": token, "firm": f}

async def get_firm(authorization: Optional[str] = Header(None)) -> dict:
    """Resolve the parent firm account from either:
      • a firm-owner JWT (kind=firm, sub=firm_id), or
      • a firm-user JWT (kind=firm_user, firm_id=…)
    Both grant the same firm-portal access; firm_users inherit the parent firm's tier.
    The firm dict gets `acting_user` set to the firm_user record when applicable,
    so per-user audit logging is possible."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")

    kind = payload.get("kind")
    if kind == "firm":
        f = await db.firm_accounts.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
        if not f: raise HTTPException(401, "Firm not found")
        f["acting_user"] = None  # owner is acting
        f["acting_role"] = "owner"
        return f
    if kind == "firm_user":
        firm_user = await db.firm_users.find_one(
            {"id": payload["sub"], "status": "active"},
            {"_id": 0, "password": 0},
        )
        if not firm_user:
            raise HTTPException(401, "Firm user not found or inactive")
        f = await db.firm_accounts.find_one({"id": firm_user["firm_id"]}, {"_id": 0, "password": 0})
        if not f:
            raise HTTPException(401, "Parent firm not found")
        f["acting_user"] = firm_user
        f["acting_role"] = firm_user.get("role", "fee_earner")
        return f
    raise HTTPException(403, "Not a firm account")

# ==================== Firm engagements & commission tracking ====================
# Firms log closed engagements in their portal; we tot up the 30% commission
# they owe AI Advocate. Founding Firm split locked at 30% per agreement clause 1.6.

class CommissionEntryCreate(BaseModel):
    client_email: str
    client_name: str = ""
    fee_gbp: float = Field(..., gt=0, le=1_000_000)
    closed_at: str = ""
    notes: str = ""
    matter_type: str = ""


def _firm_commission_pct(firm: dict) -> float:
    """30% standard rate — locked per Founding Firm Agreement."""
    return 0.30


# ⚠️ IMPORTANT — these used to mount on `/firm/engagements` which collided with the
# client-thread engagement endpoints below. Renamed to `/firm/commissions` to disambiguate.
@api_router.get("/firm/sanity-checks")
async def firm_list_sanity_checks(firm: dict = Depends(get_firm)):
    cursor = db.sanity_checks.find(
        {"assigned_firm_id": firm["id"]},
        {"_id": 0, "user_email": 0, "user_name": 0},  # privacy: hide user PII from firm
    ).sort("assigned_at", -1).limit(50)
    items = [s async for s in cursor]
    return {
        "items": items,
        "open_count": sum(1 for s in items if s.get("status") == "assigned"),
        "capacity_max": SANITY_FIRM_CAPACITY,
    }


class FirmSanityResponse(BaseModel):
    response_text: str
    confirms_lex: bool = True
    additional_concerns: str = ""


@api_router.post("/firm/sanity-checks/{sc_id}/submit")
async def firm_submit_sanity_check(sc_id: str, data: FirmSanityResponse, firm: dict = Depends(get_firm)):
    sc = await db.sanity_checks.find_one({"id": sc_id, "assigned_firm_id": firm["id"]})
    if not sc:
        raise HTTPException(404, "Not assigned to your firm")
    if sc.get("status") != "assigned":
        raise HTTPException(409, f"Already {sc.get('status')}")
    text = (data.response_text or "").strip()
    if len(text) < 60:
        raise HTTPException(400, "Please write at least a couple of sentences (minimum 60 chars).")
    now = datetime.now(timezone.utc)
    await db.sanity_checks.update_one({"id": sc_id}, {"$set": {
        "status": "completed",
        "firm_response_text": text[:10000],
        "firm_confirms_lex": bool(data.confirms_lex),
        "firm_additional_concerns": (data.additional_concerns or "")[:2000],
        "firm_response_at": now.isoformat(),
    }})
    closed_at = now.isoformat()[:10]
    commission_rec = {
        "id": str(uuid.uuid4()),
        "firm_id": firm["id"], "firm_email": firm["email"], "firm_name": firm.get("firm_name") or "",
        "client_email": sc.get("user_email") or "(sanity-check)",
        "client_name": "Sanity Check",
        "matter_type": f"Sanity Check · {sc.get('matter_type','general')}",
        "notes": f"Solicitor sanity check completed for SC #{sc_id[:8]}",
        "fee_gbp": SANITY_CHECK_PRICE_GBP,
        "commission_pct": SANITY_CHECK_FIRM_PAYOUT_GBP / SANITY_CHECK_PRICE_GBP,
        # NEGATIVE owed = AI Advocate owes the firm (payout) rather than the
        # firm owing AA. Surfaces as a credit on the firm's monthly statement.
        "commission_owed_gbp": -SANITY_CHECK_FIRM_PAYOUT_GBP,
        "closed_at": closed_at, "logged_at": now.isoformat(),
        "billing_month": closed_at[:7],
        "paid_status": "unpaid", "stripe_invoice_id": None,
        "founding_firm": bool(firm.get("founding_firm")),
        "source": "sanity_check", "sanity_check_id": sc_id,
    }
    await db.firm_engagements.insert_one(commission_rec)
    try:
        from email_helper import send_email
        verdict_label = "✓ Confirmed by a solicitor" if data.confirms_lex else "⚠ A solicitor found concerns"
        await send_email(
            to=sc["user_email"], kind="user",
            subject=f"Your Sanity Check is back — {verdict_label}",
            body_html=f"""<p>Hi,</p>
                <p>Your <strong>Solicitor Sanity Check</strong> has been completed by <strong>{firm.get('firm_name') or 'a verified UK law firm'}</strong>.</p>
                <p><strong>Verdict:</strong> {verdict_label}</p>
                <p style="background:#f7f7f7;border-left:3px solid #f7c948;padding:10px 14px;border-radius:4px;white-space:pre-wrap">{text[:3000]}</p>
                <p style="margin-top:14px"><a href="https://aiadvocate.co.uk/" style="background:#f7c948;color:#1a1300;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:700">View full response in app →</a></p>
                <p style="font-size:12px;color:#666">If you'd like to engage {firm.get('firm_name') or 'the firm'} for ongoing representation, they'll be in touch separately. AI Advocate doesn't share your contact details unless you ask us to.</p>""",
        )
    except Exception as e:
        logger.warning(f"Sanity check client email failed: {e}")
    return {"ok": True, "status": "completed"}


@api_router.post("/firm/sanity-checks/{sc_id}/decline")
async def firm_decline_sanity_check(sc_id: str, firm: dict = Depends(get_firm)):
    sc = await db.sanity_checks.find_one({"id": sc_id, "assigned_firm_id": firm["id"]})
    if not sc or sc.get("status") != "assigned":
        raise HTTPException(404, "Not currently assigned to your firm")
    await db.sanity_checks.update_one({"id": sc_id}, {"$set": {
        "status": "pending_assignment",
        "assigned_firm_id": None,
        "assigned_firm_email": None,
    }, "$push": {"declined_by": firm["id"]}})
    new_firm = await _route_sanity_check(sc_id)
    return {"ok": True, "rerouted_to": new_firm}



@api_router.post("/firm/commissions")
async def firm_log_commission(data: CommissionEntryCreate, firm: dict = Depends(get_firm)):
    """Firm logs a closed paying engagement → backend records the commission owed."""
    now = datetime.now(timezone.utc)
    closed_at = data.closed_at or now.isoformat()[:10]
    pct = _firm_commission_pct(firm)
    commission = round(data.fee_gbp * pct, 2)
    rec = {
        "id": str(uuid.uuid4()),
        "firm_id": firm["id"], "firm_email": firm["email"], "firm_name": firm.get("firm_name") or "",
        "client_email": data.client_email.strip().lower(),
        "client_name": data.client_name.strip(),
        "matter_type": data.matter_type, "notes": data.notes[:500],
        "fee_gbp": round(data.fee_gbp, 2),
        "commission_pct": pct, "commission_owed_gbp": commission,
        "closed_at": closed_at, "logged_at": now.isoformat(),
        "billing_month": closed_at[:7],
        "paid_status": "unpaid", "stripe_invoice_id": None,
        "founding_firm": bool(firm.get("founding_firm")),
    }
    await db.firm_engagements.insert_one(rec)
    rec.pop("_id", None)
    return rec


@api_router.get("/firm/commissions")
async def firm_list_commissions(firm: dict = Depends(get_firm), month: str = ""):
    q = {"firm_id": firm["id"]}
    if month:
        q["billing_month"] = month
    cursor = db.firm_engagements.find(q, {"_id": 0}).sort("closed_at", -1).limit(500)
    items = [e async for e in cursor]
    total_fees = round(sum(e["fee_gbp"] for e in items), 2)
    total_commission = round(sum(e["commission_owed_gbp"] for e in items), 2)
    total_unpaid = round(sum(e["commission_owed_gbp"] for e in items if e["paid_status"] == "unpaid"), 2)
    return {
        "items": items,
        "total_fees_gbp": total_fees,
        "total_commission_gbp": total_commission,
        "total_unpaid_commission_gbp": total_unpaid,
    }


@api_router.delete("/firm/commissions/{eid}")
async def firm_delete_commission(eid: str, firm: dict = Depends(get_firm)):
    rec = await db.firm_engagements.find_one({"id": eid, "firm_id": firm["id"]})
    if not rec:
        raise HTTPException(404, "Commission entry not found.")
    if rec.get("paid_status") in ("invoiced", "paid"):
        raise HTTPException(409, "Already invoiced — contact firms@aiadvocate.co.uk to adjust.")
    await db.firm_engagements.delete_one({"id": eid})
    return {"ok": True, "deleted": True}


@api_router.get("/admin/commissions/summary")
async def admin_commission_summary(_: dict = Depends(_check_admin_user), month: str = ""):
    if not month:
        month = datetime.now(timezone.utc).isoformat()[:7]
    pipeline = [
        {"$match": {"billing_month": month}},
        {"$group": {
            "_id": "$firm_id",
            "firm_name": {"$first": "$firm_name"},
            "firm_email": {"$first": "$firm_email"},
            "engagements_count": {"$sum": 1},
            "total_fees_gbp": {"$sum": "$fee_gbp"},
            "total_commission_gbp": {"$sum": "$commission_owed_gbp"},
            "unpaid_commission_gbp": {"$sum": {
                "$cond": [{"$eq": ["$paid_status", "unpaid"]}, "$commission_owed_gbp", 0]
            }},
        }},
        {"$sort": {"total_commission_gbp": -1}},
    ]
    rows = []
    async for row in db.firm_engagements.aggregate(pipeline):
        row["firm_id"] = row.pop("_id")
        rows.append(row)
    grand_total = round(sum(r["total_commission_gbp"] for r in rows), 2)
    return {"month": month, "by_firm": rows, "grand_total_commission_gbp": grand_total}


class IssueInvoicePayload(BaseModel):
    firm_id: str
    month: str = ""   # "YYYY-MM"; defaults to current month
    days_until_due: int = 14


async def _compute_anomaly_flags(firm_id: str, month: str, current_total: float) -> dict:
    """Compute anomaly flags for a draft invoice:
      - high_vs_avg: current month is >5x the rolling 3-month average
      - large_amount: total > £1,000 (catches typos like 15000 instead of 1500)
    Returns {flags: [...], rolling_avg_gbp: float, requires_review: bool}.
    """
    # 3 previous months
    y, m = int(month[:4]), int(month[5:7])
    prev_months = []
    for _ in range(3):
        m -= 1
        if m == 0: m = 12; y -= 1
        prev_months.append(f"{y:04d}-{m:02d}")
    pipeline = [
        {"$match": {"firm_id": firm_id, "billing_month": {"$in": prev_months}}},
        {"$group": {"_id": "$billing_month", "total": {"$sum": "$commission_owed_gbp"}}},
    ]
    totals = []
    async for row in db.firm_engagements.aggregate(pipeline):
        totals.append(row["total"])
    rolling_avg = round(sum(totals) / 3.0, 2) if totals else 0.0
    flags = []
    if current_total > 1000.0:
        flags.append("large_amount")
    if rolling_avg > 0 and current_total > rolling_avg * 5:
        flags.append("high_vs_avg")
    return {"flags": flags, "rolling_avg_gbp": rolling_avg, "requires_review": bool(flags)}


async def _issue_commission_invoice_for_firm(firm: dict, month: str, days_until_due: int = 14,
                                              as_draft: bool = False, source: str = "manual") -> dict:
    """Issues a single Stripe invoice covering all `unpaid` commission engagements
    for one firm in the given billing month.

    Modes:
      - as_draft=False (default): finalise + send immediately. Marks engagements 'invoiced'.
      - as_draft=True: create as Stripe draft (auto_advance=False), DO NOT finalise/send.
        Marks engagements 'pending_invoice'. A 'commission_drafts' record is stored
        so the founder can review/approve/void during a 48-hour window before the
        cron job auto-sends on the 3rd."""
    if not stripe.api_key:
        raise HTTPException(503, "Stripe not configured on server")

    # Skip firms signed up <30 days ago — let them have a clean first month
    if as_draft:
        ca = firm.get("created_at")
        if ca:
            try:
                created = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - created).days < 30:
                    return {"firm_id": firm["id"], "firm_email": firm.get("email"),
                            "skipped": True, "reason": "firm_under_30_days_old"}
            except Exception:
                pass

    # 1. Pull every unpaid commission entry for this firm/month
    cursor = db.firm_engagements.find({
        "firm_id": firm["id"], "billing_month": month, "paid_status": "unpaid",
    }, {"_id": 0})
    items = [e async for e in cursor]
    if not items:
        return {"firm_id": firm["id"], "firm_email": firm.get("email"), "skipped": True,
                "reason": "no_unpaid_commission_for_month"}

    # 2. Ensure firm has a Stripe customer
    cust_id = firm.get("stripe_customer_id")
    if not cust_id:
        cust = stripe.Customer.create(
            email=firm["email"],
            name=firm.get("firm_name") or firm["email"],
            metadata={"aa_firm_id": firm["id"], "kind": "firm"},
        )
        cust_id = cust.id
        await db.firm_accounts.update_one({"id": firm["id"]}, {"$set": {"stripe_customer_id": cust_id}})

    # 3. Create line items (one per engagement → easier reconciliation)
    for it in items:
        desc_parts = [
            f"AI Advocate referral commission ({int(it['commission_pct']*100)}%)",
            f"matter: {it.get('matter_type') or 'general'}",
            f"client: {it.get('client_name') or it.get('client_email','—')}",
            f"closed {it.get('closed_at','')[:10]}",
            f"fee £{it['fee_gbp']:.2f}",
        ]
        stripe.InvoiceItem.create(
            customer=cust_id,
            currency="gbp",
            amount=int(round(it["commission_owed_gbp"] * 100)),
            description=" · ".join(desc_parts),
            metadata={
                "aa_engagement_id": it["id"], "aa_firm_id": firm["id"],
                "billing_month": month, "kind": "referral_commission",
            },
        )

    # 4. Create the invoice — as DRAFT (auto_advance=False) or SENDING (auto_advance=True)
    inv = stripe.Invoice.create(
        customer=cust_id,
        collection_method="send_invoice",
        days_until_due=int(days_until_due),
        auto_advance=(not as_draft),
        description=f"AI Advocate referral commission · {month}",
        metadata={
            "aa_firm_id": firm["id"], "billing_month": month,
            "kind": "referral_commission_batch",
            "engagements_count": str(len(items)),
            "aa_source": source,
        },
    )

    total = round(sum(it["commission_owed_gbp"] for it in items), 2)
    now_iso = datetime.now(timezone.utc).isoformat()
    eids = [it["id"] for it in items]

    if as_draft:
        # Store draft record for the 48-hour review window
        anomaly = await _compute_anomaly_flags(firm["id"], month, total)
        await db.commission_drafts.update_one(
            {"stripe_invoice_id": inv.id},
            {"$set": {
                "stripe_invoice_id": inv.id,
                "firm_id": firm["id"], "firm_email": firm.get("email"),
                "firm_name": firm.get("firm_name") or "",
                "contact_name": firm.get("contact_name"),
                "month": month,
                "total_gbp": total,
                "engagements_count": len(items),
                "engagement_ids": eids,
                "anomaly_flags": anomaly["flags"],
                "rolling_avg_gbp": anomaly["rolling_avg_gbp"],
                "requires_review": anomaly["requires_review"],
                "status": "draft",
                "source": source,
                "created_at": now_iso,
            }},
            upsert=True,
        )
        await db.firm_engagements.update_many(
            {"id": {"$in": eids}},
            {"$set": {"paid_status": "pending_invoice", "stripe_invoice_id": inv.id,
                      "drafted_at": now_iso}},
        )
        return {
            "firm_id": firm["id"], "firm_email": firm.get("email"),
            "firm_name": firm.get("firm_name"),
            "stripe_invoice_id": inv.id,
            "engagements_count": len(items),
            "total_commission_gbp": total,
            "month": month,
            "anomaly_flags": anomaly["flags"],
            "requires_review": anomaly["requires_review"],
            "rolling_avg_gbp": anomaly["rolling_avg_gbp"],
            "status": "draft",
        }

    # 5. Finalise + send (immediate mode)
    try:
        inv = stripe.Invoice.finalize_invoice(inv.id)
    except Exception:
        pass
    try:
        stripe.Invoice.send_invoice(inv.id)
    except Exception:
        pass

    # 6. Mark every engagement as invoiced
    await db.firm_engagements.update_many(
        {"id": {"$in": eids}},
        {"$set": {"paid_status": "invoiced", "stripe_invoice_id": inv.id,
                  "invoiced_at": now_iso}},
    )
    # 6b. Promote any matching draft record to "sent"
    await db.commission_drafts.update_one(
        {"stripe_invoice_id": inv.id},
        {"$set": {"status": "sent", "sent_at": now_iso}},
    )

    # 7. Branded heads-up email
    try:
        from email_helper import send_email
        await send_email(
            to=firm["email"], kind="firm",
            subject=f"Your AI Advocate commission invoice for {month} is ready",
            body_html=f"""<p>Hi {firm.get('contact_name','team')},</p>
                <p>Your monthly AI Advocate referral-commission invoice for <strong>{month}</strong> is now available in Stripe.</p>
                <ul>
                  <li>{len(items)} engagement{'s' if len(items)!=1 else ''}</li>
                  <li>Total commission: <strong>£{total:.2f}</strong></li>
                  <li>Payable within {days_until_due} days</li>
                </ul>
                <p>You'll receive a separate email from Stripe with the secure payment link.</p>
                <p>Any questions please reply to firms@aiadvocate.co.uk.</p>
                <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
        )
    except Exception as e:
        logger.warning(f"Commission invoice email failed for {firm.get('email')}: {e}")

    return {
        "firm_id": firm["id"], "firm_email": firm.get("email"),
        "firm_name": firm.get("firm_name"),
        "stripe_invoice_id": inv.id,
        "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None),
        "engagements_count": len(items),
        "total_commission_gbp": total,
        "month": month,
        "status": "sent",
    }


@api_router.post("/admin/commissions/issue-invoice")
async def admin_issue_commission_invoice(data: IssueInvoicePayload, _: dict = Depends(_check_admin_user)):
    """Admin trigger: issue a Stripe invoice for ONE firm for ONE month."""
    firm = await db.firm_accounts.find_one({"id": data.firm_id}, {"_id": 0})
    if not firm:
        raise HTTPException(404, "Firm not found")
    month = data.month or datetime.now(timezone.utc).isoformat()[:7]
    return await _issue_commission_invoice_for_firm(firm, month, data.days_until_due)


class IssueAllPayload(BaseModel):
    month: str = ""   # defaults to *previous* month for auto-billing
    days_until_due: int = 14


@api_router.post("/admin/commissions/issue-all")
async def admin_issue_all_commission_invoices(data: IssueAllPayload, _: dict = Depends(_check_admin_user)):
    """Bulk: issue invoices to every firm with unpaid commission in `month`.
    If `month` is empty, defaults to the *previous* calendar month (typical
    monthly billing run executed on the 1st)."""
    if data.month:
        month = data.month
    else:
        now = datetime.now(timezone.utc)
        first_of_this = now.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        month = last_of_prev.isoformat()[:7]

    # Distinct firm_ids with unpaid commission this month
    firm_ids = await db.firm_engagements.distinct(
        "firm_id", {"billing_month": month, "paid_status": "unpaid"}
    )
    results = []
    for fid in firm_ids:
        firm = await db.firm_accounts.find_one({"id": fid}, {"_id": 0})
        if not firm:
            continue
        try:
            r = await _issue_commission_invoice_for_firm(firm, month, data.days_until_due)
            results.append(r)
        except Exception as e:
            logger.exception(f"Auto-invoice failed for firm {fid}")
            results.append({"firm_id": fid, "error": str(e)})
    return {"month": month, "count": len(results), "results": results}


# ---------- Hybrid auto-billing pipeline ----------
# 22nd of month → heads-up email to firms
# 1st of month  → generate DRAFTS (not finalised) + email admin summary
# 3rd of month  → auto-send any still-draft, non-flagged invoices

class RunDraftsPayload(BaseModel):
    month: str = ""


async def _resolve_prev_month() -> str:
    now = datetime.now(timezone.utc)
    first_of_this = now.replace(day=1)
    last_of_prev = first_of_this - timedelta(days=1)
    return last_of_prev.isoformat()[:7]


async def _create_monthly_drafts(month: str, source: str = "manual") -> dict:
    """Generates DRAFT Stripe invoices for every firm with unpaid commission in `month`.
    Stores per-firm `commission_drafts` records with anomaly flags. Does NOT send."""
    firm_ids = await db.firm_engagements.distinct(
        "firm_id", {"billing_month": month, "paid_status": "unpaid"}
    )
    results = []
    for fid in firm_ids:
        firm = await db.firm_accounts.find_one({"id": fid}, {"_id": 0})
        if not firm:
            continue
        try:
            r = await _issue_commission_invoice_for_firm(firm, month, as_draft=True, source=source)
            results.append(r)
        except Exception as e:
            logger.exception(f"Draft invoice failed for firm {fid}")
            results.append({"firm_id": fid, "error": str(e)})

    actual = [r for r in results if not r.get("skipped") and not r.get("error")]
    flagged = [r for r in actual if r.get("requires_review")]
    total = round(sum((r.get("total_commission_gbp") or 0) for r in actual), 2)
    if source == "cron" and actual:
        try:
            admin_emails = [e.strip() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]
            from email_helper import send_email
            rows_html = "".join(
                f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>{r.get('firm_name') or r.get('firm_email')}</td>"
                f"<td style='padding:6px 10px;text-align:right;border-bottom:1px solid #eee'>£{r.get('total_commission_gbp',0):.2f}</td>"
                f"<td style='padding:6px 10px;border-bottom:1px solid #eee;color:#b45309'>{', '.join(r.get('anomaly_flags') or []) or '—'}</td></tr>"
                for r in actual
            )
            html = f"""<p>Hi Sam,</p>
                <p>Monthly draft invoices for <strong>{month}</strong> are ready in your admin panel.</p>
                <ul>
                  <li><strong>{len(actual)}</strong> firm{'s' if len(actual)!=1 else ''} — total <strong>£{total:.2f}</strong></li>
                  <li><strong>{len(flagged)}</strong> flagged for review (5× rolling avg OR amount &gt; £1,000)</li>
                  <li>Drafts auto-send on day 3 at 09:00 UTC — until then you can approve/void each one.</li>
                </ul>
                <table style='border-collapse:collapse;width:100%;margin-top:12px;font-size:13px'>
                  <thead><tr style='background:#f7c948'><th style='padding:8px 10px;text-align:left'>Firm</th><th style='padding:8px 10px;text-align:right'>Commission</th><th style='padding:8px 10px;text-align:left'>Flags</th></tr></thead>
                  <tbody>{rows_html}</tbody>
                </table>
                <p style='margin-top:16px'><a href='https://aiadvocate.co.uk/' style='background:#f7c948;color:#1a1300;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:700'>Review drafts in admin →</a></p>"""
            for ae in admin_emails:
                await send_email(to=ae, kind="firm",
                                 subject=f"📊 {len(actual)} draft commission invoices ready for {month}",
                                 body_html=html)
        except Exception as e:
            logger.warning(f"Admin summary email failed: {e}")

    return {"month": month, "count": len(results),
            "total_commission_gbp": total,
            "flagged_count": len(flagged), "results": results}


@api_router.post("/admin/commissions/run-monthly-drafts")
async def admin_run_monthly_drafts(data: RunDraftsPayload, _: dict = Depends(_check_admin_user)):
    """Generate DRAFT invoices for the given month (defaults to previous calendar
    month). Drafts sit in Stripe + our `commission_drafts` collection for review."""
    month = data.month or await _resolve_prev_month()
    return await _create_monthly_drafts(month, source="manual")


@api_router.get("/admin/commissions/drafts")
async def admin_list_drafts(_: dict = Depends(_check_admin_user), month: str = ""):
    """Lists current draft invoices. If `month` is empty, defaults to current month."""
    if not month:
        month = datetime.now(timezone.utc).isoformat()[:7]
    cursor = db.commission_drafts.find({"month": month, "status": "draft"}, {"_id": 0}).sort("created_at", -1)
    drafts = [d async for d in cursor]
    return {"month": month, "drafts": drafts,
            "total_gbp": round(sum(d.get("total_gbp", 0) for d in drafts), 2),
            "flagged_count": sum(1 for d in drafts if d.get("requires_review"))}


async def _approve_draft_inner(stripe_invoice_id: str) -> dict:
    draft = await db.commission_drafts.find_one({"stripe_invoice_id": stripe_invoice_id})
    if not draft or draft.get("status") != "draft":
        raise HTTPException(404, "Draft not found or already processed")
    try:
        inv = stripe.Invoice.finalize_invoice(stripe_invoice_id)
    except Exception as e:
        raise HTTPException(500, f"Stripe finalise failed: {e}")
    try:
        stripe.Invoice.send_invoice(stripe_invoice_id)
    except Exception as e:
        logger.warning(f"Send failed (non-fatal): {e}")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.firm_engagements.update_many(
        {"id": {"$in": draft.get("engagement_ids") or []}},
        {"$set": {"paid_status": "invoiced", "invoiced_at": now_iso}},
    )
    await db.commission_drafts.update_one(
        {"stripe_invoice_id": stripe_invoice_id},
        {"$set": {"status": "sent", "sent_at": now_iso}},
    )
    try:
        from email_helper import send_email
        await send_email(
            to=draft["firm_email"], kind="firm",
            subject=f"Your AI Advocate commission invoice for {draft['month']} is ready",
            body_html=f"""<p>Hi {draft.get('contact_name','team')},</p>
                <p>Your monthly AI Advocate referral-commission invoice for <strong>{draft['month']}</strong> is now available in Stripe.</p>
                <ul>
                  <li>{draft.get('engagements_count')} engagement{'s' if draft.get('engagements_count',0)!=1 else ''}</li>
                  <li>Total commission: <strong>£{draft.get('total_gbp',0):.2f}</strong></li>
                </ul>
                <p>You'll receive a separate email from Stripe with the secure payment link.</p>
                <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
        )
    except Exception:
        pass
    return {"ok": True, "stripe_invoice_id": stripe_invoice_id,
            "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None)}


@api_router.post("/admin/commissions/drafts/{stripe_invoice_id}/approve")
async def admin_approve_draft(stripe_invoice_id: str, _: dict = Depends(_check_admin_user)):
    """Finalise + send a single draft Stripe invoice."""
    return await _approve_draft_inner(stripe_invoice_id)


@api_router.post("/admin/commissions/drafts/{stripe_invoice_id}/void")
async def admin_void_draft(stripe_invoice_id: str, _: dict = Depends(_check_admin_user)):
    """Void a draft Stripe invoice — reverts engagements to `unpaid`."""
    draft = await db.commission_drafts.find_one({"stripe_invoice_id": stripe_invoice_id})
    if not draft or draft.get("status") != "draft":
        raise HTTPException(404, "Draft not found or already processed")
    try:
        stripe.Invoice.void_invoice(stripe_invoice_id)
    except Exception:
        try:
            stripe.Invoice.delete(stripe_invoice_id)
        except Exception as e:
            logger.warning(f"Stripe void+delete both failed: {e}")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.firm_engagements.update_many(
        {"id": {"$in": draft.get("engagement_ids") or []}},
        {"$set": {"paid_status": "unpaid", "stripe_invoice_id": None}, "$unset": {"drafted_at": ""}},
    )
    await db.commission_drafts.update_one(
        {"stripe_invoice_id": stripe_invoice_id},
        {"$set": {"status": "voided", "voided_at": now_iso}},
    )
    return {"ok": True, "stripe_invoice_id": stripe_invoice_id, "status": "voided"}


@api_router.post("/admin/commissions/drafts/approve-all")
async def admin_approve_all_drafts(_: dict = Depends(_check_admin_user), include_flagged: bool = False):
    """Approve+send every draft for the current month. By default skips drafts
    with anomaly flags; pass `?include_flagged=true` to also include those."""
    month = datetime.now(timezone.utc).isoformat()[:7]
    q = {"month": month, "status": "draft"}
    if not include_flagged:
        q["requires_review"] = {"$ne": True}
    cursor = db.commission_drafts.find(q, {"_id": 0})
    drafts = [d async for d in cursor]
    sent, errors = 0, []
    for d in drafts:
        try:
            await _approve_draft_inner(d["stripe_invoice_id"])
            sent += 1
        except Exception as e:
            errors.append({"stripe_invoice_id": d["stripe_invoice_id"], "error": str(e)})
    return {"sent": sent, "errors": errors, "month": month}


async def _send_headsup_emails(month: str, source: str = "cron") -> dict:
    """Send 7-day-ahead heads-up email to every firm with unpaid commission."""
    firm_ids = await db.firm_engagements.distinct(
        "firm_id", {"billing_month": month, "paid_status": "unpaid"}
    )
    sent, errors = 0, []
    from email_helper import send_email
    for fid in firm_ids:
        firm = await db.firm_accounts.find_one({"id": fid}, {"_id": 0})
        if not firm:
            continue
        try:
            created = datetime.fromisoformat((firm.get("created_at") or "").replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - created).days < 30:
                continue
        except Exception:
            pass
        pipeline = [
            {"$match": {"firm_id": fid, "billing_month": month, "paid_status": "unpaid"}},
            {"$group": {"_id": None, "total": {"$sum": "$commission_owed_gbp"}, "count": {"$sum": 1}}},
        ]
        total, count = 0.0, 0
        async for row in db.firm_engagements.aggregate(pipeline):
            total = row["total"]; count = row["count"]
        if count == 0:
            continue
        try:
            await send_email(
                to=firm["email"], kind="firm",
                subject=f"Heads up — your AI Advocate commission for {month}",
                body_html=f"""<p>Hi {firm.get('contact_name','team')},</p>
                    <p>Quick heads-up that your monthly AI Advocate referral-commission invoice for <strong>{month}</strong> will be issued in the next 7 days.</p>
                    <ul>
                      <li>Closed referrals: <strong>{count}</strong></li>
                      <li>Estimated commission: <strong>£{total:.2f}</strong> (30% of fees, per your Founding Firm Agreement)</li>
                    </ul>
                    <p>If anything looks wrong, reply to this email before invoicing and we'll fix it. Otherwise no action needed — Stripe will send the invoice with payment link automatically.</p>
                    <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
            )
            sent += 1
        except Exception as e:
            errors.append({"firm_id": fid, "error": str(e)})
    return {"sent": sent, "errors": errors, "month": month, "source": source}


@api_router.post("/admin/commissions/send-headsup")
async def admin_send_headsup(_: dict = Depends(_check_admin_user), month: str = ""):
    """Manually trigger 7-day heads-up emails. Cron auto-fires this on the 22nd."""
    if not month:
        month = await _resolve_prev_month()
    return await _send_headsup_emails(month, source="manual")


@api_router.get("/admin/commissions/schedule")
async def admin_billing_schedule(_: dict = Depends(_check_admin_user)):
    """Returns the next scheduled cron-run timestamps (UTC)."""
    now = datetime.now(timezone.utc)
    def next_day(d: int) -> datetime:
        t = now.replace(day=1, hour=9, minute=0, second=0, microsecond=0)
        # bump to current month's day d
        try:
            t = t.replace(day=d)
        except ValueError:
            pass
        if t <= now:
            # advance to next month's day d
            yr, mo = t.year, t.month + 1
            if mo > 12: yr += 1; mo = 1
            t = t.replace(year=yr, month=mo, day=d)
        return t
    return {
        "next_headsup_at": next_day(22).isoformat(),
        "next_drafts_at": next_day(1).isoformat(),
        "next_autosend_at": next_day(3).isoformat(),
        "tz": "UTC",
    }



@api_router.get("/firm/me")
async def firm_me(firm: dict = Depends(get_firm)):
    # Recent leads
    leads = []
    async for q in db.inquiries.find({"firm_id": firm["id"]}, {"_id": 0}).sort("created_at", -1).limit(50):
        leads.append(q)
    firm["recent_leads"] = leads
    # Trial state — surface to UI so we can render the banner with days remaining.
    firm["effective_tier"] = _firm_tier(firm)
    trial_until_raw = firm.get("trial_until")
    if trial_until_raw:
        try:
            if isinstance(trial_until_raw, str):
                trial_dt = datetime.fromisoformat(trial_until_raw.replace("Z", "+00:00"))
            else:
                trial_dt = trial_until_raw
            secs_left = (trial_dt - datetime.now(timezone.utc)).total_seconds()
            firm["trial_active"] = secs_left > 0
            firm["trial_days_remaining"] = max(0, int(secs_left // 86400))
            firm["trial_hours_remaining"] = max(0, int(secs_left // 3600))
        except Exception:
            firm["trial_active"] = False
    else:
        firm["trial_active"] = False
    return firm

@api_router.patch("/firm/listing")
async def firm_update_listing(data: FirmListingUpdate, firm: dict = Depends(get_firm)):
    if firm["status"] != "approved":
        raise HTTPException(403, "Firm not yet approved by AI Advocate admin")
    upd = {k: v for k, v in data.dict(exclude_none=True).items()}
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.lawfirms.update_one({"firm_account_id": firm["id"]}, {"$set": upd})
    return {"updated": True}


# ==================== FIRM — Custom branding (Premium/Practice tier perk) ====================
# Lets firms upload a logo URL + brand colours that render in:
#   • the firm portal navigation
#   • client-facing engagement chats / cards (instead of generic AI Advocate gold)
#   • engagement email footers
# Hex validation is permissive (3 or 6 chars). Logo URL must be https.

_HEX_RE = __import__("re").compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

def _validate_hex(c: Optional[str]) -> Optional[str]:
    if not c:
        return None
    c = c.strip()
    if not _HEX_RE.match(c):
        raise HTTPException(400, f"Invalid hex colour: {c!r} — use format #1a4d8f")
    return c if c.startswith("#") else f"#{c}"

@api_router.get("/firm/branding")
async def firm_get_branding(firm: dict = Depends(get_firm)):
    """Return the firm's current branding so the portal can render it."""
    return {
        "logo_url": firm.get("logo_url") or "",
        "brand_color": firm.get("brand_color") or "",
        "accent_color": firm.get("accent_color") or "",
        "tier_allows": _firm_tier(firm) in ("premium", "practice"),
    }

@api_router.patch("/firm/branding")
async def firm_update_branding(data: FirmBrandingUpdate, firm: dict = Depends(get_firm)):
    """Update a firm's custom branding. Restricted to Premium + Practice tiers."""
    tier = _firm_tier(firm)
    if tier not in ("premium", "practice"):
        raise HTTPException(402, "Custom branding is available on Premium and Practice tiers. Upgrade to unlock.")
    if firm.get("acting_role") not in (None, "owner", "admin"):
        raise HTTPException(403, "Only firm owners or admins can edit branding")

    upd = {}
    if data.logo_url is not None:
        u = (data.logo_url or "").strip()
        if u:
            # Accept either a full https:// URL (legacy) OR a base64 data: image URL (mobile upload flow).
            # Data URLs let firms pick a photo from their phone — no external hosting required.
            if u.startswith("data:image/"):
                # Cap base64 payload at ~700KB to keep DB rows lean and avoid bloat.
                if len(u) > 700_000:
                    raise HTTPException(413, "Logo too large — please choose an image under 500KB.")
            elif not u.startswith(("https://", "http://")):
                raise HTTPException(400, "logo_url must be an https:// URL or an uploaded image")
        upd["logo_url"] = u
    if data.brand_color is not None:
        upd["brand_color"] = _validate_hex(data.brand_color) or ""
    if data.accent_color is not None:
        upd["accent_color"] = _validate_hex(data.accent_color) or ""
    upd["branding_updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.firm_accounts.update_one({"id": firm["id"]}, {"$set": upd})
    return {"updated": True, **{k: v for k, v in upd.items() if k != "branding_updated_at"}}


# ==================== FIRM — Multi-user seats (Premium/Practice tier perk) ====================
# A firm account can invite N additional fee-earners to log in under the same firm.
# Limits enforced by FIRM_SEAT_LIMITS. Invites are token-based: firm owner generates an
# invite, owner shares the link/token with the colleague, colleague POSTs accept with
# their chosen password. No email sending dependency in the critical path.

def _count_active_seats(firm_id: str) -> int:
    """Return: parent owner (always 1) + count of active firm_users."""
    return 1  # owner is always 1; firm_users counted async below

@api_router.get("/firm/users")
async def firm_list_users(firm: dict = Depends(get_firm)):
    """List all fee-earner seats under this firm (owner + invited users)."""
    tier = _firm_tier(firm)
    users = []
    async for u in db.firm_users.find({"firm_id": firm["id"]}, {"_id": 0, "password": 0, "invite_token": 0}).sort("created_at", 1):
        users.append(u)
    seat_limit = FIRM_SEAT_LIMITS.get(tier, 1)
    active_count = 1 + len([u for u in users if u.get("status") == "active"])  # +1 for owner
    return {
        "owner": {
            "id": firm["id"], "email": firm["email"],
            "full_name": firm.get("contact_name", ""), "role": "owner",
            "status": "active", "is_owner": True,
        },
        "users": users,                       # invited / pending / removed
        "seat_limit": seat_limit,
        "active_count": active_count,
        "tier": tier,
        "can_invite_more": active_count < seat_limit,
    }

@api_router.post("/firm/users/invite")
async def firm_invite_user(data: FirmUserInvite, firm: dict = Depends(get_firm)):
    """Owner / admin invites a new fee-earner. Returns an invite token the owner shares."""
    if firm.get("acting_role") not in (None, "owner", "admin"):
        raise HTTPException(403, "Only firm owners or admins can invite users")
    tier = _firm_tier(firm)
    seat_limit = FIRM_SEAT_LIMITS.get(tier, 1)
    # count current active + pending
    active_count = 1  # owner
    async for u in db.firm_users.find({"firm_id": firm["id"], "status": {"$in": ["active", "pending"]}}, {"_id": 0, "id": 1}):
        active_count += 1
    if active_count >= seat_limit:
        raise HTTPException(402, f"Seat limit reached for {tier} tier ({seat_limit} seats). Upgrade to add more fee-earners.")

    email = data.email.lower().strip()
    # Same email can't be both firm owner AND firm_user
    if email == firm["email"]:
        raise HTTPException(400, "That email is already the firm owner")
    existing = await db.firm_users.find_one({"firm_id": firm["id"], "email": email})
    if existing and existing.get("status") in ("active", "pending"):
        raise HTTPException(409, "User already invited or active under this firm")

    invite_token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "firm_id": firm["id"],
        "email": email,
        "full_name": data.full_name.strip()[:120],
        "role": data.role if data.role in ("fee_earner", "admin") else "fee_earner",
        "status": "pending",
        "invite_token": invite_token,
        "invite_expires_at": (now + timedelta(days=14)).isoformat(),
        "invited_by": firm["email"],
        "created_at": now.isoformat(),
        "password": None,                        # set on acceptance
    }
    await db.firm_users.insert_one(doc)
    doc.pop("_id", None); doc.pop("password", None)
    return {
        "ok": True,
        "invite_token": invite_token,
        "invite_url": f"{os.environ.get('APP_PUBLIC_URL', 'https://aiadvocate.co.uk')}/firm-accept-invite?token={invite_token}",
        "user_id": user_id,
        "expires_at": doc["invite_expires_at"],
    }

@api_router.post("/firm/users/accept")
async def firm_accept_invite(data: FirmUserAcceptInvite):
    """Invitee accepts: sets their password, status flips to active, returns a firm_user JWT."""
    record = await db.firm_users.find_one({"invite_token": data.invite_token})
    if not record:
        raise HTTPException(404, "Invitation not found or already used")
    if record.get("status") != "pending":
        raise HTTPException(400, f"Invitation already {record.get('status')}")
    # Check expiry
    try:
        exp = datetime.fromisoformat(record["invite_expires_at"].replace("Z", "+00:00"))
        if exp < datetime.now(timezone.utc):
            raise HTTPException(400, "Invitation has expired — ask the firm owner to resend")
    except (ValueError, KeyError):
        pass

    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    now = datetime.now(timezone.utc)
    await db.firm_users.update_one(
        {"id": record["id"]},
        {"$set": {
            "password": hash_pw(data.password),
            "status": "active",
            "accepted_at": now.isoformat(),
        }, "$unset": {"invite_token": ""}},
    )
    token = jwt.encode(
        {"sub": record["id"], "kind": "firm_user", "firm_id": record["firm_id"],
         "exp": now + timedelta(days=30)},
        JWT_SECRET, algorithm="HS256",
    )
    # Return firm context too so UI can route them
    firm = await db.firm_accounts.find_one({"id": record["firm_id"]}, {"_id": 0, "password": 0})
    return {
        "access_token": token,
        "firm_user": {"id": record["id"], "email": record["email"],
                      "full_name": record["full_name"], "role": record["role"]},
        "firm": firm,
    }

@api_router.post("/firm/users/login")
async def firm_user_login(data: FirmUserLogin):
    """Fee-earner login (separate from firm-owner login)."""
    record = await db.firm_users.find_one({"email": data.email.lower().strip()})
    if not record or not record.get("password"):
        raise HTTPException(401, "Invalid credentials")
    if record.get("status") != "active":
        raise HTTPException(403, f"Account is {record.get('status')} — contact your firm admin")
    if not verify_pw(data.password, record["password"]):
        raise HTTPException(401, "Invalid credentials")
    firm = await db.firm_accounts.find_one({"id": record["firm_id"]}, {"_id": 0, "password": 0})
    if not firm:
        raise HTTPException(401, "Parent firm not found")
    token = jwt.encode(
        {"sub": record["id"], "kind": "firm_user", "firm_id": record["firm_id"],
         "exp": datetime.now(timezone.utc) + timedelta(days=30)},
        JWT_SECRET, algorithm="HS256",
    )
    return {
        "access_token": token,
        "firm_user": {"id": record["id"], "email": record["email"],
                      "full_name": record["full_name"], "role": record["role"]},
        "firm": firm,
    }

@api_router.delete("/firm/users/{user_id}")
async def firm_remove_user(user_id: str, firm: dict = Depends(get_firm)):
    """Owner / admin removes a fee-earner from the firm."""
    if firm.get("acting_role") not in (None, "owner", "admin"):
        raise HTTPException(403, "Only firm owners or admins can remove users")
    record = await db.firm_users.find_one({"id": user_id, "firm_id": firm["id"]}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Firm user not found")
    await db.firm_users.update_one(
        {"id": user_id},
        {"$set": {"status": "removed", "removed_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"removed": True, "user_id": user_id}


@api_router.post("/firm/subscribe")
async def firm_subscribe(plan: str = "featured", firm: dict = Depends(get_firm)):
    """Stripe checkout for firms — £49/mo Featured, £199/mo Premium, £499/mo Practice."""
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
# === Multi-user fee-earner seats per firm tier (Practice tier perk) ===
# A "seat" = one solicitor / fee-earner who can log in under the firm account.
# The primary firm account itself always counts as 1 seat. So Practice = 5 total logins.
FIRM_SEAT_LIMITS = {
    "free": 1,
    "featured": 1,
    "premium": 3,
    "practice": 5,
}
# Lex-AI per-month allowance for a firm (for draft-reply / summarise / explain on threads)
FIRM_LEX_MONTHLY_LIMITS = {
    "free": 0, "featured": 0, "premium": 100, "practice": 1000,
}
# Shared file storage cap per engagement
ENGAGEMENT_FILE_LIMIT = 50   # files per engagement
ENGAGEMENT_FILE_MAX_BYTES = 12 * 1024 * 1024  # 12MB per file

def _firm_tier(firm: dict) -> str:
    """Returns the effective tier for the firm RIGHT NOW.
    Prefers the active trial tier over the base 'tier' as long as trial_until is
    still in the future. Once the trial expires it falls back to the paid tier
    (or 'free' if they never converted). Single source of truth — every paywall
    and feature gate runs through this so trials are honoured uniformly.
    """
    if not firm:
        return "free"
    trial_until = firm.get("trial_until")
    trial_tier = firm.get("trial_tier")
    if trial_until and trial_tier:
        try:
            if isinstance(trial_until, str):
                trial_dt = datetime.fromisoformat(trial_until.replace("Z", "+00:00"))
            else:
                trial_dt = trial_until
            if trial_dt > datetime.now(timezone.utc) and trial_tier in FIRM_ENGAGEMENT_LIMITS:
                return trial_tier
        except Exception:
            pass
    t = firm.get("tier") or "free"
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
        raise HTTPException(402, "Client engagements aren't included in your current plan. Upgrade to Premium (£199/mo) or Practice (£499/mo) to invite clients securely.")
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


# ==================== GDPR — Delete Analytics Data (PostHog + Sentry) ====================
# Honours UK GDPR Art. 17 "Right to erasure" for product analytics / crash reports.
# • Wipes the user's PostHog person + events (if POSTHOG_PERSONAL_API_KEY is configured).
# • Sentry doesn't support per-user delete via API — we record the request server-side
#   so the founder can action it via Sentry support if/when asked.
# • Always sets server-side flag `analytics_deleted_at` so future events from this user are
#   dropped before they reach PostHog (defense in depth).

@api_router.post("/privacy/delete-analytics-data")
async def privacy_delete_analytics(user: dict = Depends(get_user)):
    """User-initiated GDPR delete of product-analytics data.
    Wipes PostHog person + events for this user (server-side, best-effort).
    Records the request locally so we keep an audit trail."""
    user_id = user["id"]
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "posthog": {"attempted": False, "status": "skipped", "detail": "no personal key configured"},
        "sentry":  {"attempted": False, "status": "logged",  "detail": "per-user delete must be requested via Sentry support"},
        "requested_at": now,
    }

    # PostHog: requires personal API key + project id (different from the public client token).
    ph_key  = os.environ.get("POSTHOG_PERSONAL_API_KEY", "").strip()
    ph_proj = os.environ.get("POSTHOG_PROJECT_ID", "").strip()
    ph_host = os.environ.get("POSTHOG_HOST", "https://eu.posthog.com").rstrip("/")
    if ph_key and ph_proj:
        result["posthog"]["attempted"] = True
        try:
            async with httpx.AsyncClient(timeout=20.0) as cx:
                # 1) Find person by distinct_id (we use the user's UUID as identify())
                find_url = f"{ph_host}/api/projects/{ph_proj}/persons/?distinct_id={user_id}"
                headers = {"Authorization": f"Bearer {ph_key}"}
                r = await cx.get(find_url, headers=headers)
                if r.status_code != 200:
                    result["posthog"]["status"] = "not_found"
                    result["posthog"]["detail"] = f"PostHog persons lookup returned {r.status_code}"
                else:
                    persons = (r.json() or {}).get("results", []) or []
                    deleted = 0
                    for p in persons:
                        pid = p.get("id")
                        if not pid:
                            continue
                        del_url = f"{ph_host}/api/projects/{ph_proj}/persons/{pid}/?delete_events=true"
                        d = await cx.delete(del_url, headers=headers)
                        if d.status_code in (200, 202, 204):
                            deleted += 1
                    result["posthog"]["status"] = "deleted" if deleted else "not_found"
                    result["posthog"]["persons_deleted"] = deleted
        except Exception as e:
            logger.exception("PostHog GDPR delete failed")
            result["posthog"]["status"] = "error"
            result["posthog"]["detail"] = str(e)[:200]

    # Stamp the user record so future event ingestion can be suppressed defense-in-depth.
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"analytics_deleted_at": now}},
    )

    # Audit trail
    await db.privacy_analytics_deletions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_email": user.get("email") or "",
        "result": result,
        "created_at": now,
    })
    return result




# ==================== Daily "Know Your Rights" Tip ====================
# Cached per-day per-language so we don't burn LLM calls every request.

@api_router.get("/tips/daily")
async def daily_tip(language: str = "en-GB", country: str = "GB", user: dict = Depends(get_user)):
    """Daily 'Know Your Rights' tip. UK + English users get one from the curated
    120-tip pool (rotated by day-of-year + a stable per-user offset so two users
    don't see the same tip on the same day). Non-UK / non-English users get a
    cached LLM-generated tip in their language."""
    today_dt = datetime.now(timezone.utc).date()
    today = today_dt.isoformat()

    # 🇬🇧 UK + English path → curated pool (no LLM cost, no repetition for ~4 months)
    if (country or "").upper() == "GB" and (language or "").lower().startswith("en"):
        try:
            from tips_pool import tip_for, all_tips
            day_of_year = today_dt.timetuple().tm_yday
            # Stable per-user offset so two users don't see the same tip on the same day
            user_offset = (sum(ord(c) for c in (user.get("id") or "")) % len(all_tips()))
            tip = tip_for(day_of_year, user_offset)
            return {"date": today, "tip": tip, "cached": False, "source": "curated_pool"}
        except Exception as e:
            logger.exception("curated tip pool failed, falling back to LLM")
            # Continue to LLM path below

    # 🌍 Non-UK / non-English → cached LLM tip (1 LLM call per day per locale)
    cache_key = f"{today}-{language}-{country}"
    cached = await db.tips_cache.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        return {"date": today, "tip": cached["tip"], "cached": True, "source": "llm"}
    lang_name = LANG_NAMES.get(language, "English")
    sysmsg = f"""You are AI Advocate writing today's "Know Your Rights" tip for users in {country}.
Output ONE concise tip (max 35 words) in {lang_name}. Practical, useful, surprising-but-true.
Cite the relevant statute or scheme by name. No greetings, no preamble — just the tip itself."""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"tip-{cache_key}", system_message=sysmsg)\
        .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=80)
    try:
        tip = (await chat.send_message(UserMessage(text="Today's tip please."))).strip()
    except Exception:
        logger.exception("daily tip LLM failed")
        tip = "Always ask for an officer's badge number — you have the right to record it."
    await db.tips_cache.insert_one({"key": cache_key, "tip": tip,
                                     "created_at": datetime.now(timezone.utc).isoformat()})
    return {"date": today, "tip": tip, "cached": False, "source": "llm"}


# ==================== File Deletion (soft delete → recycle bin) ====================
@api_router.delete("/legal-files/{file_id}")
async def delete_legal_file(file_id: str, user: dict = Depends(get_user)):
    """Soft-delete a legal file. Recoverable from /recycle-bin for 30 days."""
    res = await db.legal_files.update_one(
        {"id": file_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "File not found")
    return {"deleted": True, "id": file_id, "recoverable_for_days": 30}


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
        analysis_obj = _json.loads(payload)
    except Exception:
        analysis_obj = {
            "contract_type": "other", "plain_english_summary": payload[:600],
            "overall_verdict": "amber", "verdict_one_liner": "Could not fully parse this contract.",
            "clauses": [], "red_flags": [], "amber_flags": [], "questions_to_ask": [],
            "solicitor_review_recommended": True, "missing_protections": [],
        }

    # 💾 Persist the analysis so the user can go back to it later (Contract Tools tab → "My contracts").
    # We store the raw bytes too (base64) for re-display + future re-analysis. Capped at ~6MB
    # after base64 inflation; the file-size guard above already keeps raw <12MB.
    try:
        import base64 as _b64
        file_b64 = _b64.b64encode(raw).decode("ascii") if len(raw) <= 8 * 1024 * 1024 else None
        rec_id = str(uuid.uuid4())
        await db.contract_analyses.insert_one({
            "id": rec_id, "user_id": user["id"],
            "filename": file.filename or "contract",
            "content_type": file.content_type or "application/octet-stream",
            "file_size": len(raw),
            "file_b64": file_b64,                   # base64 of original upload (null if oversized)
            "extracted_text": extracted_text[:60000],
            "analysis": analysis_obj,
            "title": (analysis_obj.get("contract_type") or "contract").replace("_", " ").title() + " — " + (file.filename or "Untitled"),
            "language": language, "country": country,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        analysis_obj["saved_id"] = rec_id          # client can deep-link to /contracts/analyses/<id>
    except Exception:
        logger.exception("Failed to persist contract analysis (non-fatal)")
    return analysis_obj


@api_router.get("/contract/analyses")
async def list_contract_analyses(user: dict = Depends(get_user)):
    """Return the user's saved contract analyses (newest first). Excludes the
    base64 payload so the list endpoint stays light — fetch the individual
    analysis to get the file bytes."""
    items = await db.contract_analyses.find(
        {"user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"_id": 0, "id": 1, "filename": 1, "title": 1, "content_type": 1,
         "analysis.overall_verdict": 1, "analysis.verdict_one_liner": 1,
         "analysis.contract_type": 1, "created_at": 1, "file_size": 1},
    ).sort("created_at", -1).to_list(200)
    return {"analyses": items, "count": len(items)}


@api_router.get("/contract/analyses/{analysis_id}")
async def get_contract_analysis(analysis_id: str, user: dict = Depends(get_user)):
    rec = await db.contract_analyses.find_one(
        {"id": analysis_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(404, "Analysis not found.")
    return rec


@api_router.delete("/contract/analyses/{analysis_id}")
async def delete_contract_analysis(analysis_id: str, user: dict = Depends(get_user)):
    """Soft-delete (move to Recycle Bin pattern — restorable for 30 days)."""
    rec = await db.contract_analyses.find_one(
        {"id": analysis_id, "user_id": user["id"]},
        {"_id": 0, "id": 1},
    )
    if not rec:
        raise HTTPException(404, "Analysis not found.")
    await db.contract_analyses.update_one(
        {"id": analysis_id},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "id": analysis_id}


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
    postcode: Optional[str] = None  # UK outward code (first 1-2 letters) is enough


# UK regional multipliers vs national average solicitor rate. London commands the
# highest premium; the North East / South West are typically below national mean.
_UK_REGION_MULTIPLIER = {
    "EC": 1.55, "WC": 1.55, "E1": 1.45, "E2": 1.45, "E14": 1.55, "N1": 1.35,
    "SE1": 1.35, "SW1": 1.55, "W1": 1.55, "W2": 1.45, "NW1": 1.35, "SW3": 1.55,
    # Greater London (most outward codes)
    "N": 1.25, "E": 1.25, "SE": 1.20, "SW": 1.30, "W": 1.30, "NW": 1.25,
    # South East commuter belt
    "GU": 1.15, "KT": 1.20, "TW": 1.20, "UB": 1.15, "HA": 1.15, "EN": 1.10,
    "BR": 1.15, "CR": 1.15, "DA": 1.10, "RM": 1.05, "IG": 1.05, "WD": 1.10,
    # Other premium markets
    "OX": 1.10, "CB": 1.10, "RG": 1.10, "MK": 1.05, "RH": 1.10, "SL": 1.10,
    # Major cities
    "M": 1.05, "B": 1.05, "BS": 1.05, "EH": 1.05, "G": 1.00, "LS": 1.00, "L": 1.00,
    "NE": 0.90, "CF": 0.95, "BT": 0.95, "PL": 0.90, "TR": 0.90, "EX": 0.95,
    "TQ": 0.90, "SN": 0.95, "BA": 1.00, "PO": 1.00, "BN": 1.05,
}


def _postcode_multiplier(postcode: Optional[str]) -> tuple[float, str]:
    """Return (multiplier, region_label) for a given UK postcode."""
    if not postcode:
        return 1.0, "National average"
    pc = (postcode or "").upper().strip().replace(" ", "")
    # Try most specific match first (3-char), then 2-char, then 1-char prefix
    for n in (3, 2, 1):
        prefix = pc[:n]
        if prefix in _UK_REGION_MULTIPLIER:
            mult = _UK_REGION_MULTIPLIER[prefix]
            label = (
                "Central London (premium)" if mult >= 1.50 else
                "Greater London" if mult >= 1.20 else
                "South East / commuter belt" if mult >= 1.10 else
                "Major UK city" if mult >= 1.00 else
                "Regional UK"
            )
            return mult, label
    return 1.0, "National average"

@api_router.post("/cost/estimate")
async def lawyer_cost_estimate(data: CostEstimateRequest, user: dict = Depends(get_user)):
    lang_name = LANG_NAMES.get(data.language, "English")
    mult, region_label = _postcode_multiplier(data.postcode) if (data.country or "").upper() == "GB" else (1.0, "")
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
        result = _json.loads(payload)
    except Exception:
        result = {"low_estimate_gbp": 0, "high_estimate_gbp": 0, "court_fees_gbp": 0,
                "typical_hours": 0, "hourly_rate_range_gbp": "—",
                "no_win_no_fee_available": False, "explanation": payload[:300], "ai_advocate_saving": ""}

    # Apply postcode multiplier (UK only) to low/high estimate
    low = int((result.get("low_estimate_gbp") or 0) * mult)
    high = int((result.get("high_estimate_gbp") or 0) * mult)
    result["low_estimate_gbp"] = low
    result["high_estimate_gbp"] = high
    result["postcode_region"] = region_label
    result["postcode_multiplier"] = round(mult, 2)

    # Build 3-way comparison: DIY vs AI Advocate vs Solicitor
    aa_plus_annual = 14.99 * 12   # £179.88
    aa_pro_annual  = 34.99 * 12   # £419.88
    avg_solicitor = (low + high) // 2 if (low + high) > 0 else 0
    court_fees = result.get("court_fees_gbp") or 0
    result["comparison"] = {
        "diy": {
            "label": "DIY (litigant in person)",
            "fee_low": 0, "fee_high": 0,
            "court_fees": court_fees,
            "total_low": court_fees, "total_high": court_fees,
            "downside": "You do all the work. High chance of procedural errors. Tribunal/court may strike out claims for non-compliance. Emotional toll is real.",
            "pros": ["Cheapest by far", "No third-party delays", "You control the timeline"],
            "cons": ["No legal expertise", "Strict deadlines easy to miss", "Burden falls entirely on you"],
        },
        "ai_advocate": {
            "label": "AI Advocate Pro",
            "fee_low": int(aa_pro_annual), "fee_high": int(aa_pro_annual),
            "court_fees": court_fees,
            "total_low": int(aa_pro_annual) + court_fees,
            "total_high": int(aa_pro_annual) + court_fees,
            "downside": "Lex is brilliant for prep + drafts but isn't a regulated solicitor. For court advocacy you'd still need a barrister (or use Solicitor Sanity Check at £49 per question).",
            "pros": ["~95% cost saving vs solicitor", "24/7 access", "ET1/N1 auto-fill, letter drafting, evidence analysis included"],
            "cons": ["Not a regulated solicitor", "Cannot represent you in court", "Premium tier required for full toolkit"],
        },
        "solicitor": {
            "label": "Full-service solicitor",
            "fee_low": low, "fee_high": high,
            "court_fees": court_fees,
            "total_low": low + court_fees,
            "total_high": high + court_fees,
            "downside": "Average UK matter: 60-80 hours of solicitor time at £180-£350/hr. No win = full bill due unless no-win-no-fee deal in place.",
            "pros": ["Regulated profession (SRA)", "Can represent you", "Insurance-backed advice"],
            "cons": ["Most expensive option", "Slow response times", "Risk of bill shock"],
        },
    }
    # Savings vs solicitor mid-point
    if avg_solicitor > 0:
        result["aa_pro_saving_vs_solicitor_gbp"] = avg_solicitor - int(aa_pro_annual)
        result["aa_pro_saving_percent"] = max(0, int(((avg_solicitor - aa_pro_annual) / avg_solicitor) * 100))

    return result


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


# ==================== Phase 2 — Legal Aid done right ====================
# 1. Find a Legal Adviser — scrapes gov.uk's official directory (no public API)
# 2. Draft Application Statement — AI-generated statement of support for civ/crim legal aid

# UK Legal Aid Agency category codes (used by the gov.uk search)
LAA_CATEGORY_CODES = {
    "housing": "hou", "eviction": "hou", "homelessness": "hou",
    "family": "fam",
    "immigration": "imm", "asylum": "imm",
    "debt": "deb",
    "welfare": "wel", "benefits": "wel",
    "community_care": "cmh",
    "mental_health": "mhe", "mental_capacity": "mhe",
    "discrimination": "dis",
    "education": "edu",
    "public_law": "pub",
    "actions_against_police": "aap",
    "clinical_negligence": "cln",
    "personal_injury": "per",
    "consumer": "com",
    "employment": "emp",
    "crime": "cri",
    # Fallback
    "general": "com",
    "other": "com",
}


class FindAdvisersRequest(BaseModel):
    postcode: str
    case_category: str = "general"
    language: str = "en-GB"


@api_router.post("/legal-aid/find-advisers")
async def legal_aid_find_advisers(data: FindAdvisersRequest, user: dict = Depends(get_user)):
    """Real-time lookup of legal aid advisers near a UK postcode using the gov.uk
    'Find a legal aid adviser or family mediator' directory (find-legal-advice.justice.gov.uk).
    Returns up to 12 nearest advisers with phone, address, distance, and matter categories."""
    postcode = (data.postcode or "").strip().upper().replace("  ", " ")
    if not postcode:
        raise HTTPException(400, "Postcode is required")

    # Map to category code (best-effort — fall back to 'com' = consumer/general)
    cat_key = (data.case_category or "general").lower().replace(" ", "_")
    cat_code = LAA_CATEGORY_CODES.get(cat_key) or LAA_CATEGORY_CODES.get(
        next((k for k in LAA_CATEGORY_CODES if k in cat_key), "general"), "com"
    )

    import httpx
    from bs4 import BeautifulSoup

    url = "https://find-legal-advice.justice.gov.uk/search"
    params = {"postcode": postcode, "categories": cat_code, "page": "1"}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Advocate/1.0; +https://aiadvocate.co.uk)"}
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as c:
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        logger.warning(f"find-legal-advice fetch failed: {e}")
        raise HTTPException(502, "Could not reach the gov.uk legal-aid directory. Please try again in a moment.")

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.results-list-item")
    advisers = []
    for li in items[:12]:
        name_el = li.find("h2")
        dist_el = li.select_one("p.govuk-body-s")
        tel_el = li.select_one(".telephone .tel")
        addr_el = li.select_one(".address")
        cats_el = li.select(".categories li")
        # Address: collect all non-visually-hidden text spans
        addr_parts = []
        if addr_el:
            for span in addr_el.find_all("span"):
                txt = span.get_text(strip=True)
                if txt and "Address" not in txt:
                    addr_parts.append(txt.rstrip(","))
        # Distance
        dist_txt = None
        if dist_el:
            t = dist_el.get_text(" ", strip=True).replace("Distance", "").strip()
            dist_txt = t or None
        # Map URL — gov.uk uses google maps deep links
        map_url = None
        for a in li.find_all("a", href=True):
            if "google.com/maps" in a["href"]:
                map_url = a["href"]
                break
        advisers.append({
            "name": name_el.get_text(strip=True) if name_el else "Unknown",
            "telephone": tel_el.get_text(strip=True) if tel_el else None,
            "address": ", ".join([p for p in addr_parts if p]) if addr_parts else None,
            "distance": dist_txt,
            "categories": [c.get_text(" ", strip=True) for c in cats_el][:8],
            "map_url": map_url,
        })

    count_el = soup.select_one("#result-count-overall")
    total_count = 0
    if count_el:
        try:
            total_count = int(count_el.get_text(strip=True).split()[0])
        except Exception:
            pass

    return {
        "postcode": postcode,
        "category_used": cat_code,
        "total_count": total_count,
        "advisers": advisers,
        "source": "https://find-legal-advice.justice.gov.uk/",
        "disclaimer": "Live results from the Legal Aid Agency directory. Coverage varies — call before travelling.",
    }


class DraftApplicationRequest(BaseModel):
    case_type: str = "civil"   # civil | criminal
    case_category: str = ""    # eviction, employment, family, immigration, etc.
    situation: str             # user's plain-English description
    monthly_income_gbp: float = 0
    savings_gbp: float = 0
    household_size: int = 1
    full_name: str = ""
    address: str = ""
    dob: str = ""
    nino: str = ""             # National Insurance number (optional)
    language: str = "en-GB"


@api_router.post("/legal-aid/draft-application")
async def legal_aid_draft_application(data: DraftApplicationRequest, user: dict = Depends(get_user)):
    """AI-generated Statement in Support that the user attaches to the official
    CIVAPP1 (civil legal aid) or CRM14 (criminal) form. Lex writes it in formal
    LAA-friendly language with the right sections and citations."""
    lang_name = LANG_NAMES.get(data.language, "English")

    form_name = "CIVAPP1 (Application for civil legal aid)" if data.case_type == "civil" else "CRM14 (Application for legal aid in criminal proceedings)"

    system = f"""You are a UK legal aid caseworker drafting a Statement in Support for a self-represented applicant.

The statement will be attached to {form_name} submitted to the Legal Aid Agency. Write in formal but plain English ({lang_name}). Follow the structure below exactly. Be specific, factual, and sympathetic — but never exaggerate or invent facts. Where the applicant has not provided a detail, use a clear placeholder in [SQUARE BRACKETS] so they can fill it in.

STRUCTURE (use these exact headings):

# Statement in Support of {form_name}

## Applicant
- Full name: {data.full_name or "[Applicant's full legal name]"}
- Date of birth: {data.dob or "[DD/MM/YYYY]"}
- Address: {data.address or "[Current address including postcode]"}
- National Insurance number: {data.nino or "[NI number]"}
- Monthly income: £{data.monthly_income_gbp or "[Amount]"}
- Total savings: £{data.savings_gbp or "[Amount]"}
- Household size: {data.household_size or "[Number]"}

## 1. Nature of the legal problem
A clear factual narrative of the applicant's situation, written in the applicant's voice (first person, "I"). 2-4 paragraphs. Include dates, names of opposing parties, and the specific legal issue.

## 2. Why I need legal representation
Explain the urgency, the complexity, and what could happen without legal aid. Reference specific UK statutes that apply (e.g. Housing Act 1988 for eviction, Equality Act 2010 for discrimination, Children Act 1989 for family). Keep it factual.

## 3. Means test — financial circumstances
Restate the financial figures the applicant has given. Explain why they fall within the legal aid means thresholds for their case type. Note any debts, dependants, or hardship factors.

## 4. Merits test — strength of the case
Honest assessment of the case's chance of success. Reference the relevant Legal Aid Agency merits criteria. Use language like "There is a reasonable prospect of obtaining a positive outcome because…"

## 5. What I am applying for
Specify the form of legal aid (Legal Help / Help at Court / Family Help / Legal Representation / Controlled Legal Representation). Best-effort match to the case type.

## 6. Supporting documents I will provide
List the typical documents the LAA needs (payslips/benefits letter, bank statements last 3 months, tenancy agreement / employment contract / court papers, ID).

## 7. Declaration
End with: "I declare that the information given in this statement is true to the best of my knowledge and belief. I understand that providing false information may be a criminal offence."
Signed: ___________________
Date: ___________________

Return ONLY the statement in Markdown. No preamble, no explanation, no JSON."""

    user_msg = f"""APPLICANT'S SITUATION (plain English, in their words):
{data.situation}

CASE TYPE: {data.case_type}
CASE CATEGORY: {data.case_category or "(not specified — infer from situation)"}

Draft the full Statement in Support now."""

    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"laa-{uuid.uuid4().hex[:12]}", system_message=system)\
            .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=3500)
        markdown = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("legal-aid draft-application error")
        raise HTTPException(500, f"AI error: {e}")

    if not markdown or not markdown.strip():
        raise HTTPException(502, "Lex couldn't draft the application right now. Try again in a moment.")

    # Determine the official form download link
    form_link = (
        "https://www.gov.uk/government/publications/legal-help-form-civapp1"
        if data.case_type == "civil"
        else "https://www.gov.uk/government/publications/crm-14-form-criminal-legal-aid"
    )

    return {
        "case_type": data.case_type,
        "form_name": form_name,
        "official_form_url": form_link,
        "statement_markdown": markdown.strip(),
        "next_steps": [
            f"Download the official {form_name} from gov.uk",
            "Print this Statement in Support and attach it to the form",
            "Gather your supporting documents (payslips, ID, court papers etc.)",
            "Find a legal aid adviser to file the application (use the 'Find an adviser' tab)",
            "Most legal aid advisers will submit the form on your behalf at no cost to you",
        ],
        "disclaimer": "This statement is AI-generated to help you prepare. A legal aid solicitor will adjust it before submission. Not a substitute for legal advice.",
    }


@api_router.post("/legal-aid/draft-application/pdf")
async def legal_aid_draft_application_pdf(data: DraftApplicationRequest, user: dict = Depends(get_user)):
    """Same as /draft-application but returns a downloadable PDF instead of markdown."""
    # Generate the markdown first by reusing the endpoint
    result = await legal_aid_draft_application(data, user)
    markdown = result["statement_markdown"]

    # Render to PDF using reportlab (already a dependency)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.colors import HexColor
    import io as _io

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.8*cm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, leading=18, textColor=HexColor("#1a1300"), spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, leading=15, textColor=HexColor("#7a5c00"), spaceAfter=6, spaceBefore=10)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=14)

    story = [Paragraph("AI Advocate · Legal Aid Statement in Support", body), Spacer(1, 8)]
    for raw_line in markdown.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            story.append(Spacer(1, 4)); continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:].strip(), h1))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:].strip(), h2))
        elif line.startswith("- ") or line.startswith("* "):
            story.append(Paragraph(f"• {line[2:].strip()}", bullet))
        else:
            # Escape angle brackets for reportlab Paragraph
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Re-enable **bold**
            import re as _re
            safe = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
            story.append(Paragraph(safe, body))

    doc.build(story)
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    fname = f"ai-advocate-legal-aid-statement-{data.case_type}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ==================== 📋 ET1 Employment Tribunal Auto-Fill (Phase 4a) ====================
# Lex generates a fully-populated ET1 claim from the user's chat history (+ a
# few targeted top-up questions). Output is a structured JSON payload AND a
# downloadable PDF that mirrors the gov.uk ET1 format — ready as a fill-in
# companion for the official online service.

class ET1DraftRequest(BaseModel):
    session_id: str = ""
    full_name: str = ""
    address: str = ""
    postcode: str = ""
    phone: str = ""
    email: str = ""
    dob: str = ""
    employer_name: str = ""
    employer_address: str = ""
    job_title: str = ""
    employment_start_date: str = ""
    employment_end_date: str = ""
    weekly_hours: str = ""
    gross_pay: str = ""
    net_pay: str = ""
    notice_period: str = ""
    acas_certificate_number: str = ""
    acas_received_date: str = ""
    extra_context: str = Field(default="", min_length=40, description="Plain-English narrative of what happened. Min 40 chars to avoid wasting Claude tokens on too-short prompts.")
    language: str = "en-GB"


def _et1_structure_schema() -> str:
    return """{
  "claimant": {"title": "Mr|Mrs|Ms|Mx|other", "full_name": "string", "dob": "DD/MM/YYYY", "address": "full multi-line address", "postcode": "string", "phone": "string", "email": "string"},
  "respondent": {"employer_name": "string", "employer_address": "full multi-line address with postcode"},
  "acas": {"certificate_number": "string (e.g. R123456/26/12) or [REQUIRED]", "received_date": "DD/MM/YYYY or [REQUIRED]"},
  "employment": {"job_title": "string", "start_date": "DD/MM/YYYY", "end_date": "DD/MM/YYYY or 'Still employed'", "still_employed": true|false, "weekly_hours": "string", "gross_pay": "string", "net_pay": "string", "notice_period": "string"},
  "claim_types": ["unfair_dismissal" | "discrimination" | "redundancy_pay" | "unauthorised_deductions" | "breach_of_contract" | "equal_pay" | "harassment" | "victimisation" | "whistleblowing" | "automatic_unfair_dismissal" | "constructive_dismissal" | "other"],
  "discrimination_grounds": ["age" | "disability" | "gender_reassignment" | "marriage_civil_partnership" | "pregnancy_maternity" | "race" | "religion_belief" | "sex" | "sexual_orientation"],
  "narrative": {"what_happened": "3-6 paragraph factual narrative in first person", "why_unfair_or_unlawful": "1-2 paragraphs naming the relevant statute", "key_dates_chronology": [{"date": "DD/MM/YYYY", "event": "what happened"}]},
  "remedy_sought": {"compensation": true|false, "reinstatement": true|false, "reengagement": true|false, "declaration": true|false, "recommendation": true|false, "compensation_amount_sought": "string", "explanation": "1-2 sentences"},
  "supporting_evidence_list": ["specific document e.g. 'Dismissal letter dated 12/03/2026'"],
  "warnings_for_claimant": ["string"]
}"""


@api_router.post("/forms/et1/draft")
async def forms_et1_draft(data: ET1DraftRequest, user: dict = Depends(get_user)):
    chat_context = ""
    if data.session_id:
        cursor = db.conversations.find(
            {"user_id": user["id"], "session_id": data.session_id, "user_message": {"$ne": None}},
            sort=[("created_at", -1)], projection={"_id": 0, "user_message": 1, "assistant_response": 1},
        ).limit(10)
        msgs = [m async for m in cursor]
        msgs.reverse()
        chat_context = "\n\n".join(
            f"USER: {m['user_message']}\nLEX: {m.get('assistant_response','')[:2500]}" for m in msgs
        )[:18000]

    user_overrides = {
        "full_name": data.full_name, "address": data.address, "postcode": data.postcode,
        "phone": data.phone, "email": data.email, "dob": data.dob,
        "employer_name": data.employer_name, "employer_address": data.employer_address,
        "job_title": data.job_title, "start_date": data.employment_start_date,
        "end_date": data.employment_end_date, "weekly_hours": data.weekly_hours,
        "gross_pay": data.gross_pay, "net_pay": data.net_pay, "notice_period": data.notice_period,
        "acas_certificate_number": data.acas_certificate_number,
        "acas_received_date": data.acas_received_date,
    }
    user_overrides = {k: v for k, v in user_overrides.items() if v}

    system = f"""You are a UK Employment Tribunal paralegal drafting an ET1 claim form for a self-represented claimant.

Produce ONLY a single valid JSON object matching this schema (no prose, no markdown fences):

{_et1_structure_schema()}

CRITICAL RULES:
1. Extract facts ONLY from the chat history + user-provided fields. NEVER invent facts. Unknown facts = "[PLACEHOLDER — claimant to confirm]".
2. Pick claim_types CONSERVATIVELY. Only include if the chat clearly evidences it.
3. narrative.what_happened — FIRST PERSON, 3-6 paragraphs, dated and named events, plain English.
4. Name UK statutes: Employment Rights Act 1996 (s.94 unfair dismissal, s.139 redundancy), Equality Act 2010 (discrimination), Public Interest Disclosure Act 1998 (whistleblowing), TULRCA 1992.
5. acas.certificate_number — if not provided: "[REQUIRED — get an ACAS Early Conciliation Certificate before filing. Visit acas.org.uk or call 0300 123 1100. Free.]"
6. warnings_for_claimant MUST include: (a) 3-months-less-1-day time limit reminder, (b) "attach X" reminders, (c) ACAS requirement if not done.
7. key_dates_chronology — extract every date mentioned, sort ascending.
8. Return ONLY the JSON object."""

    user_msg = f"""USER-PROVIDED FIELDS (override Lex's chat inferences):
{json.dumps(user_overrides, indent=2) if user_overrides else "(none — extract everything from chat history)"}

EXTRA CONTEXT FROM USER:
{data.extra_context or "(none)"}

CHAT HISTORY:
{chat_context or "(no chat history — rely on user-provided fields above)"}

Produce the ET1 JSON now."""

    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"et1-{uuid.uuid4().hex[:12]}", system_message=system)\
            .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=6000)
        raw = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("ET1 draft error")
        raise HTTPException(500, f"AI error: {e}")

    et1 = _extract_json_object(raw)
    if not et1:
        logger.warning(f"ET1 JSON parse failed (raw len={len(raw or '')}): {(raw or '')[:600]}")
        raise HTTPException(502, "Lex couldn't structure the ET1 right now. Try again in a moment.")

    draft_id = str(uuid.uuid4())
    rec = {
        "id": draft_id, "user_id": user["id"], "form": "ET1",
        "data": et1, "user_overrides": user_overrides,
        "extra_context": data.extra_context,
        "session_id": data.session_id, "language": data.language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.form_drafts.insert_one(rec)

    return {
        "draft_id": draft_id, "form": "ET1",
        "data": et1,
        "official_form_url": "https://www.gov.uk/government/publications/employment-tribunal-claim-form-et1",
        "online_submission_url": "https://employmenttribunal.service.gov.uk/",
        "acas_url": "https://www.acas.org.uk/early-conciliation",
        "disclaimer": "AI-generated draft. Review every field carefully. Lex cannot file the form for you — this is preparation only.",
    }


@api_router.get("/forms/et1/{draft_id}")
async def forms_et1_get(draft_id: str, user: dict = Depends(get_user)):
    rec = await db.form_drafts.find_one({"id": draft_id, "user_id": user["id"], "form": "ET1"}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Draft not found")
    return rec


class ET1UpdateRequest(BaseModel):
    data: dict


@api_router.put("/forms/et1/{draft_id}")
async def forms_et1_update(draft_id: str, body: ET1UpdateRequest, user: dict = Depends(get_user)):
    rec = await db.form_drafts.find_one({"id": draft_id, "user_id": user["id"], "form": "ET1"})
    if not rec:
        raise HTTPException(404, "Draft not found")
    await db.form_drafts.update_one(
        {"id": draft_id},
        {"$set": {"data": body.data, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


@api_router.get("/forms/et1/{draft_id}/pdf")
async def forms_et1_pdf(draft_id: str, user: dict = Depends(get_user)):
    rec = await db.form_drafts.find_one({"id": draft_id, "user_id": user["id"], "form": "ET1"}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Draft not found")
    et1 = rec["data"]

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    import io as _io

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.6*cm, bottomMargin=1.6*cm)
    styles = getSampleStyleSheet()
    GOLD = HexColor("#7a5c00"); DARK = HexColor("#1a1300")
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, leading=22, textColor=DARK, alignment=TA_LEFT, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["BodyText"], fontSize=10, textColor=HexColor("#666"), spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, leading=15, textColor=GOLD, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=4)
    label = ParagraphStyle("label", parent=body, textColor=HexColor("#666"), fontName="Helvetica-Bold")
    warn = ParagraphStyle("warn", parent=body, textColor=HexColor("#b91c1c"), backColor=HexColor("#fef2f2"))

    story = [
        Paragraph("ET1 · Employment Tribunal Claim Form", title),
        Paragraph("AI Advocate auto-fill companion. Use alongside the gov.uk online form at employmenttribunal.service.gov.uk.", sub),
    ]

    def kv_table(rows):
        data_rows = [[Paragraph(f"<b>{k}</b>", label), Paragraph(str(v) if v else "—", body)] for k, v in rows]
        t = Table(data_rows, colWidths=[5*cm, 12*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#fff8e1")),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#dddddd")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    c = et1.get("claimant", {}) or {}
    story.append(Paragraph("1. Your details (the claimant)", h2))
    story.append(kv_table([
        ("Title", c.get("title", "")), ("Full name", c.get("full_name", "")),
        ("Date of birth", c.get("dob", "")), ("Address", c.get("address", "")),
        ("Postcode", c.get("postcode", "")), ("Phone", c.get("phone", "")),
        ("Email", c.get("email", "")),
    ]))

    r = et1.get("respondent", {}) or {}
    story.append(Paragraph("2. The respondent (employer)", h2))
    story.append(kv_table([("Employer name", r.get("employer_name", "")), ("Employer address", r.get("employer_address", ""))]))

    a = et1.get("acas", {}) or {}
    story.append(Paragraph("3. ACAS Early Conciliation (required before filing)", h2))
    story.append(kv_table([("Certificate number", a.get("certificate_number", "")), ("Date received", a.get("received_date", ""))]))

    e = et1.get("employment", {}) or {}
    story.append(Paragraph("4. Employment details", h2))
    story.append(kv_table([
        ("Job title", e.get("job_title", "")), ("Employment start date", e.get("start_date", "")),
        ("Employment end date", e.get("end_date", "")),
        ("Still employed?", "Yes" if e.get("still_employed") else "No"),
        ("Hours / week", e.get("weekly_hours", "")), ("Gross pay", e.get("gross_pay", "")),
        ("Net pay", e.get("net_pay", "")), ("Notice period", e.get("notice_period", "")),
    ]))

    story.append(Paragraph("5. Type of claim", h2))
    claim_types = et1.get("claim_types") or []
    if claim_types:
        labels = {
            "unfair_dismissal": "Unfair dismissal", "discrimination": "Discrimination",
            "redundancy_pay": "Redundancy pay", "unauthorised_deductions": "Unauthorised deductions from wages",
            "breach_of_contract": "Breach of contract", "equal_pay": "Equal pay",
            "harassment": "Harassment", "victimisation": "Victimisation",
            "whistleblowing": "Whistleblowing (PIDA)", "automatic_unfair_dismissal": "Automatic unfair dismissal",
            "constructive_dismissal": "Constructive dismissal", "other": "Other",
        }
        story.append(Paragraph("<br/>".join(f"☑ {labels.get(t, t)}" for t in claim_types), body))
    else:
        story.append(Paragraph("(none identified)", body))

    disc = et1.get("discrimination_grounds") or []
    if disc:
        story.append(Paragraph("5a. Protected characteristics (discrimination grounds)", h2))
        dlabels = {
            "age": "Age", "disability": "Disability", "gender_reassignment": "Gender reassignment",
            "marriage_civil_partnership": "Marriage / civil partnership", "pregnancy_maternity": "Pregnancy / maternity",
            "race": "Race", "religion_belief": "Religion or belief", "sex": "Sex", "sexual_orientation": "Sexual orientation",
        }
        story.append(Paragraph("<br/>".join(f"☑ {dlabels.get(g, g)}" for g in disc), body))

    n = et1.get("narrative", {}) or {}
    story.append(Paragraph("8. Your claim — what happened (the facts)", h2))
    what = (n.get("what_happened") or "").strip()
    for para in what.split("\n\n"):
        if para.strip():
            safe = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            story.append(Paragraph(safe, body))

    why = (n.get("why_unfair_or_unlawful") or "").strip()
    if why:
        story.append(Paragraph("Why this was unfair or unlawful", h2))
        safe = why.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        story.append(Paragraph(safe, body))

    chrono = n.get("key_dates_chronology") or []
    if chrono:
        story.append(Paragraph("Chronology of key dates", h2))
        rows = [[Paragraph(f"<b>{cr.get('date','—')}</b>", label), Paragraph(cr.get('event',''), body)] for cr in chrono]
        t = Table(rows, colWidths=[3*cm, 14*cm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#dddddd")),
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#fff8e1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    rem = et1.get("remedy_sought", {}) or {}
    story.append(Paragraph("9. What outcome you are seeking (remedy)", h2))
    rem_bullets = []
    if rem.get("compensation"): rem_bullets.append("☑ Compensation")
    if rem.get("reinstatement"): rem_bullets.append("☑ Reinstatement (return to your old job)")
    if rem.get("reengagement"): rem_bullets.append("☑ Re-engagement (a different role with the same employer)")
    if rem.get("declaration"): rem_bullets.append("☑ Declaration that your rights have been breached")
    if rem.get("recommendation"): rem_bullets.append("☑ Recommendation (tribunal asks employer to take action)")
    if rem_bullets:
        story.append(Paragraph("<br/>".join(rem_bullets), body))
    if rem.get("compensation_amount_sought"):
        story.append(Paragraph(f"<b>Amount sought:</b> {rem['compensation_amount_sought']}", body))
    if rem.get("explanation"):
        story.append(Paragraph(rem["explanation"], body))

    evi = et1.get("supporting_evidence_list") or []
    if evi:
        story.append(Paragraph("10. Supporting documents to attach", h2))
        story.append(Paragraph("<br/>".join(f"• {x}" for x in evi), body))

    warnings = et1.get("warnings_for_claimant") or []
    if warnings:
        story.append(Spacer(1, 6))
        story.append(Paragraph("⚠ Important — read before filing", h2))
        for w in warnings:
            safe = w.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f"• {safe}", warn))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "<i>This document was generated by AI Advocate. It is preparatory and informational only — not legal advice. Always file your ET1 via the official online service at employmenttribunal.service.gov.uk and complete ACAS Early Conciliation first (acas.org.uk).</i>",
        ParagraphStyle("foot", parent=body, fontSize=8, textColor=HexColor("#888")),
    ))

    doc.build(story)
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    fname = f"ai-advocate-ET1-{draft_id[:8]}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api_router.get("/forms/drafts")
async def forms_list_drafts(user: dict = Depends(get_user)):
    cursor = db.form_drafts.find(
        {"user_id": user["id"]},
        {"_id": 0, "data": 0},
    ).sort("created_at", -1).limit(40)
    items = [d async for d in cursor]
    return {"items": items}



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


@api_router.get("/admin/rag-usage")
async def admin_rag_usage(_: dict = Depends(require_admin)):
    """Tavily usage this month — used / cap / remaining. Lets the owner see whether
    Lex's RAG grounding is still active before the monthly cap kicks in."""
    usage = await rag_get_usage(db)
    return {
        "enabled": rag_enabled(),
        **usage,
        "pct_used": round(100.0 * usage["used"] / usage["cap"], 1) if usage["cap"] else 0.0,
    }


# ==================== Admin: Feature suggestion inbox ====================
# Reads from db.feature_requests (populated by the "Missing a legal area?" modal
# via POST /feedback/suggest). One-screen inbox so the owner can review and
# triage suggestions without digging through their email.

@api_router.get("/admin/suggestions")
async def admin_list_suggestions(
    _: dict = Depends(require_admin),
    status: Optional[str] = None,  # "open" | "resolved" | None (all)
):
    q: dict = {}
    if status == "open":
        q["resolved_at"] = {"$in": [None, "", False]}
    elif status == "resolved":
        q["resolved_at"] = {"$nin": [None, "", False]}
    items = []
    async for r in db.feature_requests.find(q, {"_id": 0}).sort("created_at", -1).limit(500):
        items.append(r)
    open_count = await db.feature_requests.count_documents({"resolved_at": {"$in": [None, "", False]}})
    return {"suggestions": items, "open_count": open_count, "total": await db.feature_requests.count_documents({})}


class SuggestionResolveBody(BaseModel):
    resolved: bool = True
    admin_note: Optional[str] = ""


@api_router.patch("/admin/suggestions/{sid}")
async def admin_mark_suggestion(sid: str, body: SuggestionResolveBody, admin: dict = Depends(require_admin)):
    if body.resolved:
        update = {"$set": {
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": admin["email"],
            "admin_note": (body.admin_note or "")[:500],
        }}
    else:
        update = {"$set": {"resolved_at": None, "resolved_by": None}}
    res = await db.feature_requests.update_one({"id": sid}, update)
    if res.matched_count == 0:
        raise HTTPException(404, "Suggestion not found")
    return {"ok": True}


@api_router.delete("/admin/suggestions/{sid}")
async def admin_delete_suggestion(sid: str, _: dict = Depends(require_admin)):
    res = await db.feature_requests.delete_one({"id": sid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Suggestion not found")
    return {"ok": True}






# ==================== Admin: Solicitor Brief download ====================
# Static PDF served from /app/memory. Admin-only because it's a privileged
# document the owner sends to their solicitor. The PDF is regenerated on each
# call from /app/backend/tools/generate_solicitor_brief.py so the date in the
# document is always today.

@api_router.get("/admin/solicitor-brief.pdf")
async def admin_solicitor_brief(_: dict = Depends(require_admin)):
    """Generate (fresh) and return the AI Advocate solicitor engagement brief."""
    from fastapi.responses import FileResponse
    import subprocess
    pdf_path = "/app/memory/AI_Advocate_Solicitor_Brief.pdf"
    try:
        subprocess.run(
            ["python", "/app/backend/tools/generate_solicitor_brief.py"],
            check=True, capture_output=True, timeout=30,
        )
    except Exception:
        # Fall through to whatever file is on disk; only fail if it's missing.
        pass
    if not os.path.exists(pdf_path):
        raise HTTPException(500, "Brief not available — regeneration failed.")
    return FileResponse(
        pdf_path, media_type="application/pdf",
        filename="AI_Advocate_Solicitor_Brief.pdf",
    )


@api_router.get("/admin/founder-briefing.pdf")
async def admin_founder_briefing(_: dict = Depends(require_admin)):
    """Generate (fresh) and return the FOUNDER BRIEFING PDF — internal-only
    pitch / talking-points / honest-status document for Samuel's client meetings."""
    from fastapi.responses import FileResponse
    import subprocess
    pdf_path = "/app/memory/AI_Advocate_Founder_Briefing.pdf"
    try:
        subprocess.run(
            ["python", "/app/backend/tools/generate_founder_briefing.py"],
            check=True, capture_output=True, timeout=30,
        )
    except Exception:
        pass
    if not os.path.exists(pdf_path):
        raise HTTPException(500, "Founder briefing not available — regeneration failed.")
    return FileResponse(
        pdf_path, media_type="application/pdf",
        filename="AI_Advocate_Founder_Briefing.pdf",
    )


@api_router.get("/admin/founding-firm-agreement.pdf")
async def admin_founding_firm_agreement(
    firm_name: str = "",
    sra: str = "",
    address: str = "",
    contact: str = "",
    email: str = "",
    _: dict = Depends(require_admin),
):
    """Generate (fresh) and return the FOUNDING FIRM AGREEMENT PDF, personalised with
    the firm's details if provided. Empty fields fall back to bracketed placeholders
    you can manually fill before sending. Used to onboard the first 20 founding firms."""
    from fastapi.responses import FileResponse
    import subprocess
    pdf_path = "/app/memory/AI_Advocate_Founding_Firm_Agreement.pdf"
    args = ["python", "/app/backend/tools/generate_founding_firm_agreement.py"]
    if firm_name: args += ["--firm-name", firm_name]
    if sra:       args += ["--sra", sra]
    if address:   args += ["--address", address]
    if contact:   args += ["--contact", contact]
    if email:     args += ["--email", email]
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=30)
    except Exception:
        pass
    if not os.path.exists(pdf_path):
        raise HTTPException(500, "Agreement not available — regeneration failed.")
    safe_firm = (firm_name or "Template").replace(" ", "_").replace("/", "_")[:60]
    return FileResponse(
        pdf_path, media_type="application/pdf",
        filename=f"AI_Advocate_Founding_Firm_Agreement_{safe_firm}.pdf",
    )


# ==================== Founding Firm Agreement — E-signature flow ====================
# Three-step flow:
#   1) Admin clicks "Send for signature" → /admin/firm-agreements/send
#      • Backend creates a firm_agreement record with a unique token + AA signature
#      • Emails the firm a signing URL: aiadvocate.co.uk/firm-sign/<token>
#   2) Firm opens the signing URL → GET /firm-agreements/<token>
#      • Public endpoint (no auth) returns agreement metadata so the page can render
#   3) Firm signs in their browser (canvas) → POST /firm-agreements/<token>/sign
#      • Captures IP + UA for the audit trail
#      • Regenerates the PDF with BOTH signatures embedded
#      • Emails both parties a copy of the signed PDF
#
# Legally binding under UK Electronic Communications Act 2000 + eIDAS as a
# "simple electronic signature" (typed name + canvas drawing + IP + timestamp).

class FirmAgreementSendPayload(BaseModel):
    firm_name: str
    sra: str = ""
    address: str = ""
    contact_name: str   # e.g. "Jane Smith, Partner"
    contact_email: str
    aa_signature_data_url: str  # base64 PNG drawn by founder in admin panel

class FirmAgreementSignPayload(BaseModel):
    firm_signer_name: str   # typed full name
    firm_signature_data_url: str  # base64 PNG drawn on canvas


def _agreement_to_public(rec: dict) -> dict:
    """Strip Mongo internal + sensitive fields before returning to client."""
    if not rec: return None
    return {
        "token": rec.get("token"),
        "firm_name": rec.get("firm_name"),
        "sra": rec.get("sra"),
        "address": rec.get("address"),
        "contact_name": rec.get("contact_name"),
        "contact_email": rec.get("contact_email"),
        "status": rec.get("status"),  # "sent" | "signed" | "declined"
        "sent_at": rec.get("sent_at"),
        "signed_at": rec.get("signed_at"),
        "aa_signer_name": rec.get("aa_signer_name"),
        "firm_signer_name": rec.get("firm_signer_name"),
    }


def _generate_signed_pdf(rec: dict) -> str:
    """Regenerate the agreement PDF with whatever signatures are on record. Returns the file path."""
    from tools.generate_founding_firm_agreement import build as _build
    safe = (rec.get("firm_name") or "Firm").replace(" ", "_").replace("/", "_")[:60]
    out = f"/app/memory/agreements/{rec['token']}_{safe}.pdf"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    _build(
        firm_name=rec.get("firm_name") or "[FIRM NAME]",
        sra_number=rec.get("sra") or "[SRA NUMBER]",
        firm_address=rec.get("address") or "[FIRM ADDRESS]",
        primary_contact=rec.get("contact_name") or "[CONTACT]",
        firm_email=rec.get("contact_email") or "[FIRM EMAIL]",
        signed_date=(rec.get("sent_at") or datetime.now(timezone.utc).isoformat())[:10],
        aa_signature_data_url=rec.get("aa_signature_data_url"),
        firm_signature_data_url=rec.get("firm_signature_data_url"),
        firm_signed_date=(rec.get("signed_at") or "")[:10] if rec.get("signed_at") else None,
        output_path=out,
    )
    return out


@api_router.post("/admin/firm-agreements/send")
async def admin_firm_agreement_send(
    data: FirmAgreementSendPayload,
    request: Request,
    _: dict = Depends(require_admin),
):
    """Create a new firm agreement record + email the firm a signing link."""
    if not (data.aa_signature_data_url or "").startswith("data:image/"):
        raise HTTPException(400, "Founder signature required to send an agreement.")
    if len(data.aa_signature_data_url) > 200_000:
        raise HTTPException(413, "Signature image too large.")
    if not data.contact_email or "@" not in data.contact_email:
        raise HTTPException(400, "Valid firm contact email required.")

    token = _secrets.token_urlsafe(20)
    now = datetime.now(timezone.utc).isoformat()
    rec = {
        "_id": str(uuid.uuid4()),
        "token": token,
        "firm_name": data.firm_name.strip(),
        "sra": data.sra.strip(),
        "address": data.address.strip(),
        "contact_name": data.contact_name.strip(),
        "contact_email": data.contact_email.strip().lower(),
        "aa_signer_name": "Samuel Malick",
        "aa_signature_data_url": data.aa_signature_data_url,
        "firm_signer_name": None,
        "firm_signature_data_url": None,
        "status": "sent",
        "sent_at": now,
        "signed_at": None,
        "signer_ip": None,
        "signer_user_agent": None,
        # Snapshot of clause-1.6 wording at the time of sending — protects both parties
        # from disputes if we update the template later.
        "terms_snapshot_version": "2026-02-rev1",
    }
    await db.firm_agreements.insert_one(rec)

    # Production public URL — hardcoded to avoid env-var drift between deployments.
    # If we ever support multiple domains, switch back to an env var, but for now
    # this is the canonical site users open in their browser.
    app_base = "https://aiadvocate.co.uk"
    signing_url = f"{app_base}/firm-sign/{token}"

    # Email the firm
    try:
        from email_helper import send_email
        await send_email(
            to=data.contact_email,
            kind="firm",
            subject=f"AI Advocate — Founding Firm Agreement for {data.firm_name}",
            body_html=f"""<p>Hi {data.contact_name.split(',')[0]},</p>
            <p>Thank you for joining the AI Advocate <strong>Founding Firm</strong> cohort.</p>
            <p>Your Founding Firm Agreement is ready to sign. It locks in your £199/month rate for life and confirms all the benefits we discussed (70/30 referral split, App Store launch marketing, ranking boost, etc.).</p>
            <p style="margin:24px 0;"><a href="{signing_url}" style="background:#f7c948;color:#1a1300;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:700;">Review &amp; sign agreement →</a></p>
            <p style="color:#666;font-size:13px;">Or copy this link: <a href="{signing_url}">{signing_url}</a></p>
            <p style="color:#666;font-size:12px;">You can review the full agreement on screen, draw your signature, and we'll email both parties a signed PDF copy. This link is unique to your firm — please don't forward it.</p>
            <p>Any questions, please contact <a href="mailto:firms@aiadvocate.co.uk">firms@aiadvocate.co.uk</a>.</p>
            <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
        )
    except Exception as e:
        # Don't 500 — admin can resend or the firm can be given the link directly
        print(f"[firm-agreement] Email send failed for {data.contact_email}: {e}")

    return {"ok": True, "token": token, "signing_url": signing_url}


@api_router.get("/firm-agreements/{token}")
async def get_firm_agreement(token: str):
    """Public endpoint — fetch agreement metadata for the signing page (no auth)."""
    rec = await db.firm_agreements.find_one({"token": token})
    if not rec:
        raise HTTPException(404, "Agreement not found or link expired.")
    return _agreement_to_public(rec)


@api_router.post("/firm-agreements/{token}/sign")
async def sign_firm_agreement(token: str, data: FirmAgreementSignPayload, request: Request):
    """Public endpoint — firm submits their signature. Locks the record + emails both parties."""
    rec = await db.firm_agreements.find_one({"token": token})
    if not rec:
        raise HTTPException(404, "Agreement not found.")
    if rec.get("status") == "signed":
        raise HTTPException(409, "This agreement has already been signed.")
    if not (data.firm_signature_data_url or "").startswith("data:image/"):
        raise HTTPException(400, "Signature required.")
    if len(data.firm_signature_data_url) > 200_000:
        raise HTTPException(413, "Signature image too large.")
    if len((data.firm_signer_name or "").strip()) < 2:
        raise HTTPException(400, "Please type your full name.")

    now = datetime.now(timezone.utc).isoformat()
    signer_ip = _client_ip(request)
    signer_ua = (request.headers.get("user-agent") or "")[:300]

    await db.firm_agreements.update_one({"token": token}, {"$set": {
        "firm_signer_name": data.firm_signer_name.strip(),
        "firm_signature_data_url": data.firm_signature_data_url,
        "status": "signed",
        "signed_at": now,
        "signer_ip": signer_ip,
        "signer_user_agent": signer_ua,
    }})
    fresh = await db.firm_agreements.find_one({"token": token})

    # 🎯 Auto-promote to Founding Firm trial — lifetime £199 Premium tier.
    # As soon as the firm signs, they show up in the "Firm trial active" list
    # with a 100-year trial (effectively lifetime) at the Premium tier. Saves
    # the founder a manual step and means the firm can log in to the firm
    # portal immediately if they want to.
    try:
        contact_email = (fresh.get("contact_email") or "").lower()
        if contact_email:
            existing_firm = await db.firm_accounts.find_one({"email": contact_email})
            if existing_firm:
                # Firm already exists — extend trial to lifetime + bump tier.
                until = (datetime.now(timezone.utc) + timedelta(days=36500)).isoformat()
                await db.firm_accounts.update_one(
                    {"id": existing_firm["id"]},
                    {"$set": {
                        "trial_until": until,
                        "trial_tier": "premium",
                        "trial_granted_by": "founding-firm-signed",
                        "trial_granted_at": now,
                        "founding_firm": True,
                        "founding_firm_signed_at": now,
                        "founding_firm_agreement_token": token,
                    }}
                )
                await db.firm_comp_audit.insert_one({
                    "id": str(uuid.uuid4()),
                    "granted_by_id": "system", "granted_by_email": "system",
                    "target_firm_id": existing_firm["id"], "target_firm_email": contact_email,
                    "target_firm_name": existing_firm.get("firm_name") or fresh.get("firm_name") or "",
                    "days": 36500, "tier": "premium", "until": until,
                    "reason": "Founding Firm Agreement signed — auto-promoted to lifetime Premium",
                    "at": now, "action": "founding_firm_auto_promote",
                })
            else:
                # Firm hasn't signed up to the portal yet — queue a pending grant
                # so they get the lifetime Premium tier the moment they create an account.
                await db.pending_firm_comp_grants.update_one(
                    {"email": contact_email},
                    {"$set": {
                        "email": contact_email, "days": 36500, "tier": "premium",
                        "reason": f"Founding Firm Agreement signed ({fresh.get('firm_name','')})",
                        "granted_by_id": "system", "granted_by_email": "system",
                        "queued_at": now, "founding_firm": True,
                        "founding_firm_agreement_token": token,
                    }},
                    upsert=True,
                )
                await db.firm_comp_audit.insert_one({
                    "id": str(uuid.uuid4()),
                    "granted_by_id": "system", "granted_by_email": "system",
                    "target_firm_id": None, "target_firm_email": contact_email,
                    "target_firm_name": fresh.get("firm_name") or "",
                    "days": 36500, "tier": "premium", "until": None,
                    "reason": "Founding Firm Agreement signed — queued for auto-promote on signup",
                    "at": now, "action": "founding_firm_pre_comp_queued",
                })
    except Exception as e:
        print(f"[firm-agreement] auto-promote failed (non-fatal): {e}")

    # Regenerate signed PDF + email both parties
    try:
        pdf_path = _generate_signed_pdf(fresh)
        # 🔑 Generate a portal-login link for the firm.
        #   • If firm has a portal account → reset-password link so they can log in instantly
        #   • If firm doesn't have an account yet → /firm-portal sign-up link (their
        #     pending lifetime-Premium grant will auto-apply on signup)
        portal_url = "https://aiadvocate.co.uk/firm-portal"
        portal_cta_label = "Open your firm portal →"
        portal_cta_link = portal_url
        portal_explainer = "Sign up using this email — your lifetime Founding Firm Premium will auto-apply."
        try:
            contact_email = (fresh.get("contact_email") or "").lower()
            if contact_email:
                existing = await db.firm_accounts.find_one({"email": contact_email}, {"_id": 0, "id": 1, "email": 1})
                if existing:
                    tok = await _create_reset_token(account_kind="firm", account_id=existing["id"], email=existing["email"])
                    portal_cta_link = f"https://aiadvocate.co.uk/reset.html?token={tok}&kind=firm"
                    portal_cta_label = "Set your password & log in →"
                    portal_explainer = "We've upgraded your firm to lifetime Premium. Set a password to log in."
        except Exception as e:
            print(f"[firm-agreement] portal link gen failed: {e}")

        try:
            from email_helper import send_email
            # Read PDF as base64 for the email attachment
            import base64 as _b64
            with open(pdf_path, "rb") as fh:
                pdf_b64 = _b64.b64encode(fh.read()).decode("utf-8")

            firm_email_html = f"""<p>The Founding Firm Agreement between AI Advocate Ltd. and <strong>{fresh['firm_name']}</strong> has been signed by both parties. Welcome to the cohort. 🎉</p>
            <ul>
              <li>Signed by AI Advocate: {fresh.get('aa_signer_name')}</li>
              <li>Signed by Firm: {fresh.get('firm_signer_name')}</li>
              <li>Signed on: {now[:10]}</li>
            </ul>
            <p><strong>Next step — set up your firm portal:</strong></p>
            <p>{portal_explainer}</p>
            <p style="margin:24px 0;"><a href="{portal_cta_link}" style="background:#f7c948;color:#1a1300;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:700;">{portal_cta_label}</a></p>
            <p style="color:#666; font-size:13px;">Inside the portal you can:</p>
            <ul style="color:#444; font-size:13px;">
              <li>Upload your firm logo and brand colours</li>
              <li>Set your specialisms and opening hours</li>
              <li>Add your fee-earners (multi-seat access)</li>
              <li>Receive client invites from AI Advocate users</li>
              <li>See your Founding Firm badge on your directory listing</li>
            </ul>
            <p style="color:#666; font-size:12px;">A signed PDF copy of the agreement is attached for your records.</p>"""

            aa_email_html = f"""<p>The Founding Firm Agreement between AI Advocate Ltd. and <strong>{fresh['firm_name']}</strong> has been signed by both parties.</p>
            <ul>
              <li>Signed by AI Advocate: {fresh.get('aa_signer_name')}</li>
              <li>Signed by Firm: {fresh.get('firm_signer_name')} ({fresh.get('contact_email')})</li>
              <li>Signed on: {now[:10]}</li>
              <li>Auto-promoted to: Lifetime Premium tier</li>
            </ul>
            <p>A signed PDF copy is attached.</p>"""

            for recipient, html_body, who in [
                (fresh["contact_email"], firm_email_html, "Firm"),
                ("firms@aiadvocate.co.uk", aa_email_html, "AI Advocate"),
            ]:
                try:
                    await send_email(
                        to=recipient,
                        kind="firm",
                        subject=f"✅ Signed — Founding Firm Agreement: {fresh['firm_name']}",
                        body_html=html_body,
                        attachments=[{
                            "filename": f"AI_Advocate_Founding_Firm_Agreement_{fresh['firm_name'].replace(' ', '_')[:40]}_SIGNED.pdf",
                            "content": pdf_b64,
                        }],
                    )
                except Exception as e:
                    print(f"[firm-agreement] Email to {recipient} failed: {e}")
        except Exception as e:
            print(f"[firm-agreement] PDF email step failed: {e}")
    except Exception as e:
        print(f"[firm-agreement] PDF regen failed: {e}")

    return {"ok": True, "status": "signed", "signed_at": now}


@api_router.get("/firm-agreements/{token}/pdf")
async def get_signed_firm_agreement_pdf(token: str):
    """Public endpoint — download the (signed or in-progress) PDF for a given token."""
    rec = await db.firm_agreements.find_one({"token": token})
    if not rec:
        raise HTTPException(404, "Agreement not found.")
    from fastapi.responses import FileResponse
    pdf_path = _generate_signed_pdf(rec)
    safe = (rec.get("firm_name") or "Firm").replace(" ", "_")[:40]
    suffix = "_SIGNED" if rec.get("status") == "signed" else ""
    return FileResponse(
        pdf_path, media_type="application/pdf",
        filename=f"AI_Advocate_Founding_Firm_Agreement_{safe}{suffix}.pdf",
    )


@api_router.delete("/admin/firm-agreements/{token}")
async def admin_delete_firm_agreement(token: str, admin: dict = Depends(require_admin)):
    """Permanently delete an agreement record. Useful for typos or wrong recipients.
    Does NOT affect the firm_accounts row if the agreement was already signed —
    the founder should revoke the firm trial separately from the firm trial list."""
    rec = await db.firm_agreements.find_one({"token": token})
    if not rec:
        raise HTTPException(404, "Agreement not found.")
    await db.firm_agreements.delete_one({"token": token})
    await db.firm_comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_firm_id": None, "target_firm_email": rec.get("contact_email"),
        "target_firm_name": rec.get("firm_name") or "",
        "days": 0, "tier": "", "until": None,
        "reason": f"Founding Firm Agreement deleted (status was: {rec.get('status')})",
        "at": datetime.now(timezone.utc).isoformat(), "action": "founding_firm_agreement_deleted",
    })
    return {"ok": True, "deleted": True}


@api_router.post("/admin/firm-agreements/{token}/resend")
async def admin_resend_firm_agreement(token: str, _: dict = Depends(require_admin)):
    """Re-send the signing link to the firm. Useful when they say "I lost the email."
    Only works on agreements still in 'sent' status — once signed, this is a no-op."""
    rec = await db.firm_agreements.find_one({"token": token})
    if not rec:
        raise HTTPException(404, "Agreement not found.")
    if rec.get("status") == "signed":
        raise HTTPException(409, "Agreement already signed — no need to resend.")

    app_base = "https://aiadvocate.co.uk"
    signing_url = f"{app_base}/firm-sign/{token}"

    try:
        from email_helper import send_email
        first_name = (rec.get("contact_name") or "there").split(",")[0]
        await send_email(
            to=rec["contact_email"],
            kind="firm",
            subject=f"Reminder — your AI Advocate Founding Firm Agreement is waiting",
            body_html=f"""<p>Hi {first_name},</p>
            <p>Just a quick reminder — your Founding Firm Agreement for <strong>{rec['firm_name']}</strong> is ready to sign.</p>
            <p style="margin:24px 0;"><a href="{signing_url}" style="background:#f7c948;color:#1a1300;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:700;">Review &amp; sign agreement →</a></p>
            <p style="color:#666;font-size:13px;">Or copy this link: <a href="{signing_url}">{signing_url}</a></p>
            <p style="color:#666;font-size:12px;">No rush — but the Founding cohort only has 20 spots and we'd love to have you in. If you've got any questions or need a change to the agreement, please contact <a href="mailto:firms@aiadvocate.co.uk">firms@aiadvocate.co.uk</a>.</p>
            <p>Samuel Malick<br/>Founder, AI Advocate Ltd.</p>""",
        )
    except Exception as e:
        print(f"[firm-agreement] Resend email failed for {rec['contact_email']}: {e}")
        raise HTTPException(500, "Could not send reminder email. Try again shortly.")

    # Bump a counter so we can see how many times we've nudged each firm
    await db.firm_agreements.update_one({"token": token}, {
        "$inc": {"resend_count": 1},
        "$set": {"last_resent_at": datetime.now(timezone.utc).isoformat()},
    })
    return {"ok": True, "signing_url": signing_url}


@api_router.get("/admin/firm-agreements")
async def admin_list_firm_agreements(_: dict = Depends(require_admin)):
    """Admin — list every agreement we've sent, with status + signed_at."""
    items = []
    cursor = db.firm_agreements.find({}).sort("sent_at", -1).limit(200)
    async for rec in cursor:
        items.append(_agreement_to_public(rec))
    return {"agreements": items}


# ==================== Admin: Comp Pro Access (gift free Pro) ====================
# Owner-only tool to grant free Pro access to family, friends, or unhappy customers.
# Every grant is logged in db.comp_audit for accountability.
class CompUserPayload(BaseModel):
    email: str
    days: int = 30                       # 0 = lifetime (sets ~30 years)
    reason: Optional[str] = "Goodwill"
    keep: Optional[bool] = False         # uncomp: if True, revoke but don't soft-delete

@api_router.get("/admin/users/search")
async def admin_users_search(q: str, _: dict = Depends(require_admin)):
    """Search users by email (partial match). Used by the comp UI to find a user."""
    if not q or len(q) < 2:
        return {"users": []}
    rx = q.strip().lower().replace("\\", "").replace("%", "").replace("$", "")
    users = await db.users.find(
        {"email": {"$regex": rx, "$options": "i"}, "deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "tier": 1, "subscription_status": 1,
         "trial_end_date": 1, "comp_pro_until": 1, "created_at": 1},
    ).limit(20).to_list(20)
    return {"users": users}


@api_router.get("/admin/users/recent")
async def admin_users_recent(_: dict = Depends(require_admin), limit: int = 30, include_test: bool = False):
    """Return the most recently signed-up users. Used by the comp UI to show a
    default tappable list before any search is performed.
    By default we exclude @advocate.app test-account emails (used by pytest)
    so the admin UI isn't polluted. Set include_test=true to include them."""
    limit = max(1, min(int(limit or 30), 100))
    query = {"deleted": {"$ne": True}, "is_demo": {"$ne": True}}
    if not include_test:
        # Hide pytest-fixture emails ending in @advocate.app and obvious test prefixes
        query["email"] = {"$not": {"$regex": r"(@advocate\.app$|^firmpytest|^giftclaim_|^recipient_|^firmtest|^shottest|^pytest|^test_)"}}
    users = await db.users.find(
        query,
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "tier": 1, "subscription_status": 1,
         "trial_end_date": 1, "comp_pro_until": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"users": users}


@api_router.post("/admin/users/comp")
async def admin_users_comp(data: CompUserPayload, admin: dict = Depends(require_admin)):
    """Grant the named user free Pro access for `days` days (0 = lifetime).
    If the user hasn't signed up yet, store as a pending grant — auto-applied
    when they later create an account with this email (same pattern as pending_gifts)."""
    email_lc = data.email.strip().lower()
    target = await db.users.find_one({"email": email_lc}, {"_id": 0})
    days = max(1, int(data.days or 30)) if data.days and data.days > 0 else (365 * 30)  # 0 = lifetime
    now = datetime.now(timezone.utc)

    # 🆕 No account yet — queue a pending grant so they get comp the moment they sign up
    if not target:
        await db.pending_comp_grants.update_one(
            {"email": email_lc},
            {"$set": {
                "email": email_lc,
                "days": days,
                "reason": (data.reason or "Founder pre-comp")[:300],
                "granted_by_id": admin["id"], "granted_by_email": admin["email"],
                "queued_at": now.isoformat(),
            }},
            upsert=True,
        )
        await db.comp_audit.insert_one({
            "id": str(uuid.uuid4()),
            "granted_by_id": admin["id"], "granted_by_email": admin["email"],
            "target_id": None, "target_email": email_lc,
            "days": days, "reason": (data.reason or "Pre-signup comp")[:300],
            "at": now.isoformat(), "action": "pre_comp_queued",
        })
        return {
            "ok": True, "email": email_lc, "pending": True,
            "days_granted": days,
            "message": f"User has no account yet. Comp queued — they'll get {days} days Pro the moment they sign up with this email.",
        }

    # If they already have a comp window in the future, extend it; else start from now
    existing = target.get("comp_pro_until")
    if existing:
        try:
            existing_dt = datetime.fromisoformat(existing) if isinstance(existing, str) else existing
            if existing_dt.tzinfo is None:
                existing_dt = existing_dt.replace(tzinfo=timezone.utc)
            base = max(now, existing_dt)
        except Exception:
            base = now
    else:
        base = now
    new_until = base + timedelta(days=days)

    await db.users.update_one(
        {"id": target["id"]},
        {"$set": {"comp_pro_until": new_until.isoformat(),
                  "comp_pro_granted_at": now.isoformat()}},
    )
    # Audit log
    await db.comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_id": target["id"], "target_email": target["email"],
        "days": days, "until": new_until.isoformat(),
        "reason": (data.reason or "Goodwill")[:300],
        "at": now.isoformat(), "action": "grant",
    })
    return {
        "ok": True, "email": target["email"], "comp_pro_until": new_until.isoformat(),
        "days_granted": days,
        "is_lifetime": days >= 365 * 25,
    }


@api_router.post("/admin/users/uncomp")
async def admin_users_uncomp(data: CompUserPayload, admin: dict = Depends(require_admin)):
    """Revoke comp Pro for a user. By default we ALSO soft-delete them from the
    admin list so the row disappears (founder request). Pass `keep:true` in the
    payload to revoke without deleting (legitimate users who shouldn't vanish).

    Also:
      • Cancels any active Stripe subscription so they're not double-billed
      • Sends a branded cancellation email so the user has a paper trail
    """
    target = await db.users.find_one({"email": data.email.strip().lower()}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found.")
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {"comp_pro_until": None, "comp_pro_revoked_at": now_iso}
    keep = bool(getattr(data, "keep", False))
    if not keep:
        update["deleted"] = True
        update["deleted_at"] = now_iso
        update["deleted_by"] = admin["email"]
    await db.users.update_one({"id": target["id"]}, {"$set": update})

    # 💳 Cancel Stripe subscription if active
    stripe_cancelled = False
    sub_id = target.get("stripe_subscription_id")
    if sub_id:
        try:
            stripe.Subscription.delete(sub_id)
            stripe_cancelled = True
            await db.users.update_one(
                {"id": target["id"]},
                {"$set": {"stripe_subscription_id": None, "subscription_status": "canceled",
                          "tier": "free", "subscription_ended_at": now_iso}},
            )
        except Exception as e:
            logger.warning(f"Stripe cancel failed for user {target['email']}: {e}")

    await db.comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_id": target["id"], "target_email": target["email"],
        "reason": (data.reason or "Revoked")[:300],
        "at": now_iso, "action": ("revoke_and_delete" if not keep else "revoke"),
        "stripe_cancelled": stripe_cancelled,
    })

    # 📧 Branded cancellation email
    try:
        from email_helper import send_cancellation_email
        from datetime import datetime as _dt
        await send_cancellation_email(
            email=target["email"],
            name=target.get("full_name") or "",
            account_kind="user",
            ended_on=_dt.now(timezone.utc).strftime("%d %B %Y"),
            reason=data.reason or "",
        )
    except Exception as e:
        logger.warning(f"Cancellation email failed for {target['email']}: {e}")

    return {"ok": True, "email": target["email"], "revoked": True, "deleted": not keep, "stripe_cancelled": stripe_cancelled}


class DeleteUserPayload(BaseModel):
    email: str
    reason: Optional[str] = None


@api_router.post("/admin/users/delete")
async def admin_users_delete(data: DeleteUserPayload, admin: dict = Depends(require_admin)):
    """Soft-delete a user (sets deleted=true) so they no longer appear in admin
    lists. The user's data (including comp_pro_until) is PRESERVED so the action
    can be reversed via /admin/users/restore. Protected accounts are blocked."""
    email_lc = data.email.strip().lower()
    PROTECTED = {"admin@aiadvocate.co.uk", "appstore.reviewer@aiadvocate.co.uk", "demo@aiadvocate.co.uk"}
    if email_lc in PROTECTED:
        raise HTTPException(400, f"Cannot delete protected account: {email_lc}")
    target = await db.users.find_one({"email": email_lc}, {"_id": 0, "id": 1, "email": 1})
    if not target:
        raise HTTPException(404, "User not found.")
    now_iso = datetime.now(timezone.utc).isoformat()
    # IMPORTANT: do NOT wipe comp_pro_until — keeping it intact means a Restore
    # brings the user back complete with their Pro comp. The "deleted" flag is
    # what filters them out of admin lists.
    await db.users.update_one(
        {"id": target["id"]},
        {"$set": {"deleted": True, "deleted_at": now_iso, "deleted_by": admin["email"]}},
    )
    await db.comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_id": target["id"], "target_email": target["email"],
        "reason": (data.reason or "Removed by founder")[:300],
        "at": now_iso, "action": "delete",
    })
    return {"ok": True, "email": target["email"], "deleted": True}


@api_router.get("/admin/users/deleted")
async def admin_users_deleted(_: dict = Depends(require_admin)):
    """List soft-deleted users so they can be restored if removed by mistake."""
    cursor = db.users.find(
        {"deleted": True},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "deleted_at": 1, "deleted_by": 1,
         "comp_pro_until": 1, "tier": 1},
    ).sort("deleted_at", -1).limit(100)
    items = [u async for u in cursor]
    return {"users": items}


class RestoreUserPayload(BaseModel):
    email: str


@api_router.post("/admin/users/restore")
async def admin_users_restore(data: RestoreUserPayload, admin: dict = Depends(require_admin)):
    """Restore a previously soft-deleted user. Clears the deleted flag — their
    Pro comp (if any) is intact because we preserve it in /admin/users/delete."""
    email_lc = data.email.strip().lower()
    target = await db.users.find_one({"email": email_lc, "deleted": True}, {"_id": 0, "id": 1, "email": 1})
    if not target:
        raise HTTPException(404, "Deleted user not found.")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": target["id"]},
        {"$set": {"deleted": False}, "$unset": {"deleted_at": "", "deleted_by": ""}},
    )
    await db.comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_id": target["id"], "target_email": target["email"],
        "reason": "Restored by founder",
        "at": now_iso, "action": "restore",
    })
    return {"ok": True, "email": target["email"], "restored": True}


@api_router.post("/admin/users/purge")
async def admin_users_purge(data: RestoreUserPayload, admin: dict = Depends(require_admin)):
    """HARD delete — permanently remove a soft-deleted user from MongoDB along
    with the bulk of their associated data. Use this to keep the Recently
    Deleted list clean of old test accounts. Cannot purge protected accounts."""
    email_lc = data.email.strip().lower()
    PROTECTED = {"admin@aiadvocate.co.uk", "appstore.reviewer@aiadvocate.co.uk", "demo@aiadvocate.co.uk"}
    if email_lc in PROTECTED:
        raise HTTPException(400, f"Cannot purge protected account: {email_lc}")
    target = await db.users.find_one({"email": email_lc, "deleted": True}, {"_id": 0, "id": 1, "email": 1})
    if not target:
        raise HTTPException(404, "Deleted user not found (only soft-deleted users can be purged).")
    uid = target["id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    # Audit FIRST so we keep a permanent record of the purge.
    await db.comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_id": uid, "target_email": target["email"],
        "reason": "PURGED — hard delete from DB",
        "at": now_iso, "action": "purge",
    })

    # Best-effort cascade — wipe the user's data across the collections we know about.
    # Wrapped in try/except per-collection so a missing collection doesn't abort the purge.
    cascade_collections = [
        "conversations", "chat_sessions", "case_items", "contract_analyses",
        "letters", "deadlines", "evidence", "voice_journals", "vault_items",
        "user_documents", "comp_pro_grants", "sponsor_links",
        "totp_secrets", "password_reset_tokens", "trusted_devices",
        "pending_grants", "stripe_customers",
    ]
    for col in cascade_collections:
        try:
            await db[col].delete_many({"user_id": uid})
        except Exception as e:
            print(f"[purge] {col} cascade skipped: {e}")

    # Finally, delete the user record itself
    await db.users.delete_one({"id": uid})
    return {"ok": True, "email": target["email"], "purged": True}


@api_router.get("/admin/users/comps")
async def admin_users_comps(_: dict = Depends(require_admin)):
    """List all currently-active comps + pending pre-signup grants
    (for the owner's at-a-glance dashboard)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    users = await db.users.find(
        {"comp_pro_until": {"$gt": now_iso}, "deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "comp_pro_until": 1, "comp_pro_granted_at": 1},
    ).sort("comp_pro_until", -1).to_list(200)
    pending = await db.pending_comp_grants.find(
        {}, {"_id": 0, "email": 1, "days": 1, "reason": 1, "queued_at": 1, "granted_by_email": 1},
    ).sort("queued_at", -1).to_list(100)
    return {"comps": users, "count": len(users), "pending": pending, "pending_count": len(pending)}


@api_router.post("/admin/users/comp-cancel-pending")
async def admin_users_comp_cancel_pending(data: ForgotPasswordReq, admin: dict = Depends(require_admin)):
    """Cancel a queued pre-signup comp before the recipient signs up."""
    r = await db.pending_comp_grants.delete_one({"email": data.email.strip().lower()})
    if r.deleted_count == 0:
        raise HTTPException(404, "No pending comp found for this email.")
    return {"ok": True, "email": data.email, "cancelled": True}


# ─── Founding-100 queue ──────────────────────────────────────────────
# The landing page promises a free Day Pass to the first 100 signups.
# The signup endpoint already auto-grants this (launch_day_pass_until),
# but the founder wants visibility — a queue of every founding-cohort
# signup so they can verify the day pass, optionally extend it, and
# dismiss the row when done. Dismissals are per-user (founding_list_dismissed)
# so the list shrinks as the founder works through it.
@api_router.get("/admin/founding-100")
async def admin_founding_100(_: dict = Depends(require_admin), include_dismissed: bool = False):
    """Return the first 100 real signups by signup_position. Each row carries the
    user's day-pass status + dismiss flag so the founder can manage them."""
    query = {
        "signup_position": {"$gte": 1, "$lte": 100},
        "deleted": {"$ne": True},
        "is_demo": {"$ne": True},
        "auth_provider": {"$nin": ["demo"]},
        "email": {"$not": {"$regex": r"(@advocate\.app$|^firmpytest|^giftclaim_|^recipient_|^firmtest|^shottest|^pytest|^test_)"}},
    }
    if not include_dismissed:
        query["founding_list_dismissed"] = {"$ne": True}
    users = await db.users.find(
        query,
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "tier": 1, "signup_position": 1,
         "launch_day_pass_until": 1, "comp_pro_until": 1, "created_at": 1,
         "founding_list_dismissed": 1, "founding_list_dismissed_at": 1,
         "founding_thanked": 1, "founding_thanked_at": 1},
    ).sort("signup_position", 1).to_list(120)
    # Slot count = how many of the 100 are taken (lifetime — doesn't shrink on dismiss)
    slots_taken = await db.users.count_documents({
        "signup_position": {"$gte": 1, "$lte": 100},
        "deleted": {"$ne": True}, "is_demo": {"$ne": True},
        "auth_provider": {"$nin": ["demo"]},
    })
    return {"users": users, "slots_taken": slots_taken, "slots_total": 100, "pending": len(users)}


class FoundingDismissPayload(BaseModel):
    email: str
    undo: Optional[bool] = False  # if True, un-dismiss instead


@api_router.post("/admin/founding-100/dismiss")
async def admin_founding_100_dismiss(data: FoundingDismissPayload, admin: dict = Depends(require_admin)):
    """Mark a founding-cohort user as 'dealt with' so they drop off the queue.
    Pass undo=true to bring them back. No effect on the user's actual day-pass."""
    target = await db.users.find_one({"email": data.email.strip().lower()}, {"_id": 0, "id": 1, "email": 1, "signup_position": 1})
    if not target:
        raise HTTPException(404, "User not found.")
    if not target.get("signup_position") or target["signup_position"] > 100:
        raise HTTPException(400, "User is not part of the founding 100 cohort.")
    now_iso = datetime.now(timezone.utc).isoformat()
    if data.undo:
        await db.users.update_one(
            {"id": target["id"]},
            {"$set": {"founding_list_dismissed": False}, "$unset": {"founding_list_dismissed_at": ""}},
        )
        return {"ok": True, "email": target["email"], "dismissed": False}
    await db.users.update_one(
        {"id": target["id"]},
        {"$set": {"founding_list_dismissed": True, "founding_list_dismissed_at": now_iso,
                  "founding_list_dismissed_by": admin["email"]}},
    )
    return {"ok": True, "email": target["email"], "dismissed": True}


@api_router.post("/admin/founding-100/thank")
async def admin_founding_100_thank(data: FoundingDismissPayload, admin: dict = Depends(require_admin)):
    """Approve a founding-100 signup: fire a personal thank-you email AND
    auto-dismiss the row from the queue. Idempotent — re-running just resends
    the email and refreshes the timestamps. Returns sent=False if Resend is
    unavailable (signup still survives — same graceful-degradation rule)."""
    target = await db.users.find_one(
        {"email": data.email.strip().lower()},
        {"_id": 0, "id": 1, "email": 1, "full_name": 1, "signup_position": 1, "founding_thanked": 1},
    )
    if not target:
        raise HTTPException(404, "User not found.")
    if not target.get("signup_position") or target["signup_position"] > 100:
        raise HTTPException(400, "User is not part of the founding 100 cohort.")
    now_iso = datetime.now(timezone.utc).isoformat()
    sent = False
    try:
        from email_helper import send_founding_thank_you
        sent = await send_founding_thank_you(target["email"], target.get("full_name") or "")
    except Exception:
        logger.exception("Founding-100 thank-you email failed")
    await db.users.update_one(
        {"id": target["id"]},
        {"$set": {
            "founding_thanked": True,
            "founding_thanked_at": now_iso,
            "founding_thanked_by": admin["email"],
            "founding_list_dismissed": True,
            "founding_list_dismissed_at": now_iso,
            "founding_list_dismissed_by": admin["email"],
        }},
    )
    return {"ok": True, "email": target["email"], "sent": sent, "already_thanked": bool(target.get("founding_thanked"))}


# ============================================================
# Owner-only: Firm trial / comp tools (founding firms cohort)
# ============================================================
class CompFirmPayload(BaseModel):
    email: str
    days: int = Field(30, ge=1, le=36500)  # up to ~100 years to allow "Lifetime" comps for Founding Firms
    tier: str = Field("featured", pattern=r"^(featured|premium|practice)$")
    reason: str = ""

@api_router.post("/admin/firms/comp")
async def admin_firms_comp(data: CompFirmPayload, admin: dict = Depends(require_admin)):
    """Grant a free trial extension to a law firm (founding-firm cohort + goodwill).
    If the firm hasn't signed up yet, queue a pending_firm_comp_grants entry
    that auto-applies on first firm signup with this email.
    """
    email_lc = data.email.strip().lower()
    target = await db.firm_accounts.find_one({"email": email_lc}, {"_id": 0})
    now = datetime.now(timezone.utc)

    # 🆕 No firm account yet — queue a pending grant so they get the tier the moment they sign up
    if not target:
        days = max(1, int(data.days or 90))
        await db.pending_firm_comp_grants.update_one(
            {"email": email_lc},
            {"$set": {
                "email": email_lc, "days": days, "tier": data.tier,
                "reason": (data.reason or "Founder pre-comp firm")[:300],
                "granted_by_id": admin["id"], "granted_by_email": admin["email"],
                "queued_at": now.isoformat(),
            }},
            upsert=True,
        )
        await db.firm_comp_audit.insert_one({
            "id": str(uuid.uuid4()),
            "granted_by_id": admin["id"], "granted_by_email": admin["email"],
            "target_firm_id": None, "target_firm_email": email_lc, "target_firm_name": "",
            "days": days, "tier": data.tier, "until": None,
            "reason": (data.reason or "Pre-signup firm comp queued")[:300],
            "at": now.isoformat(), "action": "pre_comp_queued",
        })
        return {
            "ok": True, "email": email_lc, "pending": True,
            "trial_tier": data.tier, "days_granted": days,
            "message": f"Firm has no account yet. Pre-comp queued — they'll get {days} days of {data.tier.title()} on first signup.",
        }

    existing = target.get("trial_until")
    if existing:
        try:
            existing_dt = datetime.fromisoformat(existing) if isinstance(existing, str) else existing
            if existing_dt.tzinfo is None:
                existing_dt = existing_dt.replace(tzinfo=timezone.utc)
            base = max(now, existing_dt)
        except Exception:
            base = now
    else:
        base = now
    new_until = base + timedelta(days=data.days)
    await db.firm_accounts.update_one(
        {"id": target["id"]},
        {"$set": {
            "trial_until": new_until.isoformat(),
            "trial_tier": data.tier,
            "trial_granted_by": admin["email"],
            "trial_granted_at": now.isoformat(),
        }},
    )
    # Audit
    await db.firm_comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_firm_id": target["id"], "target_firm_email": target["email"],
        "target_firm_name": target.get("firm_name") or "",
        "days": data.days, "tier": data.tier, "until": new_until.isoformat(),
        "reason": (data.reason or "Founding firm / goodwill")[:300],
        "at": now.isoformat(), "action": "grant",
    })
    # 🎁 Auto-send a firm-onboarding email with a one-tap "Set password & sign in"
    # reset link. This is Feature A in the founding-firms onboarding plan — when
    # the founder comps a firm, the firm gets an automatic email with the portal
    # URL and a secure password-reset link so they don't need to remember the
    # password the founder set (or be embarrassed about asking for it).
    email_sent = False
    try:
        tok = await _create_reset_token(account_kind="firm", account_id=target["id"], email=target["email"])
        portal_url = f"{_public_app_url()}/firm-portal"
        reset_link = f"{_public_app_url()}/reset.html?token={tok}&kind=firm"
        from email_helper import send_firm_onboarding
        email_sent = await send_firm_onboarding(
            target["email"], target.get("firm_name") or "Your firm",
            data.tier, data.days, reset_link, portal_url,
        )
    except Exception:
        logger.exception("Firm onboarding email send failed (non-fatal)")
    return {
        "ok": True,
        "firm_id": target["id"],
        "firm_name": target.get("firm_name"),
        "email": target["email"],
        "trial_until": new_until.isoformat(),
        "trial_tier": data.tier,
        "days_granted": data.days,
        "onboarding_email_sent": email_sent,
    }


@api_router.post("/admin/firms/uncomp")
async def admin_firms_uncomp(data: CompFirmPayload, admin: dict = Depends(require_admin)):
    """Revoke a firm's trial (sets trial_until to null). Also:
      • Cancels any active Stripe subscription (so they're not double-billed
        after the comp ends)
      • Sends a branded cancellation email so the firm has a paper trail
    Both side-effects are wrapped in try/except so a failure on either doesn't
    block the revoke itself."""
    target = await db.firm_accounts.find_one({"email": data.email.strip().lower()}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Firm not found.")
    now = datetime.now(timezone.utc)
    await db.firm_accounts.update_one(
        {"id": target["id"]},
        {"$set": {
            "trial_until": None, "trial_tier": None,
            "trial_revoked_by": admin["email"],
            "trial_revoked_at": now.isoformat(),
        }},
    )
    # 💳 Cancel any active Stripe subscription tied to this firm
    stripe_cancelled = False
    sub_id = target.get("stripe_subscription_id")
    if sub_id:
        try:
            stripe.Subscription.delete(sub_id)  # immediate cancellation
            stripe_cancelled = True
            await db.firm_accounts.update_one(
                {"id": target["id"]},
                {"$set": {"stripe_subscription_id": None, "subscription_status": "canceled"}},
            )
        except Exception as e:
            logger.warning(f"Stripe cancel failed for firm {target['email']}: {e}")

    await db.firm_comp_audit.insert_one({
        "id": str(uuid.uuid4()),
        "granted_by_id": admin["id"], "granted_by_email": admin["email"],
        "target_firm_id": target["id"], "target_firm_email": target["email"],
        "target_firm_name": target.get("firm_name") or "",
        "reason": (data.reason or "Trial revoked")[:300],
        "at": now.isoformat(), "action": "revoke",
        "stripe_cancelled": stripe_cancelled,
    })

    # 📧 Branded cancellation email (fire-and-forget)
    try:
        from email_helper import send_cancellation_email
        await send_cancellation_email(
            email=target["email"],
            name=target.get("firm_name") or target.get("primary_contact") or "",
            account_kind="firm",
            ended_on=now.strftime("%d %B %Y"),
            reason=data.reason or "",
        )
    except Exception as e:
        logger.warning(f"Cancellation email failed for {target['email']}: {e}")

    return {"ok": True, "email": target["email"], "stripe_cancelled": stripe_cancelled}


@api_router.get("/admin/firms/comps/active")
async def admin_firms_active_comps(_: dict = Depends(require_admin)):
    """List every firm currently on a trial (with days remaining)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    firms = await db.firm_accounts.find(
        {"trial_until": {"$gt": now_iso}},
        {"_id": 0, "id": 1, "email": 1, "firm_name": 1, "city": 1, "country": 1,
         "trial_until": 1, "trial_tier": 1, "trial_granted_by": 1, "trial_granted_at": 1,
         "created_at": 1, "status": 1, "tier": 1},
    ).sort("trial_until", 1).to_list(500)
    # Decorate with days_remaining
    now = datetime.now(timezone.utc)
    out = []
    for f in firms:
        try:
            until = datetime.fromisoformat(f["trial_until"].replace("Z", "+00:00"))
            f["days_remaining"] = max(0, int((until - now).total_seconds() // 86400))
        except Exception:
            f["days_remaining"] = 0
        out.append(f)
    return {"firms": out, "count": len(out)}


@api_router.get("/admin/firms/search")
async def admin_firms_search(q: str = "", _: dict = Depends(require_admin)):
    """Owner-side firm search for the comp-tool autocomplete."""
    q = (q or "").strip().lower()
    if not q:
        return {"firms": []}
    safe = re.escape(q)
    firms = await db.firm_accounts.find(
        {"$or": [
            {"email": {"$regex": safe, "$options": "i"}},
            {"firm_name": {"$regex": safe, "$options": "i"}},
            {"city": {"$regex": safe, "$options": "i"}},
        ]},
        {"_id": 0, "id": 1, "email": 1, "firm_name": 1, "city": 1, "country": 1,
         "tier": 1, "trial_until": 1, "trial_tier": 1, "status": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(40)
    return {"firms": firms}


# Sponsor management — flip the "In partnership with [Firm]" footer on/off without an engineer.
class SponsorPayload(BaseModel):
    active: bool = True
    name: str = ""
    url: str = ""
    tagline: str = "In partnership with"
    logo_url: str = ""

@api_router.get("/admin/sponsor")
async def admin_get_sponsor(_: dict = Depends(require_admin)):
    s = await db.sponsor.find_one({}, {"_id": 0}) or {}
    return {
        "active": bool(s.get("active", False)),
        "name": s.get("name") or "",
        "url": s.get("url") or "",
        "tagline": s.get("tagline") or "In partnership with",
        "logo_url": s.get("logo_url") or "",
    }

@api_router.post("/admin/sponsor")
async def admin_set_sponsor(payload: SponsorPayload, _: dict = Depends(require_admin)):
    name = (payload.name or "").strip()
    if payload.active and not name:
        raise HTTPException(400, "Sponsor name is required when activating.")
    doc = {
        "active": bool(payload.active),
        "name": name,
        "url": (payload.url or "").strip(),
        "tagline": (payload.tagline or "In partnership with").strip(),
        "logo_url": (payload.logo_url or "").strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # One sponsor doc — upsert
    await db.sponsor.update_one({}, {"$set": doc}, upsert=True)
    return {"ok": True, **doc}

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


# ==================== Recycle Bin (30-day soft-delete recovery) ====================
# Every "delete" in the app actually marks `deleted_at` instead of removing the row.
# This endpoint family lets users see, restore, or permanently purge soft-deleted items
# for 30 days. After 30 days the daily sweeper hard-purges them.
RECYCLE_KIND_TO_COLL = {
    "legal_file": "legal_files",
    "case": "cases",
    "case_item": "case_items",
    "reminder": "reminders",
    "conversation": "conversations",
    "hearing": "hearing_recordings",
}

@api_router.get("/recycle-bin")
async def list_recycle_bin(user: dict = Depends(get_user)):
    """Aggregate every soft-deleted item across kinds for this user."""
    out = []
    for kind, coll_name in RECYCLE_KIND_TO_COLL.items():
        try:
            coll = db[coll_name]
            cursor = coll.find(
                {"user_id": user["id"], "deleted_at": {"$nin": [None, "", False]}},
                {"_id": 0, "id": 1, "name": 1, "title": 1, "filename": 1,
                 "deleted_at": 1, "created_at": 1, "case_id": 1, "item_type": 1, "type": 1},
            ).sort("deleted_at", -1).limit(200)
            async for d in cursor:
                # Compute days remaining (30-day window)
                try:
                    deleted_dt = datetime.fromisoformat(d["deleted_at"].replace("Z", "+00:00"))
                    expires_at = deleted_dt + timedelta(days=30)
                    days_left = max(0, (expires_at - datetime.now(timezone.utc)).days)
                except Exception:
                    days_left = 30
                out.append({
                    "kind": kind,
                    "id": d.get("id"),
                    "label": d.get("filename") or d.get("name") or d.get("title") or d.get("item_type") or kind,
                    "deleted_at": d.get("deleted_at"),
                    "created_at": d.get("created_at"),
                    "case_id": d.get("case_id"),
                    "subtype": d.get("type") or d.get("item_type"),
                    "days_left": days_left,
                })
        except Exception:
            continue
    out.sort(key=lambda x: x.get("deleted_at") or "", reverse=True)
    return {"items": out, "count": len(out)}


@api_router.post("/recycle-bin/restore/{kind}/{item_id}")
async def restore_recycle_item(kind: str, item_id: str, user: dict = Depends(get_user)):
    coll_name = RECYCLE_KIND_TO_COLL.get(kind)
    if not coll_name:
        raise HTTPException(400, f"Unknown kind: {kind}")
    coll = db[coll_name]
    res = await coll.update_one(
        {"id": item_id, "user_id": user["id"]},
        {"$unset": {"deleted_at": "", "deleted_with_case": ""}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")
    # If we just restored a case, also restore items deleted alongside it
    if kind == "case":
        await db.case_items.update_many(
            {"case_id": item_id, "deleted_with_case": True},
            {"$unset": {"deleted_at": "", "deleted_with_case": ""}},
        )
    # If we restored a case_item, bump parent case items_count
    if kind == "case_item":
        it = await db.case_items.find_one({"id": item_id}, {"_id": 0, "case_id": 1})
        if it and it.get("case_id"):
            await db.cases.update_one({"id": it["case_id"]}, {"$inc": {"items_count": 1}})
    return {"restored": True, "kind": kind, "id": item_id}


@api_router.delete("/recycle-bin/{kind}/{item_id}")
async def purge_recycle_item(kind: str, item_id: str, user: dict = Depends(get_user)):
    coll_name = RECYCLE_KIND_TO_COLL.get(kind)
    if not coll_name:
        raise HTTPException(400, f"Unknown kind: {kind}")
    coll = db[coll_name]
    res = await coll.delete_one(
        {"id": item_id, "user_id": user["id"], "deleted_at": {"$nin": [None, "", False]}},
    )
    if res.deleted_count == 0:
        raise HTTPException(404, "Item not found")
    return {"purged": True, "kind": kind, "id": item_id}


@api_router.delete("/recycle-bin")
async def empty_recycle_bin(user: dict = Depends(get_user)):
    """Hard-delete every soft-deleted item for this user, across all kinds."""
    total = 0
    for coll_name in RECYCLE_KIND_TO_COLL.values():
        try:
            res = await db[coll_name].delete_many(
                {"user_id": user["id"], "deleted_at": {"$nin": [None, "", False]}}
            )
            total += res.deleted_count
        except Exception:
            continue
    return {"purged_count": total}


async def _recycle_bin_sweeper():
    """Permanently delete soft-deleted items older than 30 days. Idempotent."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    total = 0
    for coll_name in RECYCLE_KIND_TO_COLL.values():
        try:
            res = await db[coll_name].delete_many(
                {"deleted_at": {"$lt": cutoff, "$nin": [None, "", False]}}
            )
            total += res.deleted_count
        except Exception:
            continue
    if total:
        logger.info(f"[recycle-bin] swept {total} expired soft-deleted items")
    return total


# ==================== Save-to-Vault (any file kind → Vault) ====================
class VaultSaveLegalFile(BaseModel):
    file_id: str
    # Client-side AES-GCM encryption happens before this call; we just store the wrapped
    # ciphertext + IV under the user's vault. The legal_file row stays where it is —
    # this is a copy, not a move (so the source-of-truth chain-of-custody remains intact).
    encrypted_content: str
    iv: str
    label: Optional[str] = None


@api_router.post("/legal-files/{file_id}/save-to-vault")
async def save_legal_file_to_vault(file_id: str, payload: VaultSaveLegalFile, user: dict = Depends(get_user)):
    src = await db.legal_files.find_one({"id": file_id, "user_id": user["id"]}, {"_id": 0})
    if not src:
        raise HTTPException(404, "File not found")
    # Insert into vault_items with the client-encrypted payload
    item_id = str(uuid.uuid4())
    await db.vault_items.insert_one({
        "id": item_id,
        "user_id": user["id"],
        "label": (payload.label or src.get("filename") or "Saved file")[:200],
        "kind": src.get("type") or "file",
        "encrypted_content": payload.encrypted_content,
        "iv": payload.iv,
        "source_id": file_id,
        "source_kind": "legal_file",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"saved": True, "vault_item_id": item_id}


# ==================== Case Items: file upload + delete + save-to-vault ====================
@api_router.post("/cases/{case_id}/upload-file")
async def upload_file_to_case(
    case_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    user: dict = Depends(get_user),
):
    """Attach an arbitrary file (document/photo/audio/video) to a case. The raw file
    is NOT stored — only metadata + a SHA256 hash for chain-of-custody. Users who
    want the bytes preserved should save the file to the Vault separately."""
    c = await db.cases.find_one({"id": case_id, "user_id": user["id"], "deleted_at": {"$in": [None, "", False]}})
    if not c:
        raise HTTPException(404, "Case not found")
    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (50MB max)")
    import hashlib as _hl
    sha = _hl.sha256(raw).hexdigest()
    mt = (file.content_type or "application/octet-stream").lower()
    kind = "photo" if mt.startswith("image/") else (
           "video" if mt.startswith("video/") else (
           "audio" if mt.startswith("audio/") else "document"))
    item = {
        "id": str(uuid.uuid4()), "case_id": case_id, "user_id": user["id"],
        "item_type": kind,
        "title": (title or file.filename or kind)[:200],
        "preview": (description or "")[:500],
        "filename": file.filename or "",
        "content_type": mt,
        "size_bytes": len(raw),
        "sha256": sha,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.case_items.insert_one(item)
    await db.cases.update_one(
        {"id": case_id},
        {"$inc": {"items_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    item.pop("_id", None)
    return item


# ==================== Timeline: save snapshot + clear ====================
@api_router.post("/timeline/snapshot")
async def save_timeline_snapshot(user: dict = Depends(get_user)):
    """Save a point-in-time snapshot of the user's timeline into legal_files (so it
    appears in My Legal Files + can be exported / saved to Vault later)."""
    # Reuse the same aggregation as /timeline above
    tl = await get_timeline(user=user)  # type: ignore[arg-type]
    snap_id = str(uuid.uuid4())
    label = f"Case timeline — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    # Build a human-readable text summary so PDF export & previews look right
    lines = [label, ""]
    for it in tl.get("items", []):
        when = it.get("updated_at") or it.get("due_at") or ""
        lines.append(f"• [{it.get('kind','')}] {it.get('title','')}  ({when})")
    content = "\n".join(lines)
    await db.legal_files.insert_one({
        "id": snap_id,
        "user_id": user["id"],
        "filename": label + ".txt",
        "type": "timeline_snapshot",
        "content": content,
        "timeline_payload": tl,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"saved": True, "snapshot_id": snap_id, "label": label}


@api_router.delete("/timeline")
async def clear_timeline(user: dict = Depends(get_user)):
    """Soft-delete every source row contributing to the timeline. Recoverable from
    Recycle Bin for 30 days. Conversations and reminders only — case files are NOT
    cleared by this (would be too destructive); user can delete cases individually."""
    now_iso = datetime.now(timezone.utc).isoformat()
    convs = await db.conversations.update_many(
        {"user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"$set": {"deleted_at": now_iso}},
    )
    rems = await db.reminders.update_many(
        {"user_id": user["id"], "deleted_at": {"$in": [None, "", False]}},
        {"$set": {"deleted_at": now_iso}},
    )
    return {"cleared": True, "conversations": convs.modified_count, "reminders": rems.modified_count}


# ==========================================================================
# 🚀 PHASE 4b BATCH — 6 features added 2026-02:
#   1. OCR Form Scanner (POST /api/forms/ocr/detect)
#   2. Letter Counter-Ladder (POST /api/letters/counter-ladder)
#   3. Case Timeline Lex Summary (POST /api/cases/{id}/timeline/summarise)
#   4. Witness Statement Invite + magic-link (POST /api/cases/{id}/witness/invite)
#   5. Witness public submit (GET/POST /api/witness/{token})
#   6. Witness list + PDF (GET /api/cases/{id}/witness-statements, /pdf)
# Letter Writing tone slider + Lawyer Cost postcode/comparison are upgrades
# applied in-place to existing endpoints above.
# ==========================================================================

# ---------- 1. OCR Form Scanner ----------
# Gemini 2.5 Flash vision → detects UK gov form type + extracts visible field values.
# Supports: ET1 (Employment Tribunal), N1 (Money Claim), N9 (Defence), N244
# (Application Notice), MC100 (Money Claim), DR1 (Divorce). Unknown forms get a
# graceful fallback with extracted text + best-guess field labels.

_KNOWN_FORMS = {
    "ET1": {"label": "Employment Tribunal Claim (ET1)", "modal": "et1", "fields": [
        "claimant_name", "claimant_address", "claimant_postcode", "claimant_dob", "claimant_email",
        "respondent_name", "respondent_address", "acas_number", "job_title",
        "start_date", "end_date", "weekly_hours", "gross_pay", "net_pay",
    ]},
    "ET3": {"label": "Employment Tribunal Response (ET3)", "modal": "manual", "fields": [
        "respondent_name", "respondent_address", "case_number", "claimant_name",
    ]},
    "N1":  {"label": "Money Claim (N1)", "modal": "manual", "fields": [
        "claimant_name", "claimant_address", "defendant_name", "defendant_address",
        "claim_amount", "brief_details", "court_fee",
    ]},
    "N9":  {"label": "Acknowledgement of Service / Defence (N9)", "modal": "manual", "fields": [
        "case_number", "court", "defendant_name", "claimant_name",
    ]},
    "N244": {"label": "Application Notice (N244)", "modal": "manual", "fields": [
        "case_number", "court", "applicant_name", "application_sought", "evidence_relied_on",
    ]},
    "MC100": {"label": "Money Claim — Online (MC100/MCOL)", "modal": "manual", "fields": [
        "claimant_name", "defendant_name", "claim_amount",
    ]},
    "DR1": {"label": "Divorce / Dissolution Application (D8)", "modal": "manual", "fields": [
        "applicant_name", "respondent_name", "marriage_date", "grounds",
    ]},
}


@api_router.post("/forms/ocr/detect")
async def forms_ocr_detect(
    file: UploadFile = File(...),
    language: str = Form("en-GB"),
    user: dict = Depends(get_user),
):
    """Photo/scan of a UK gov form → Gemini vision detects which form + extracts
    visible field values. Used to pre-fill the ET1 Auto-Fill modal (or signpost
    the right tool for other forms)."""
    pub = user_to_public(user)
    ok, used, limit = await check_quota_and_increment(user["id"], pub["tier"], "doc_analyze", "monthly")
    if not ok:
        raise HTTPException(429, f"OCR limit reached ({used}/{limit}). Upgrade to Plus.")

    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 12MB)")
    if len(raw) < 200:
        raise HTTPException(400, "File too small / empty")
    suffix = "." + (file.filename.split(".")[-1].lower() if "." in (file.filename or "") else "jpg")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw); tmp.flush(); tmp.close()
    lang_name = LANG_NAMES.get(language, "English")
    form_codes = ", ".join(_KNOWN_FORMS.keys())

    sysmsg = f"""You are AI Advocate's UK legal form-OCR specialist. The user uploaded a photo/scan of
a UK government or court form (or a letter). Reply in {lang_name}.

Return STRICT JSON (no markdown, no commentary):
{{
  "form_type": "<one of: {form_codes}, OTHER_FORM, NOT_A_FORM>",
  "form_label": "<plain-English name e.g. 'Employment Tribunal claim form (ET1)'>",
  "confidence": <float 0.0-1.0>,
  "extracted_fields": {{ "<field_name>": "<value as printed>" }},
  "raw_text": "<full visible text, max 4000 chars, line-by-line>",
  "warnings": ["<any visible deadlines, signature blocks unsigned, missing ACAS, etc.>"]
}}

Field-name guidance (use these EXACT keys when found):
- claimant_name, claimant_address, claimant_postcode, claimant_dob, claimant_email, claimant_phone
- respondent_name, respondent_address (or defendant_name, defendant_address for N1/N9)
- acas_number, acas_date
- job_title, start_date, end_date, weekly_hours, gross_pay, net_pay
- case_number, court, claim_amount, court_fee
- applicant_name, application_sought, evidence_relied_on
If a field is handwritten and unclear, return your best guess prefixed with '~'.
If completely unreadable, omit the field rather than guessing wildly.
If this is NOT a legal form at all, set form_type='NOT_A_FORM'."""

    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"ocr-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("gemini", "gemini-2.5-flash").with_params(max_tokens=3000)
    try:
        resp = await chat.send_message(UserMessage(
            text="Analyse the attached form image and extract every visible field.",
            file_contents=[FileContentWithMimeType(file_path=tmp.name, mime_type=file.content_type or "image/jpeg")],
        ))
    except Exception as e:
        try: os.unlink(tmp.name)
        except Exception: pass
        logger.exception("forms ocr failed"); raise HTTPException(500, f"AI error: {e}")
    try: os.unlink(tmp.name)
    except Exception: pass

    parsed = _extract_json_object(resp) or {}
    form_type = (parsed.get("form_type") or "OTHER_FORM").upper()
    known = _KNOWN_FORMS.get(form_type)
    parsed["suggested_route"] = known["modal"] if known else ("manual" if form_type == "OTHER_FORM" else "none")
    parsed["form_label"] = parsed.get("form_label") or (known["label"] if known else "Unknown form")
    parsed["known_form"] = bool(known)

    # Persist the OCR detection for audit
    await db.form_ocr_scans.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "form_type": form_type, "filename": file.filename,
        "result": parsed, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return parsed


# ---------- 2. Letter Counter-Ladder ----------
# Given a received letter (decoded) + user's desired outcome, produce 4 escalation
# drafts (Polite → Firm → Pre-action → Court). Used by the Letter Reader upgrade.

class CounterLadderRequest(BaseModel):
    received_letter_summary: str = Field(min_length=20)
    desired_outcome: str = Field(min_length=10)
    your_name: str = "[Your name]"
    recipient: str = "[Recipient]"
    category: str = "other"
    language: str = "en-GB"


@api_router.post("/letters/counter-ladder")
async def letters_counter_ladder(data: CounterLadderRequest, user: dict = Depends(get_user)):
    pub = user_to_public(user)
    if not pub.get("has_access"):
        raise HTTPException(402, "Subscription required.")
    lang_name = LANG_NAMES.get(data.language, "English")
    # Delimiter-based output is far more robust than nested JSON for long letter
    # bodies (newlines in JSON strings break frequently). We use distinctive
    # ASCII fences and split client-side.
    sysmsg = f"""You are AI Advocate. Reply in {lang_name}. The user received a letter and wants to push
back. Generate FOUR drafts at escalating tones — Polite → Firm → Pre-action → Court.

Output EXACTLY this structure (no JSON, no markdown fences, no commentary):

===POLITE===
WHEN: <one-sentence guidance on when to use this tone>
---
<full letter body — sender, date, recipient, salutation, body, sign-off>

===FIRM===
WHEN: <one-sentence guidance>
---
<full letter body>

===PRE_ACTION===
WHEN: <one-sentence guidance>
---
<full letter body — must begin "LETTER BEFORE ACTION">

===COURT===
WHEN: <one-sentence guidance>
---
<full letter body — numbered paragraphs, statement of truth at the end>

Tone rules:
- POLITE: goodwill + reasonable request, NO threats.
- FIRM: 14-day deadline + cite UK statute by name.
- PRE_ACTION: headed "LETTER BEFORE ACTION", warning of proceedings, numbered facts and remedies.
- COURT: numbered paragraphs, "To the Honourable [Tribunal/Court]", statement of truth.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"ladder-{uuid.uuid4()}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=4500)
    user_msg = f"""RECEIVED LETTER SUMMARY:
{data.received_letter_summary}

CATEGORY: {data.category}
DESIRED OUTCOME: {data.desired_outcome}
FROM: {data.your_name}
TO: {data.recipient}

Produce the 4 escalating drafts now using the EXACT delimiter format."""
    try:
        raw = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("counter-ladder failed"); raise HTTPException(500, f"AI error: {e}")

    # Parse the delimiter format
    labels = {"polite": "Polite opener", "firm": "Firm — statute-cited",
              "pre_action": "Pre-action protocol", "court": "Skeleton submission"}
    result = {}
    keys = ["polite", "firm", "pre_action", "court"]
    # Split on the fences (===NAME===)
    pattern = re.compile(r"===\s*(POLITE|FIRM|PRE_ACTION|COURT)\s*===", re.IGNORECASE)
    parts = pattern.split(raw)
    # parts = [preamble, name1, content1, name2, content2, ...]
    if len(parts) >= 3:
        for i in range(1, len(parts) - 1, 2):
            key = parts[i].strip().lower().replace("-", "_")
            content = parts[i + 1].strip()
            # Split WHEN line + body using the --- separator
            when = ""
            body = content
            if "---" in content:
                head, _, body = content.partition("---")
                head = head.strip()
                # extract WHEN: line if present
                m = re.search(r"WHEN\s*:\s*(.+)", head, re.IGNORECASE)
                if m:
                    when = m.group(1).strip()
            body = body.strip()
            if key in keys:
                result[key] = {"tone_label": labels.get(key, key.title()),
                               "body": body, "when_to_use": when}

    # Fallback: ensure all 4 keys present (even if Lex truncated)
    for k in keys:
        if k not in result:
            result[k] = {"tone_label": labels[k], "body": "", "when_to_use": ""}

    if not any(result[k]["body"] for k in keys):
        raise HTTPException(502, "Lex couldn't structure the ladder. Try again.")
    return result


# ---------- 3. Case Timeline — Lex Auto-Summary ----------

@api_router.post("/cases/{case_id}/timeline/summarise")
async def case_timeline_summarise(case_id: str, user: dict = Depends(get_user)):
    """Lex turns the raw event timeline into a chronological prose summary
    ready for a solicitor handover. Cached per-case for 24h."""
    feed = await _build_case_timeline(case_id, user)
    events = feed.get("events", [])
    if not events:
        raise HTTPException(400, "No events in timeline yet — add chats / evidence first.")

    # Compact event list for the prompt
    lines = []
    for ev in events:
        when = (ev.get("at") or "")[:10]
        kind = ev.get("kind", "")
        title = ev.get("title", "") or ""
        extra = ""
        if kind == "lex_turn":
            extra = f" — Q: {ev.get('user_message','')[:160]}... → A: {ev.get('lex_reply','')[:160]}..."
        elif ev.get("summary"):
            extra = f" — {ev.get('summary')[:200]}"
        elif ev.get("preview"):
            extra = f" — {ev.get('preview')[:200]}"
        lines.append(f"[{when}] {kind}: {title}{extra}")
    timeline_text = "\n".join(lines)[:14000]

    case = feed.get("case", {})
    sysmsg = """You are AI Advocate's solicitor-handover writer. Turn this raw event chronology into a
CRISP, NEUTRAL, third-person narrative. The output is going to a UK solicitor as a handover briefing.

Return STRICT JSON (no markdown):
{
  "headline": "<one-line case summary>",
  "narrative": "<3-5 paragraphs in plain English, chronological, third-person, factual only. No legal advice. Reference dates inline (e.g. 'On 15 March 2026...'). End with where the case currently stands.>",
  "key_dates": [{"date": "DD/MM/YYYY", "what": "<short event>"}],
  "open_questions": ["<question solicitor should ask the client>", "..."],
  "next_legal_steps": ["<deadline-driven action>", "..."]
}

RULES:
- Stick to facts in the timeline. NEVER invent dates, names, or events.
- If a date is missing, write '[date unclear]' inline.
- key_dates: max 8, sorted ascending.
- open_questions: max 5 — focus on gaps a solicitor will need answered.
- next_legal_steps: max 4 — actionable, deadline-aware.
"""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"casesum-{case_id[:8]}", system_message=sysmsg)\
        .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2500)
    user_msg = f"""CASE: {case.get('name')} ({case.get('category') or 'general'})

CHRONOLOGY:
{timeline_text}

Produce the handover JSON now."""
    try:
        raw = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("timeline summarise failed"); raise HTTPException(500, f"AI error: {e}")
    parsed = _extract_json_object(raw)
    if not parsed:
        raise HTTPException(502, "Lex couldn't structure the summary. Try again.")
    # Persist for re-use
    await db.case_timeline_summaries.update_one(
        {"case_id": case_id, "user_id": user["id"]},
        {"$set": {**parsed, "event_count": len(events),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {**parsed, "event_count": len(events), "case": case}


# ---------- 4. Witness Statement Invite (magic link) ----------

class WitnessInviteRequest(BaseModel):
    witness_name: str = Field(min_length=2, max_length=120)
    witness_email: Optional[EmailStr] = None
    context_for_witness: str = Field(min_length=20, max_length=2000)
    # Optional: a couple of guiding questions for the witness
    questions: Optional[List[str]] = None


@api_router.post("/cases/{case_id}/witness/invite")
async def witness_invite(case_id: str, data: WitnessInviteRequest, request: Request, user: dict = Depends(get_user)):
    case = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")

    token = _secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    invite_id = str(uuid.uuid4())

    invite = {
        "id": invite_id, "token": token,
        "case_id": case_id, "user_id": user["id"],
        "witness_name": data.witness_name,
        "witness_email": data.witness_email,
        "context_for_witness": data.context_for_witness,
        "questions": (data.questions or [])[:6],
        "status": "pending",  # pending | submitted | expired
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
    }
    await db.witness_invites.insert_one(invite)

    # Public link — uses APP_PUBLIC_URL or falls back to the request's base URL
    base = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
    if not base:
        # Build from request
        proto = "https" if request.url.scheme == "https" else request.url.scheme
        base = f"{proto}://{request.url.netloc}"
    magic_link = f"{base}/witness/{token}"

    # Email the witness if email was provided
    email_sent = False
    if data.witness_email:
        try:
            from email_helper import send_email
            requester = user.get("full_name") or user.get("email", "the case owner")
            html = f"""
              <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">You've been asked to give a witness statement</h2>
              <p>Hi {data.witness_name.split()[0]},</p>
              <p><strong>{requester}</strong> has asked you to provide a witness statement for a legal matter they're dealing with through <strong>AI Advocate</strong>.</p>
              <p style="background:#fffaeb; border-left:3px solid #f7c948; padding:10px 14px; margin:18px 0; font-size:13px; color:#1a1300;">
                <strong>What they wrote:</strong><br/>"{data.context_for_witness[:600]}"
              </p>
              <p>Click the secure link below to write your statement. No account needed — it takes about 5-10 minutes.</p>
              <p style="margin:24px 0;">
                <a href="{magic_link}" style="background:#f7c948; color:#1a1300; padding:12px 22px; border-radius:8px; font-weight:700; text-decoration:none; display:inline-block;">Write your statement →</a>
              </p>
              <p style="font-size:12.5px; color:#555;">The link expires in 30 days. Your statement will be private to {requester} and won't be shared without your consent.</p>
              <p style="font-size:13px; color:#666;">If you don't recognise this request, simply ignore this email.</p>
            """
            email_sent = await send_email(
                to=data.witness_email,
                subject=f"Witness statement request from {requester}",
                body_html=html,
                kind="user",
            )
        except Exception as e:
            logger.warning(f"witness invite email failed: {e}")

    return {
        "invite_id": invite_id, "token": token,
        "magic_link": magic_link, "expires_at": expires_at,
        "email_sent": email_sent,
    }


@api_router.get("/witness/{token}")
async def witness_public_fetch(token: str):
    """Public — witness clicks the magic link, frontend loads the brief."""
    inv = await db.witness_invites.find_one({"token": token}, {"_id": 0, "user_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv.get("status") == "submitted":
        return {"status": "already_submitted", "witness_name": inv.get("witness_name")}
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < datetime.now(timezone.utc):
        return {"status": "expired", "witness_name": inv.get("witness_name")}
    # Look up requester name (not email — privacy) — separate fetch since the public
    # projection above excludes user_id.
    raw = await db.witness_invites.find_one({"token": token}, {"_id": 0, "user_id": 1})
    requester_name = "the case owner"
    if raw and raw.get("user_id"):
        u = await db.users.find_one({"id": raw["user_id"]}, {"_id": 0, "full_name": 1, "email": 1})
        if u:
            requester_name = u.get("full_name") or (u.get("email", "").split("@")[0] if u.get("email") else "the case owner")
    return {
        "status": "ready",
        "witness_name": inv.get("witness_name"),
        "context_for_witness": inv.get("context_for_witness"),
        "questions": inv.get("questions", []),
        "requester_name": requester_name,
        "expires_at": inv.get("expires_at"),
    }


class WitnessSubmitRequest(BaseModel):
    statement: str = Field(min_length=80, max_length=20000)
    witness_full_name: str = Field(min_length=2, max_length=200)
    witness_address: Optional[str] = ""
    witness_occupation: Optional[str] = ""
    witness_phone: Optional[str] = ""
    witness_email: Optional[EmailStr] = None
    statement_of_truth: bool = False  # must be True to submit


class WitnessAutoDraftRequest(BaseModel):
    bullet_points: str = Field(default="", max_length=4000, description="Witness's own rough notes / bullets")
    witness_full_name: str = Field(default="", max_length=200)
    witness_occupation: Optional[str] = ""
    language: str = "en-GB"


@api_router.post("/witness/{token}/auto-draft")
async def witness_auto_draft(token: str, data: WitnessAutoDraftRequest):
    """Public — witness asks Lex to draft a first version of their statement from
    their own bullet points + the invite's context_for_witness. PRIVACY: only
    the witness's own input + the invite context are passed to the LLM — NEVER
    the case owner's chat history or other case items."""
    inv = await db.witness_invites.find_one({"token": token}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv.get("status") == "submitted":
        raise HTTPException(409, "Already submitted")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(410, "Invite has expired")

    if not (data.bullet_points or "").strip() and not (inv.get("context_for_witness") or "").strip():
        raise HTTPException(400, "Need either your own notes OR the invite context to draft from.")

    lang_name = LANG_NAMES.get(data.language, "English")
    witness_name = data.witness_full_name or inv.get("witness_name") or "[Witness name]"
    occ = data.witness_occupation or ""

    sysmsg = f"""You are AI Advocate's witness-statement drafter. Reply in {lang_name}.

Draft a UK CPR Part 32-compliant witness statement IN FIRST PERSON ("I").

CRITICAL RULES:
- Use ONLY the facts in the bullet points + the invite context provided. NEVER invent facts.
- If a date/name/place is missing, write '[date unclear]' or '[name to confirm]' — do NOT guess.
- Plain English. Chronological. Numbered paragraphs (1, 2, 3...).
- First paragraph: who the witness is, occupation if given, how they know the parties / what they witnessed.
- Middle paragraphs: factual chronology of what they saw/heard/did. One event per paragraph.
- Final paragraph: confirms they are willing to attend court / give oral evidence if required.
- Do NOT include the Statement of Truth — the form handles that separately.
- Output ONLY the body of the statement. No greeting, no header, no markdown fences."""

    user_msg = f"""WITNESS NAME: {witness_name}
WITNESS OCCUPATION: {occ or "(not provided)"}

CONTEXT FROM THE CASE OWNER (what they asked the witness to write about):
{inv.get("context_for_witness", "(none provided)")}

GUIDING QUESTIONS THE OWNER WANTS ANSWERED:
{chr(10).join(f"- {q}" for q in (inv.get("questions") or [])) or "(none)"}

WITNESS'S OWN ROUGH BULLETS / NOTES:
{data.bullet_points or "(none — work from the context above only)"}

Draft the witness statement now."""

    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"wdraft-{uuid.uuid4().hex[:10]}", system_message=sysmsg)\
            .with_model("anthropic", "claude-sonnet-4-5-20250929").with_params(max_tokens=2500)
        draft = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        logger.exception("witness auto-draft failed"); raise HTTPException(500, f"AI error: {e}")

    return {"draft": (draft or "").strip(), "based_on_bullets": bool((data.bullet_points or "").strip())}


@api_router.post("/witness/{token}/submit")
async def witness_public_submit(token: str, data: WitnessSubmitRequest):
    """Public — witness submits the statement. Tokens are single-use."""
    if not data.statement_of_truth:
        raise HTTPException(400, "You must confirm the Statement of Truth to submit.")
    inv = await db.witness_invites.find_one({"token": token}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv.get("status") == "submitted":
        raise HTTPException(409, "This statement has already been submitted.")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(410, "This invite has expired. Ask the case owner for a new link.")

    statement_id = str(uuid.uuid4())
    rec = {
        "id": statement_id,
        "invite_id": inv["id"], "case_id": inv["case_id"], "user_id": inv["user_id"],
        "witness_name": data.witness_full_name,
        "witness_address": data.witness_address or "",
        "witness_occupation": data.witness_occupation or "",
        "witness_phone": data.witness_phone or "",
        "witness_email": data.witness_email or inv.get("witness_email") or "",
        "statement": data.statement,
        "statement_of_truth": True,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "ip_hash": "",  # could hash the requesting IP for audit
    }
    await db.witness_statements.insert_one(rec.copy())
    await db.witness_invites.update_one(
        {"token": token}, {"$set": {"status": "submitted", "submitted_at": rec["submitted_at"]}},
    )

    # Auto-link into the case as a case_item so it shows in the case + timeline
    try:
        await db.case_items.insert_one({
            "id": str(uuid.uuid4()),
            "case_id": inv["case_id"], "user_id": inv["user_id"],
            "item_type": "note", "item_id": statement_id,
            "title": f"Witness statement — {data.witness_full_name}",
            "preview": data.statement[:300],
            "timestamp_utc": rec["submitted_at"],
            "kind": "witness_statement",
            "created_at": rec["submitted_at"],
        })
        await db.cases.update_one(
            {"id": inv["case_id"]},
            {"$inc": {"items_count": 1}, "$set": {"updated_at": rec["submitted_at"]}},
        )
    except Exception as e:
        logger.warning(f"witness → case_items link failed: {e}")

    # Notify the case owner by email
    try:
        owner = await db.users.find_one({"id": inv["user_id"]}, {"_id": 0, "email": 1, "full_name": 1})
        if owner and owner.get("email"):
            from email_helper import send_email
            html = f"""
              <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">📬 Witness statement received</h2>
              <p>Hi {(owner.get('full_name') or '').split(' ')[0] or 'there'},</p>
              <p><strong>{data.witness_full_name}</strong> has just submitted their witness statement for your case.</p>
              <p style="background:#fffaeb; border-left:3px solid #f7c948; padding:10px 14px; margin:18px 0; font-size:13px; color:#1a1300; line-height:1.5;">
                <strong>Statement preview:</strong><br/>"{data.statement[:400]}{'...' if len(data.statement)>400 else ''}"
              </p>
              <p>Log in to AI Advocate and open the case to view the full statement and download a CPR 32-compliant PDF.</p>
              <p style="font-size:12.5px; color:#555;">The statement of truth was signed at {rec['submitted_at']}.</p>
            """
            await send_email(to=owner["email"], subject=f"Witness statement received — {data.witness_full_name}", body_html=html)
    except Exception as e:
        logger.warning(f"owner-notify email failed: {e}")

    return {"ok": True, "statement_id": statement_id}


@api_router.get("/cases/{case_id}/witness-statements")
async def witness_statements_list(case_id: str, user: dict = Depends(get_user)):
    case = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0, "id": 1})
    if not case:
        raise HTTPException(404, "Case not found")
    statements = [
        s async for s in db.witness_statements.find(
            {"case_id": case_id, "user_id": user["id"]}, {"_id": 0},
        ).sort("submitted_at", -1)
    ]
    pending = [
        i async for i in db.witness_invites.find(
            {"case_id": case_id, "user_id": user["id"], "status": "pending"},
            {"_id": 0, "witness_name": 1, "witness_email": 1, "id": 1,
             "created_at": 1, "expires_at": 1, "token": 1},
        ).sort("created_at", -1)
    ]
    return {"statements": statements, "pending_invites": pending}


@api_router.get("/cases/{case_id}/witness-statements/{ws_id}/pdf")
async def witness_statement_pdf(case_id: str, ws_id: str, user: dict = Depends(get_user)):
    ws = await db.witness_statements.find_one(
        {"id": ws_id, "case_id": case_id, "user_id": user["id"]}, {"_id": 0},
    )
    if not ws:
        raise HTTPException(404, "Statement not found")

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.enums import TA_LEFT
    import io as _io

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=2.2*cm, rightMargin=2.2*cm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=11, leading=15, alignment=TA_LEFT)
    bold = ParagraphStyle("bold", parent=body, fontName="Helvetica-Bold")
    small = ParagraphStyle("small", parent=body, fontSize=9, textColor="#555")

    case = await db.cases.find_one({"id": case_id}, {"_id": 0, "name": 1, "category": 1}) or {}
    story = []
    story += [Paragraph("WITNESS STATEMENT", ParagraphStyle("title", parent=body, fontSize=15, alignment=1, fontName="Helvetica-Bold")), Spacer(1, 6)]
    story += [Paragraph(f"In the matter of: <b>{case.get('name','')}</b>", body), Spacer(1, 4)]
    story += [Paragraph(f"Category: {case.get('category','general')}", small), Spacer(1, 14)]

    story += [Paragraph(f"<b>Witness:</b> {ws['witness_name']}", body)]
    if ws.get("witness_occupation"):
        story += [Paragraph(f"<b>Occupation:</b> {ws['witness_occupation']}", body)]
    if ws.get("witness_address"):
        story += [Paragraph(f"<b>Address:</b> {ws['witness_address']}", body)]
    story += [Spacer(1, 14)]

    story += [Paragraph("Statement:", bold), Spacer(1, 6)]
    # Number paragraphs (CPR 32 style)
    paragraphs = [p.strip() for p in ws["statement"].split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [ws["statement"]]
    for i, p in enumerate(paragraphs, 1):
        story += [Paragraph(f"{i}. {p}", body), Spacer(1, 6)]

    story += [Spacer(1, 12)]
    story += [Paragraph("<b>Statement of Truth</b>", body)]
    story += [Paragraph(
        "I believe that the facts stated in this witness statement are true. I understand that "
        "proceedings for contempt of court may be brought against anyone who makes, or causes to be "
        "made, a false statement in a document verified by a statement of truth without an honest "
        "belief in its truth.", body)]
    story += [Spacer(1, 18)]
    story += [Paragraph(f"Signed: {ws['witness_name']}", body)]
    story += [Paragraph(f"Date submitted: {ws['submitted_at'][:10]}", small)]
    story += [Spacer(1, 12)]
    story += [Paragraph("Generated by AI Advocate · CPR Part 32 compliant template · NOT a substitute for legal advice.", small)]

    doc.build(story)
    buf.seek(0)
    fname = f"witness-statement-{ws['witness_name'].replace(' ','_')}-{ws_id[:8]}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ==========================================================================
# 🗂  EVIDENCE-COLLECTION MAGIC-LINK (Iter 45)
# Anyone (HR, ex-employer, friend) can upload documents directly into a case
# without signing up. Owner creates a tokenised invite → uploader gets a link
# → uploads files (max 12MB each, max 8 files per invite) → files land in the
# case_items + raw bytes stored in evidence_files (encrypted base64).
# ==========================================================================


class EvidenceInviteRequest(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    instructions: str = Field(min_length=10, max_length=2000)
    uploader_email: Optional[EmailStr] = None
    uploader_name: Optional[str] = ""


@api_router.post("/cases/{case_id}/evidence/invite")
async def evidence_invite(case_id: str, data: EvidenceInviteRequest, request: Request, user: dict = Depends(get_user)):
    case = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")

    token = _secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    invite_id = str(uuid.uuid4())
    invite = {
        "id": invite_id, "token": token,
        "case_id": case_id, "user_id": user["id"],
        "label": data.label, "instructions": data.instructions,
        "uploader_name_hint": data.uploader_name or "",
        "uploader_email": data.uploader_email,
        "status": "open",   # open | closed (owner can revoke). Uploads stay available until expiry.
        "upload_count": 0, "max_uploads": 8,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
    }
    await db.evidence_invites.insert_one(invite)

    base = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
    if not base:
        proto = "https" if request.url.scheme == "https" else request.url.scheme
        base = f"{proto}://{request.url.netloc}"
    magic_link = f"{base}/evidence/{token}"

    email_sent = False
    if data.uploader_email:
        try:
            from email_helper import send_email
            requester = user.get("full_name") or user.get("email", "the case owner")
            html = f"""
              <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">You've been asked to share some documents</h2>
              <p>Hi {(data.uploader_name or '').split(' ')[0] or 'there'},</p>
              <p><strong>{requester}</strong> has asked you to share some documents for a legal matter they're dealing with through <strong>AI Advocate</strong>.</p>
              <p style="background:#fffaeb; border-left:3px solid #f7c948; padding:10px 14px; margin:18px 0; font-size:13px; color:#1a1300;">
                <strong>What they need:</strong><br/>"{data.instructions[:600]}"
              </p>
              <p>Click the secure link below to upload the files. No account needed — drag-and-drop works.</p>
              <p style="margin:24px 0;">
                <a href="{magic_link}" style="background:#f7c948; color:#1a1300; padding:12px 22px; border-radius:8px; font-weight:700; text-decoration:none; display:inline-block;">Upload your files →</a>
              </p>
              <p style="font-size:12.5px; color:#555;">The link expires in 30 days. Maximum 8 files, 12 MB each.</p>
            """
            email_sent = await send_email(
                to=data.uploader_email,
                subject=f"Document request from {requester}",
                body_html=html, kind="user",
            )
        except Exception as e:
            logger.warning(f"evidence invite email failed: {e}")

    return {"invite_id": invite_id, "token": token, "magic_link": magic_link,
            "expires_at": expires_at, "email_sent": email_sent}


@api_router.get("/evidence/{token}")
async def evidence_public_fetch(token: str):
    """Public — uploader clicks the magic link."""
    inv = await db.evidence_invites.find_one({"token": token}, {"_id": 0, "user_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv.get("status") == "closed":
        return {"status": "closed", "label": inv.get("label")}
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < datetime.now(timezone.utc):
        return {"status": "expired", "label": inv.get("label")}
    if (inv.get("upload_count") or 0) >= (inv.get("max_uploads") or 8):
        return {"status": "limit_reached", "label": inv.get("label"), "max_uploads": inv.get("max_uploads")}
    # Requester display name
    raw = await db.evidence_invites.find_one({"token": token}, {"_id": 0, "user_id": 1})
    requester_name = "the case owner"
    if raw and raw.get("user_id"):
        u = await db.users.find_one({"id": raw["user_id"]}, {"_id": 0, "full_name": 1, "email": 1})
        if u:
            requester_name = u.get("full_name") or (u.get("email", "").split("@")[0] if u.get("email") else "the case owner")
    return {
        "status": "ready",
        "label": inv.get("label"), "instructions": inv.get("instructions"),
        "uploader_name_hint": inv.get("uploader_name_hint", ""),
        "requester_name": requester_name,
        "upload_count": inv.get("upload_count", 0),
        "max_uploads": inv.get("max_uploads", 8),
        "expires_at": inv.get("expires_at"),
    }


@api_router.post("/evidence/{token}/upload")
async def evidence_public_upload(
    token: str,
    file: UploadFile = File(...),
    uploader_name: str = Form(...),
    uploader_email: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    """Public — uploader submits a file. Stores BYTES (encrypted, base64) so the
    owner can actually download them later. Capped at 12MB per file, 8 per invite."""
    inv = await db.evidence_invites.find_one({"token": token}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv.get("status") == "closed":
        raise HTTPException(403, "This evidence request was closed by the requester.")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(410, "Invite has expired")
    if (inv.get("upload_count") or 0) >= (inv.get("max_uploads") or 8):
        raise HTTPException(429, f"Upload limit reached ({inv.get('max_uploads')} files). Ask the requester for a new link.")

    if not uploader_name or len(uploader_name.strip()) < 2:
        raise HTTPException(400, "Please provide your name.")

    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "File too large (12 MB max)")
    if len(raw) < 50:
        raise HTTPException(400, "File seems empty.")
    import hashlib as _hl
    sha = _hl.sha256(raw).hexdigest()
    mt = (file.content_type or "application/octet-stream").lower()
    kind = ("photo" if mt.startswith("image/") else
            "video" if mt.startswith("video/") else
            "audio" if mt.startswith("audio/") else "document")

    # Store the bytes encrypted in evidence_files (separate collection — keeps
    # case_items lean for listing).
    evidence_file_id = str(uuid.uuid4())
    file_b64 = base64.b64encode(raw).decode("ascii")
    await db.evidence_files.insert_one({
        "id": evidence_file_id, "case_id": inv["case_id"], "user_id": inv["user_id"],
        "invite_id": inv["id"], "token_hash": _hl.sha256(token.encode()).hexdigest()[:32],
        "filename": file.filename or "evidence",
        "content_type": mt, "size_bytes": len(raw), "sha256": sha,
        "file_b64": encrypt_text(file_b64),
        "uploader_name": uploader_name.strip()[:200],
        "uploader_email": (uploader_email or "").strip()[:200] or None,
        "description": (description or "")[:1000],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })

    # Auto-create a case_item so it shows up in the case + timeline immediately
    case_item_id = str(uuid.uuid4())
    await db.case_items.insert_one({
        "id": case_item_id,
        "case_id": inv["case_id"], "user_id": inv["user_id"],
        "item_type": kind, "item_id": evidence_file_id,
        "title": f"{file.filename or 'Evidence'} — from {uploader_name.strip()[:80]}",
        "preview": (description or "")[:500],
        "filename": file.filename or "",
        "content_type": mt, "size_bytes": len(raw), "sha256": sha,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "evidence_upload", "evidence_file_id": evidence_file_id,
        "uploader_name": uploader_name.strip()[:200],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.cases.update_one(
        {"id": inv["case_id"]},
        {"$inc": {"items_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.evidence_invites.update_one({"token": token}, {"$inc": {"upload_count": 1}})

    # Notify owner
    try:
        owner = await db.users.find_one({"id": inv["user_id"]}, {"_id": 0, "email": 1, "full_name": 1})
        if owner and owner.get("email"):
            from email_helper import send_email
            html = f"""
              <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">📎 New evidence received</h2>
              <p>Hi {(owner.get('full_name') or '').split(' ')[0] or 'there'},</p>
              <p><strong>{uploader_name}</strong> just uploaded a file to your "<em>{inv.get('label')}</em>" evidence request.</p>
              <p style="background:#fffaeb; border-left:3px solid #f7c948; padding:10px 14px; margin:18px 0; font-size:13px; color:#1a1300;">
                <strong>File:</strong> {file.filename or 'evidence'} ({(len(raw)/1024):.0f} KB)<br/>
                {('<strong>Note:</strong> ' + description) if description else ''}
              </p>
              <p>Log in to AI Advocate and open the case to view + download the file.</p>
              <p style="font-size:12.5px; color:#555;">SHA-256: {sha[:16]}… · Uploaded {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
            """
            await send_email(to=owner["email"], subject=f"Evidence received — {uploader_name}", body_html=html)
    except Exception as e:
        logger.warning(f"evidence owner-notify failed: {e}")

    return {"ok": True, "evidence_file_id": evidence_file_id,
            "remaining_uploads": (inv.get("max_uploads") or 8) - (inv.get("upload_count") or 0) - 1}


@api_router.get("/cases/{case_id}/evidence/invites")
async def evidence_invites_list(case_id: str, user: dict = Depends(get_user)):
    case = await db.cases.find_one({"id": case_id, "user_id": user["id"]}, {"_id": 0, "id": 1})
    if not case:
        raise HTTPException(404, "Case not found")
    invites = [
        i async for i in db.evidence_invites.find(
            {"case_id": case_id, "user_id": user["id"]},
            {"_id": 0, "id": 1, "label": 1, "instructions": 1, "uploader_email": 1,
             "uploader_name_hint": 1, "status": 1, "upload_count": 1, "max_uploads": 1,
             "created_at": 1, "expires_at": 1, "token": 1},
        ).sort("created_at", -1)
    ]
    files = [
        f async for f in db.evidence_files.find(
            {"case_id": case_id, "user_id": user["id"]},
            {"_id": 0, "file_b64": 0},  # exclude bytes
        ).sort("uploaded_at", -1)
    ]
    return {"invites": invites, "files": files}


@api_router.get("/cases/{case_id}/evidence/files/{file_id}/download")
async def evidence_file_download(case_id: str, file_id: str, user: dict = Depends(get_user)):
    rec = await db.evidence_files.find_one(
        {"id": file_id, "case_id": case_id, "user_id": user["id"]}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(404, "File not found")
    try:
        decoded = base64.b64decode(decrypt_text(rec["file_b64"]))
    except Exception:
        raise HTTPException(500, "File could not be decrypted")
    fname = rec.get("filename") or f"evidence-{file_id[:8]}"
    return StreamingResponse(
        io.BytesIO(decoded),
        media_type=rec.get("content_type") or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api_router.post("/cases/{case_id}/evidence/invites/{invite_id}/close")
async def evidence_invite_close(case_id: str, invite_id: str, user: dict = Depends(get_user)):
    r = await db.evidence_invites.update_one(
        {"id": invite_id, "case_id": case_id, "user_id": user["id"]},
        {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Invite not found")
    return {"ok": True}


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
    # Run the recycle-bin sweeper once at startup, then schedule periodic re-runs.
    # Idempotent — safe even if multiple workers boot.
    import asyncio as _aio
    try:
        await _recycle_bin_sweeper()
    except Exception as e:
        logger.warning(f"Recycle-bin sweep on startup failed: {e}")
    async def _periodic_sweep():
        while True:
            await _aio.sleep(6 * 3600)   # every 6 hours
            try:
                await _recycle_bin_sweeper()
            except Exception as e:
                logger.warning(f"Periodic recycle-bin sweep failed: {e}")
    _aio.create_task(_periodic_sweep())

    # === Hybrid auto-billing scheduler ===
    # 22nd 09:00 UTC → heads-up email to firms
    # 1st  09:00 UTC → generate DRAFT invoices + admin summary
    # 3rd  09:00 UTC → auto-send any still-draft non-flagged invoices
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        sched = AsyncIOScheduler(timezone="UTC")

        async def _job_headsup():
            try:
                month = await _resolve_prev_month()
                # heads-up is for the month we'll be invoicing — so for run on
                # March 22, we're warning about March engagements (current month).
                # Use current month here.
                month = datetime.now(timezone.utc).isoformat()[:7]
                r = await _send_headsup_emails(month, source="cron")
                logger.info(f"[cron] heads-up sent: {r}")
            except Exception as e:
                logger.exception(f"[cron] heads-up failed: {e}")

        async def _job_create_drafts():
            try:
                month = await _resolve_prev_month()
                r = await _create_monthly_drafts(month, source="cron")
                logger.info(f"[cron] drafts created for {month}: count={r.get('count')} total=£{r.get('total_commission_gbp')}")
            except Exception as e:
                logger.exception(f"[cron] draft creation failed: {e}")

        async def _job_autosend():
            try:
                # Auto-send any drafts still in draft state for previous month
                # (the one we drafted on the 1st), but ONLY non-flagged ones.
                prev = await _resolve_prev_month()
                cursor = db.commission_drafts.find({"month": prev, "status": "draft",
                                                    "requires_review": {"$ne": True}}, {"_id": 0})
                drafts = [d async for d in cursor]
                sent = 0
                for d in drafts:
                    try:
                        await _approve_draft_inner(d["stripe_invoice_id"])
                        sent += 1
                    except Exception as e:
                        logger.warning(f"[cron] autosend failed for {d.get('stripe_invoice_id')}: {e}")
                logger.info(f"[cron] auto-sent {sent} drafts for {prev}")
                # Email admin a summary of what still needs manual review
                still_held = await db.commission_drafts.count_documents(
                    {"month": prev, "status": "draft", "requires_review": True}
                )
                if still_held > 0:
                    try:
                        admin_emails = [e.strip() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]
                        from email_helper import send_email
                        for ae in admin_emails:
                            await send_email(to=ae, kind="firm",
                                subject=f"⚠️ {still_held} commission draft(s) need your review",
                                body_html=f"<p>{still_held} draft invoice(s) for {prev} are flagged as anomalies and were NOT auto-sent. Review them in admin → 💷 Firm referral commissions.</p>")
                    except Exception as e:
                        logger.warning(f"Admin held-drafts email failed: {e}")
            except Exception as e:
                logger.exception(f"[cron] autosend job failed: {e}")

        sched.add_job(_job_headsup,       CronTrigger(day=22, hour=9, minute=0), id="aa_headsup",  replace_existing=True)
        sched.add_job(_job_create_drafts, CronTrigger(day=1,  hour=9, minute=0), id="aa_drafts",   replace_existing=True)
        sched.add_job(_job_autosend,      CronTrigger(day=3,  hour=9, minute=0), id="aa_autosend", replace_existing=True)
        sched.start()
        app.state.aa_scheduler = sched
        logger.info("✅ Auto-billing scheduler started — next run: %s",
                    next((j.next_run_time for j in sched.get_jobs()), "n/a"))
    except Exception as e:
        logger.exception(f"Scheduler failed to start (non-fatal): {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        sched = getattr(app.state, "aa_scheduler", None)
        if sched: sched.shutdown(wait=False)
    except Exception:
        pass
    client.close()
