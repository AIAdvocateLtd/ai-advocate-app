"""Compose Apple App Store screenshots (1290x2796) from captured landing-page shots.

Takes JPEGs captured at 430x932 CSS resolution, upscales via LANCZOS to Apple's
required iPhone 6.9" size, and stacks them onto a branded dark canvas with a
gold caption band at the top.

Run: python3 scripts/finalize_ios_screenshots.py
Output: /app/marketing_screenshots/ios/final/*.png
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

TARGET_W, TARGET_H = 1290, 2796
BG = (10, 12, 16)
GOLD = (212, 175, 55)
TEXT = (245, 240, 225)

BASE = Path("/root/.emergent/automation_output")
OUT = Path("/app/marketing_screenshots/ios/final")
OUT.mkdir(parents=True, exist_ok=True)

# ordered oldest -> newest of the shots we just captured
SHOTS = [
    ("20260910_144958/ios_shot_01_landing.jpeg",
     "Your pocket legal AI",
     "Real UK law · 11 languages · under 60 seconds"),
    ("20260910_145302/features1.jpeg",
     "An entire law firm",
     "Ask Lex anything · powered by GPT-5.2 & Claude Sonnet"),
    ("20260910_145319/features2.jpeg",
     "Built for the moments that matter",
     "Evidence · Court Prep · Emergency Rights · Encrypted Vault"),
    ("20260910_145334/pricing.jpeg",
     "Start free · upgrade when you need to",
     "No card required · No long contracts · Cancel any time"),
]


def _pick_font(size: int):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(text: str, font, draw, max_width: int) -> list[str]:
    """Naive width-aware word wrap."""
    words = text.split()
    lines: list[str] = []
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def compose(src_rel: str, headline: str, subhead: str, out_name: str) -> Path:
    src = Image.open(BASE / src_rel).convert("RGB")

    # Header takes top ~20% of the canvas
    header_h = int(TARGET_H * 0.20)
    inner_top = header_h
    inner_h = TARGET_H - inner_top - 30  # small bottom padding

    # Scale the source shot to fit inner area preserving aspect ratio
    src_w, src_h = src.size
    scale = min(TARGET_W / src_w, inner_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    scaled = src.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (TARGET_W, TARGET_H), BG)
    x_offset = (TARGET_W - new_w) // 2
    y_offset = inner_top + (inner_h - new_h) // 2
    canvas.paste(scaled, (x_offset, y_offset))

    draw = ImageDraw.Draw(canvas)
    hl_font = _pick_font(88)
    sh_font = _pick_font(44)
    max_text_width = TARGET_W - 120

    # Headline (wrap if needed)
    hl_lines = _wrap(headline, hl_font, draw, max_text_width)
    y = int(header_h * 0.25)
    for line in hl_lines:
        w = draw.textbbox((0, 0), line, font=hl_font)[2]
        draw.text(((TARGET_W - w) // 2, y), line, font=hl_font, fill=GOLD)
        y += int(hl_font.size * 1.05)

    # Subhead
    sh_lines = _wrap(subhead, sh_font, draw, max_text_width)
    y += 14
    for line in sh_lines:
        w = draw.textbbox((0, 0), line, font=sh_font)[2]
        draw.text(((TARGET_W - w) // 2, y), line, font=sh_font, fill=TEXT)
        y += int(sh_font.size * 1.20)

    out_path = OUT / out_name
    canvas.save(out_path, "PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    for i, (src, h, sh) in enumerate(SHOTS, start=1):
        p = BASE / src
        if not p.exists():
            print(f"[skip] {src} not found")
            continue
        out = compose(src, h, sh, f"appstore_iphone69_{i:02d}.png")
        w, h_dim = Image.open(out).size
        print(f"[ok] {out.name}  {w}x{h_dim}  {out.stat().st_size // 1024} KB")
