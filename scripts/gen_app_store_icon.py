"""Generate the 1024×1024 App Store icon from the existing AI Advocate logo.

Apple App Store requirements:
  • Exactly 1024 × 1024 px.
  • Pure RGB (NO alpha channel / transparency — Apple rejects PNGs with alpha).
  • Pure JPEG OR PNG (no GIF/HEIC).
  • Dark `#0a0a0a` background (matches the app theme + splash screen).
  • No rounded corners or shadow (Apple applies these at render time).

We take the existing transparent-bg logo, downscale it to ~78% of the canvas,
centre it on a solid black background, and write to:
    /app/frontend/public/icons/app-icon-1024.png
"""
from PIL import Image
import os

SRC = "/app/frontend/public/assets/logo-transparent.png"
DST = "/app/frontend/public/icons/app-icon-1024.png"
SIZE = 1024
BG_COLOR = (10, 10, 10)   # matches the dashboard background --bg
PADDING_RATIO = 0.11      # leaves a comfortable margin around the mark

# 1. Canvas
canvas = Image.new("RGB", (SIZE, SIZE), BG_COLOR)

# 2. Load + downscale the logo, preserving aspect ratio
logo = Image.open(SRC).convert("RGBA")
inner = int(SIZE * (1 - 2 * PADDING_RATIO))
lw, lh = logo.size
scale = min(inner / lw, inner / lh)
new_size = (int(lw * scale), int(lh * scale))
logo_scaled = logo.resize(new_size, Image.LANCZOS)

# 3. Composite with alpha onto the dark canvas
ox = (SIZE - new_size[0]) // 2
oy = (SIZE - new_size[1]) // 2
canvas.paste(logo_scaled, (ox, oy), logo_scaled)

# 4. Save (RGB only, no alpha — Apple's hard requirement)
canvas.save(DST, "PNG", optimize=True)
print(f"OK → {DST}  ({SIZE}x{SIZE}, RGB, {os.path.getsize(DST):,} bytes)")
