"""Generate iOS App Store screenshots (1290x2796) from existing Play Store PNGs.

Takes 1080x1920 assets from frontend/public/play_store and produces iPhone 6.9"
sized screenshots with a subtle gold header strip and dark padding to match brand.

Run: python3 scripts/gen_ios_screenshots.py
Output: /app/marketing_screenshots/ios/*.png
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# iPhone 6.9" required by Apple for iPhone 15/16 Pro Max
TARGET_W, TARGET_H = 1290, 2796

# AI Advocate brand colours (matching frontend App.css)
BG = (12, 15, 20)          # near-black canvas
GOLD = (212, 175, 55)      # brand gold
TEXT = (245, 240, 225)     # warm off-white for readability on dark

SRC_DIR = Path("/app/frontend/public/play_store")
OUT_DIR = Path("/app/marketing_screenshots/ios")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Screens to produce: (source_filename, caption_line1, caption_line2)
SCREENS = [
    ("phone_01_home.png",
     "Your pocket legal AI",
     "Ask any question, in plain English"),
    ("phone_02_ask_lex.png",
     "Meet Lex, your legal AI",
     "Trained on UK law · Cites real statutes"),
]


def _pick_font(size: int):
    """Prefer a bundled TrueType font; fall back to PIL default if none exist."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_screenshot(src_name: str, headline: str, subhead: str, out_name: str) -> Path:
    src_path = SRC_DIR / src_name
    src = Image.open(src_path).convert("RGB")

    # Reserve top ~18% of the canvas for the gold caption header
    header_h = int(TARGET_H * 0.18)
    inner_top = header_h
    inner_h = TARGET_H - inner_top

    # Scale the source image to fit inside (TARGET_W, inner_h) preserving aspect ratio
    src_w, src_h = src.size
    scale = min(TARGET_W / src_w, inner_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    src_resized = src.resize((new_w, new_h), Image.LANCZOS)

    # Compose on brand-dark canvas
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), BG)
    x_offset = (TARGET_W - new_w) // 2
    y_offset = inner_top + (inner_h - new_h) // 2
    canvas.paste(src_resized, (x_offset, y_offset))

    # Draw the header captions
    draw = ImageDraw.Draw(canvas)
    headline_font = _pick_font(96)
    subhead_font = _pick_font(50)

    # Centre-align headline in the top half of the header strip
    hl_bbox = draw.textbbox((0, 0), headline, font=headline_font)
    hl_w = hl_bbox[2] - hl_bbox[0]
    hl_x = (TARGET_W - hl_w) // 2
    hl_y = int(header_h * 0.30)
    draw.text((hl_x, hl_y), headline, font=headline_font, fill=GOLD)

    sh_bbox = draw.textbbox((0, 0), subhead, font=subhead_font)
    sh_w = sh_bbox[2] - sh_bbox[0]
    sh_x = (TARGET_W - sh_w) // 2
    sh_y = int(header_h * 0.62)
    draw.text((sh_x, sh_y), subhead, font=subhead_font, fill=TEXT)

    out_path = OUT_DIR / out_name
    canvas.save(out_path, "PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    for i, (src, h, sh) in enumerate(SCREENS, start=1):
        out = make_screenshot(src, h, sh, f"ios_phone_69_{i:02d}.png")
        print(f"[ok] {out} ({out.stat().st_size // 1024} KB)")
