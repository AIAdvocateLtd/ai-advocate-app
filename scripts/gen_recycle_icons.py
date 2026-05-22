"""Generate 4 candidate Recycle Bin tile icons for AI Advocate.
Matches the existing photorealistic embossed-3D-gold aesthetic of the other dashboard
tiles (files.png, hearing.png, etc.). Each variant explores a different styling.
Outputs: /app/frontend/public/icons/recycle_v{1..4}.png
"""
import asyncio, os, base64, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from emergentintegrations.llm.chat import LlmChat, UserMessage

API_KEY = os.environ["EMERGENT_LLM_KEY"]
OUT_DIR = Path("/app/frontend/public/icons")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_STYLE = (
    "Photorealistic 3D embossed solid GOLD icon, polished metallic gold with soft "
    "specular highlights, deep amber shadows, ornate vintage law-firm aesthetic, "
    "centered, pure transparent background (PNG, no scene, no text, no watermark), "
    "256x256, isolated subject only, dramatic studio lighting from upper-left, "
    "rich warm tones matching a luxury legal app. NO words, NO labels."
)

PROMPTS = {
    "recycle_v1": (
        "A classic ornate vintage gold trash bin / waste basket with a domed hinged lid, "
        "art-deco engraved vertical panels on the body, small handle on top. " + BASE_STYLE
    ),
    "recycle_v2": (
        "A luxurious gold cylindrical refuse bin with an angled open lid revealing "
        "the interior, decorative laurel-wreath relief around the rim, slim profile. "
        + BASE_STYLE
    ),
    "recycle_v3": (
        "A modern minimalist gold trash can with a foot pedal, smooth polished surface, "
        "subtle reflections, slightly tapered cylindrical body, closed flat lid. "
        + BASE_STYLE
    ),
    "recycle_v4": (
        "A heraldic golden chalice-shaped recycle bin with the classic three-arrow recycle "
        "symbol embossed on the front panel, ornate footed base, regal British look. "
        + BASE_STYLE
    ),
}


async def generate(label: str, prompt: str) -> Path | None:
    chat = LlmChat(api_key=API_KEY, session_id=f"aa-icon-{label}",
                   system_message="You generate single-subject icon images on transparent backgrounds.")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    msg = UserMessage(text=prompt)
    try:
        text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        print(f"[{label}] error: {e}")
        return None
    if not images:
        print(f"[{label}] no image returned. text={text[:120]!r}")
        return None
    img = images[0]
    out = OUT_DIR / f"{label}.png"
    out.write_bytes(base64.b64decode(img["data"]))
    print(f"[{label}] OK → {out} ({out.stat().st_size} bytes)")
    return out


async def main():
    tasks = [generate(k, v) for k, v in PROMPTS.items()]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
