"""
One-off generator for the AI Advocate 5-week Instagram content pack.

Generates 15 Nano Banana images (1 per post, ~1080×1080 square) into
/app/frontend/public/instagram-pack/images/ . Run sequentially to avoid
rate-limiting on the proxy.

Usage:  python3 /app/scripts/gen_instagram_pack.py
"""
import asyncio
import base64
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("/app/backend"))
load_dotenv("/app/backend/.env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

API_KEY = os.environ["EMERGENT_LLM_KEY"]
OUT_DIR = "/app/frontend/public/instagram-pack/images"
os.makedirs(OUT_DIR, exist_ok=True)

# Strict shared style prompt baked into every image — keeps the grid cohesive.
STYLE = (
    "Cinematic editorial photography style. Dark moody background (#0a0a0a near-black) "
    "with subtle gold accent lighting. Premium luxurious feel. Centred composition, "
    "1:1 square aspect ratio. NO text on the image, NO logos, NO watermarks. "
    "British / UK setting. Gold (#f7c948) and warm-brown highlights only. "
    "Tasteful, professional, never gaudy. Sharp focus on subject. Empty space "
    "around the subject for caption overlay later. No people's faces clearly visible "
    "(use silhouettes, hands, side-profiles instead) — for stock-image usability."
)

POSTS = [
    # 5-week rhythm: 3 per week × 5 weeks = 15 posts
    # Week 1 — Identity / brand intro
    ("01_palm_of_hand", "A British solicitor's hand holding a sleek black smartphone, "
     "the phone screen subtly glowing gold. Gavel and scales of justice softly blurred in the background. "
     "Symbolises 'the law in the palm of your hand'."),
    ("02_uk_courthouse_silhouette", "Side silhouette of the Royal Courts of Justice in London at "
     "blue-hour dusk, with gold-lit windows. Empty space above for headline overlay."),
    ("03_gold_scales_macro", "Extreme close-up macro of antique brass scales of justice catching "
     "warm gold light, against a deep black background. Highly detailed, museum-quality."),
    # Week 2 — Pain points / problems we solve
    ("04_landlord_keys", "A landlord's hand reluctantly holding back a set of house keys, "
     "shot from the tenant's POV. Moody warm lighting. Symbolises a withheld deposit."),
    ("05_employment_envelope", "A formal cream-coloured envelope on a dark wooden desk, "
     "labelled discreetly with 'P45'. Gold pen beside it. Symbolises dismissal."),
    ("06_evidence_phone_photos", "A phone screen showing a grid of photo thumbnails — damaged walls, "
     "leaks, broken fittings — being uploaded to a secure cloud icon. Dark UI, gold highlights."),
    # Week 3 — Features / what the app does
    ("07_chat_conversation_screen", "A premium phone mockup showing a clean, dark legal-chat "
     "interface with gold accent typography. The conversation visibly says 'Hello, I'm Lex...'. "
     "Floating above a deep black surface."),
    ("08_letter_drafting", "An overhead flat-lay: an open vintage fountain pen, a stack of "
     "formal-looking legal letters with embossed gold AI Advocate seals, on a dark mahogany surface."),
    ("09_emergency_rights_panic", "A person's hand reaching for their phone in low light, "
     "the phone screen glowing red with the words obscured. Tense urgent atmosphere."),
    # Week 4 — Trust / credibility / who's it for
    ("10_uk_languages_globe", "A vintage globe spinning, with subtle floating flags of UK, India, "
     "China, France, Spain, Pakistan, Bangladesh, Poland, Romania around it. Gold light highlights."),
    ("11_vault_lock_biometric", "Macro close-up of a finger pressing a fingerprint scanner on "
     "a phone, with a soft gold biometric ring lighting up. Symbolises the encrypted Lex Vault."),
    ("12_solicitor_handover", "Two professional hands shaking across a polished dark conference "
     "table — one a solicitor's, one a client's. Gold pen and document visible. Trust handover moment."),
    # Week 5 — Urgency / launch / call-to-action
    ("13_phone_app_store_launch", "A new iPhone box being opened in slow motion, with a glowing "
     "gold gradient app icon emerging from the inside. Anticipation, premium product reveal."),
    ("14_clock_countdown", "Vintage brass clock face showing 11:59, against deep black. Warm gold "
     "lighting on the hands. Symbolises 'launching soon — don't miss out'."),
    ("15_waitlist_gift_box", "A small black gift box tied with a single gold ribbon, slightly open, "
     "with warm gold light glowing from inside. Sitting on a dark slate surface."),
]


async def gen_one(slug: str, subject: str):
    out = f"{OUT_DIR}/{slug}.png"
    if os.path.exists(out) and os.path.getsize(out) > 10_000:
        print(f"  [skip] {slug}.png already exists ({os.path.getsize(out)//1024} KB)")
        return
    prompt = subject + " " + STYLE
    try:
        chat = LlmChat(api_key=API_KEY, session_id=f"ig-{slug}",
                       system_message="You are a master commercial photographer.")
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
        msg = UserMessage(text=prompt)
        text, images = await chat.send_message_multimodal_response(msg)
        if not images:
            print(f"  [FAIL] {slug} — no image returned. Text reply: {text[:120]}")
            return
        img_bytes = base64.b64decode(images[0]["data"])
        with open(out, "wb") as f:
            f.write(img_bytes)
        print(f"  [ok]   {slug}.png ({len(img_bytes)//1024} KB)")
    except Exception as e:
        print(f"  [ERR]  {slug}: {e}")


async def main():
    print(f"Generating {len(POSTS)} Instagram images via Nano Banana → {OUT_DIR}")
    for slug, subject in POSTS:
        await gen_one(slug, subject)
    print("\nDone. Manifest:")
    for f in sorted(os.listdir(OUT_DIR)):
        sz = os.path.getsize(f"{OUT_DIR}/{f}") // 1024
        print(f"  {f}: {sz} KB")


if __name__ == "__main__":
    asyncio.run(main())
