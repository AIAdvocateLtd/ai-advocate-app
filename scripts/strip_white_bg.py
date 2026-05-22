"""Make near-white/neutral-grey pixels transparent on the recycle bin PNG so the
tile blends with the dark dashboard like the other gold icons.

The Nano Banana render produces a flat neutral grey (~204,204,204) background
rather than true white. We detect "neutral" pixels by low chroma (max-min < band)
AND high luminance, then key them out with a soft alpha taper.
"""
from PIL import Image
import sys

src = sys.argv[1] if len(sys.argv) > 1 else "/app/frontend/public/icons/recycle.png"
dst = sys.argv[2] if len(sys.argv) > 2 else src

im = Image.open(src).convert("RGBA")
px = im.load()
w, h = im.size

CHROMA_THRESH = 18      # max(R,G,B) - min(R,G,B) <= this  → considered neutral
BRIGHT_THRESH = 170     # min channel >= this              → considered "light grey or whiter"
SOFT_BAND     = 30      # taper alpha over (BRIGHT_THRESH-band .. BRIGHT_THRESH) to avoid hard edges

for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        chroma = max(r, g, b) - min(r, g, b)
        if chroma <= CHROMA_THRESH:
            m = min(r, g, b)
            if m >= BRIGHT_THRESH:
                # Full transparent
                px[x, y] = (r, g, b, 0)
            elif m >= BRIGHT_THRESH - SOFT_BAND:
                fade = int(255 * (BRIGHT_THRESH - m) / SOFT_BAND)
                fade = max(0, min(255, fade))
                px[x, y] = (r, g, b, fade)

im.save(dst, "PNG", optimize=True)
print(f"Wrote {dst} ({im.size[0]}x{im.size[1]})")
