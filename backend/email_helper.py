"""
Resend transactional-email helper for AI Advocate.

Sends 4 email types:
  1. send_waitlist_ack(email)              — when someone joins the waitlist
  2. send_welcome_with_daypass(email, name) — first 100 real signups
  3. send_welcome_missed_offer(email, name) — signup #101+
  4. send_launch_broadcast(email)           — manual blast when iOS goes live

Key design choices:
  • Async-safe (uses asyncio.to_thread so the FastAPI event loop never blocks)
  • Graceful degradation: if RESEND_API_KEY is empty or Resend fails, we log
    and return False — signup flow MUST never break because of email issues
  • Inline CSS only (every email client supports it). Gold accent #f7c948.
  • Reply-To set to support@aiadvocate.co.uk so user replies go to the real inbox
"""

import asyncio
import logging
import os
from typing import Optional

import resend
from dotenv import load_dotenv

# Ensure .env is loaded even if this module is imported before server.py
# completes its own load_dotenv() call (e.g. via uvicorn auto-reload).
load_dotenv()

logger = logging.getLogger(__name__)


def _api_key() -> Optional[str]:
    """Read RESEND_API_KEY on every call so a redeploy / .env update is picked
    up without restarting Python. Returns None for empty/missing values."""
    v = os.environ.get("RESEND_API_KEY") or ""
    return v.strip() or None


def _from_email() -> str:
    return (os.environ.get("RESEND_FROM_EMAIL") or "").strip() or "no-reply@aiadvocate.co.uk"


def _reply_to() -> str:
    return (os.environ.get("RESEND_REPLY_TO") or "").strip() or "support@aiadvocate.co.uk"


def _wrap(html_body: str, preview: str = "") -> str:
    """Standard email shell: gold-accent header, dark card on white, footer."""
    return f"""<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <span style="display:none; visibility:hidden; max-height:0; overflow:hidden;">{preview}</span>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f5f5f5; padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06);">
        <tr><td style="background:linear-gradient(135deg,#0a0a0a,#1a1300); padding:24px 28px; text-align:left;">
          <div style="color:#f7c948; font-family:'Cinzel', Georgia, serif; font-size:22px; font-weight:700; letter-spacing:0.04em;">AI ADVOCATE</div>
          <div style="color:#cfcfcf; font-size:11px; letter-spacing:0.08em; margin-top:4px;">A LAWYER IN YOUR POCKET</div>
        </td></tr>
        <tr><td style="padding:28px 28px 24px 28px; color:#1a1300; font-size:15px; line-height:1.6;">
          {html_body}
        </td></tr>
        <tr><td style="padding:14px 28px 22px 28px; border-top:1px solid #eaeaea; color:#888; font-size:11.5px; line-height:1.5;">
          AI Advocate Ltd. · ICO Registration ZC158457 · <a href="https://aiadvocate.co.uk" style="color:#b8860b; text-decoration:none;">aiadvocate.co.uk</a><br>
          You're receiving this because you signed up at aiadvocate.co.uk. Reply to this email if you have questions.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


async def _send(to_email: str, subject: str, html: str) -> bool:
    """Low-level async send. Returns False (never raises) so callers can fire-and-forget safely."""
    api_key = _api_key()
    if not api_key:
        logger.info(f"[email-skip] {to_email} | {subject!r} (no RESEND_API_KEY)")
        return False
    try:
        resend.api_key = api_key
        params = {
            "from": _from_email(),
            "to": [to_email],
            "subject": subject,
            "html": html,
            "reply_to": [_reply_to()],
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        eid = result.get("id") if isinstance(result, dict) else None
        logger.info(f"[email-sent] {to_email} | {subject!r} | id={eid}")
        return True
    except Exception as e:
        logger.exception(f"[email-fail] {to_email} | {subject!r}: {e}")
        return False


# ============================================================================
# Public helpers — call these from FastAPI route handlers.
# ============================================================================

async def send_waitlist_ack(email: str, full_name: str = "") -> bool:
    name = (full_name or "").strip().split(" ")[0] or "there"
    html = _wrap(f"""
      <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">You're on the list, {name} 🎉</h2>
      <p>Thanks for joining the AI Advocate waitlist. We'll email you the moment the iOS and Android apps go live.</p>
      <p style="background:#fff8e1; border-left:3px solid #f7c948; padding:12px 14px; border-radius:6px; font-size:14px; margin:18px 0;">
        <strong style="color:#b8860b;">Want to start now?</strong><br>
        The web app is already live — sign up at
        <a href="https://aiadvocate.co.uk/app" style="color:#b8860b; font-weight:600;">aiadvocate.co.uk/app</a>
        and the first 100 signups get a free 24-hour Day Pass.
      </p>
      <p style="font-size:13px; color:#666;">Until then — stay safe out there.</p>
      <p style="margin:18px 0 0 0;">— The AI Advocate team</p>
    """, preview="You're on the AI Advocate waitlist — here's what happens next.")
    return await _send(email, "You're on the AI Advocate waitlist 🎉", html)


async def send_welcome_with_daypass(email: str, full_name: str = "") -> bool:
    name = (full_name or "").strip().split(" ")[0] or "there"
    html = _wrap(f"""
      <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">Welcome, {name} — your free Day Pass is active 🎁</h2>
      <p>You're one of the first 100 to sign up, so you get a free <strong>24-hour Day Pass</strong> (worth £4.99) — unlocking unlimited Lex chat, evidence analysis, letter generation, and case files for the next 24 hours.</p>
      <p style="background:#fff8e1; border-left:3px solid #f7c948; padding:12px 14px; border-radius:6px; font-size:14px; margin:18px 0;">
        <strong style="color:#b8860b;">Get started:</strong><br>
        1. Open <a href="https://aiadvocate.co.uk/app" style="color:#b8860b; font-weight:600;">aiadvocate.co.uk/app</a><br>
        2. Try asking Lex any UK legal question<br>
        3. Add your emergency contacts in Settings → SOS<br>
      </p>
      <p style="font-size:14px; line-height:1.6;">
        When the 24h is up, you'll automatically drop back to the Free tier. No charge, no surprises.
        If you want to keep the unlimited access, you can upgrade to Plus (£19.99/mo) or Pro (£34.99/mo) any time.
      </p>
      <p style="margin:18px 0 0 0;">— The AI Advocate team</p>
    """, preview="Your 24-hour Day Pass is live — start using Lex now.")
    return await _send(email, "🎁 Welcome — your free Day Pass is active", html)


async def send_welcome_missed_offer(email: str, full_name: str = "") -> bool:
    name = (full_name or "").strip().split(" ")[0] or "there"
    html = _wrap(f"""
      <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">Welcome, {name} 👋</h2>
      <p>You're now signed up to AI Advocate — thank you for joining.</p>
      <p>Sadly the first 100 free Day Passes have already been claimed (the offer was wildly popular). But we'd still love to have you try Plus or Pro at a reduced rate.</p>
      <p style="background:#fff8e1; border:1px solid #f7c948; padding:14px; border-radius:8px; text-align:center; margin:18px 0;">
        <strong style="color:#b8860b; font-size:13px; letter-spacing:0.08em;">YOUR LATE-COMER REWARD</strong><br>
        <span style="font-size:24px; font-weight:700; color:#1a1300; display:block; margin:8px 0;">20% off your first month</span>
        <span style="font-family:monospace; background:#1a1300; color:#f7c948; padding:6px 14px; border-radius:6px; font-size:14px; letter-spacing:0.1em;">WELCOME20</span><br>
        <span style="font-size:12px; color:#666; display:block; margin-top:8px;">Use the code at checkout. Valid for 14 days from today.</span>
      </p>
      <p style="font-size:14px; line-height:1.6;">
        Or stay on the free tier forever — you'll still have access to limited Lex chat and core features.
      </p>
      <p style="margin:18px 0 0 0;">— The AI Advocate team</p>
    """, preview="You missed the Day Pass — but here's 20% off as a thank you.")
    return await _send(email, "Welcome to AI Advocate (and a small thank-you gift)", html)


async def send_founding_thank_you(email: str, full_name: str = "") -> bool:
    """Personal thank-you from the founder, fired when the founder taps 'Approve'
    on a Founding-100 queue row in the admin panel. Distinct from the auto
    welcome email — this one comes after manual review."""
    name = (full_name or "").strip().split(" ")[0] or "there"
    html = _wrap(f"""
      <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">A personal thank-you, {name} 🙏</h2>
      <p>I just wanted to drop you a quick note from the team — you're one of the very first 100 people to sign up for AI Advocate, and that means a lot.</p>
      <p>Your free 24-hour Day Pass is already active (worth £4.99) — unlimited Lex chat, evidence analysis, letter drafting, the lot. Use it however you like.</p>
      <p style="background:#fff8e1; border-left:3px solid #f7c948; padding:12px 14px; border-radius:6px; font-size:14px; margin:18px 0;">
        <strong style="color:#b8860b;">If something's broken, weird, or could be better</strong> — hit reply to this email. It comes straight to me.
      </p>
      <p style="font-size:14px; line-height:1.6;">
        You're not just a user — you're a founding member. As a thank-you, you'll always get early access to new features before anyone else.
      </p>
      <p style="margin:18px 0 0 0;">— The AI Advocate founder</p>
    """, preview="A personal thank-you for being a founding-100 member of AI Advocate.")
    return await _send(email, "🌟 Thank you for being one of our first 100", html)





async def send_firm_onboarding(email: str, firm_name: str, tier: str, days: int, reset_link: str, portal_url: str) -> bool:
    """Fire when the founder comps a firm via /admin/firms/comp.
    Delivers the portal URL + a one-tap 'set password' link so the firm
    can log in without having to remember whatever the founder set."""
    tier_label = (tier or "Featured").title()
    duration = "Lifetime" if days >= 365 * 25 else f"{days} days"
    html = _wrap(f"""
      <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">Your AI Advocate firm portal is ready 🏛</h2>
      <p>{firm_name or 'Your firm'} has been activated on the <strong>{tier_label}</strong> tier for <strong>{duration}</strong>.</p>
      <p>Inside the portal you can:</p>
      <ul style="font-size:14px; line-height:1.7; padding-left:18px; margin:8px 0 14px 0;">
        <li>Set your firm <strong>logo + brand colours</strong> (Premium/Practice)</li>
        <li>Invite fee-earner team-mates as <strong>seats</strong> (up to 5 on Practice)</li>
        <li>Reply to <strong>encrypted client case threads</strong> end-to-end</li>
        <li>Track leads from your firm directory listing</li>
      </ul>
      <p style="text-align:center; margin:26px 0;">
        <a href="{reset_link}" style="background:#f7c948; color:#1a1300; padding:14px 28px; border-radius:10px; font-weight:700; text-decoration:none; display:inline-block; font-size:15px;">Set your password & sign in →</a>
      </p>
      <p style="font-size:12.5px; color:#666; line-height:1.5;">
        This one-time link expires in 60 minutes. Once you've set a password, log in any time at
        <a href="{portal_url}" style="color:#b8860b; font-weight:600;">{portal_url.replace('https://','').replace('http://','')}</a>.
      </p>
      <p style="font-size:13px; line-height:1.6; margin-top:18px;">
        Questions or onboarding help? Reply to this email — it lands in our founder's inbox.
      </p>
      <p style="margin:18px 0 0 0;">— The AI Advocate team</p>
    """, preview=f"Your AI Advocate firm portal is ready — {tier_label} for {duration}.")
    return await _send(email, "🏛 Your AI Advocate firm portal is ready", html)

async def send_password_reset(email: str, reset_link: str) -> bool:
    html = _wrap(f"""
      <h2 style="margin:0 0 12px 0; color:#1a1300; font-size:22px;">Reset your AI Advocate password</h2>
      <p>You (or someone using your email) asked to reset the password on your AI Advocate account.</p>
      <p style="margin:18px 0;">
        <a href="{reset_link}" style="background:#f7c948; color:#1a1300; padding:12px 22px; border-radius:8px; font-weight:700; text-decoration:none; display:inline-block;">Reset password</a>
      </p>
      <p style="font-size:12px; color:#666;">This link expires in 60 minutes. If you didn't request this, ignore this email — your password is unchanged.</p>
    """, preview="Reset your AI Advocate password — link expires in 60 mins.")
    return await _send(email, "Reset your AI Advocate password", html)
