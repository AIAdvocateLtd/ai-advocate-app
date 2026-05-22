"""Hue-shift the recycle bin to match the existing tile palette (files/hearing).
Calibrated by side-by-side comparison: previous +0.072 was too yellow/lime; the
target gold is amber-warm, so we use a gentler shift and slight saturation cut.
"""
from PIL import Image
import colorsys
import sys

src = sys.argv[1] if len(sys.argv) > 1 else "/app/frontend/public/icons/recycle.png"
dst = sys.argv[2] if len(sys.argv) > 2 else src

im = Image.open(src).convert("RGBA")
px = im.load()
w, h = im.size

HUE_SHIFT = 0.038          # ~+14° — copper → amber-gold (NOT all the way to yellow)
SAT_CAP   = 0.78           # cap saturation so highlights don't blow out
WARM_LOW  = 0.00
WARM_HIGH = 0.13

for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a == 0:
            continue
        rr, gg, bb = r / 255.0, g / 255.0, b / 255.0
        hh, ss, vv = colorsys.rgb_to_hsv(rr, gg, bb)
        if WARM_LOW <= hh <= WARM_HIGH or hh >= 0.92:
            hh = (hh + HUE_SHIFT) % 1.0
            if ss > SAT_CAP:
                ss = SAT_CAP
        rr2, gg2, bb2 = colorsys.hsv_to_rgb(hh, ss, vv)
        px[x, y] = (int(rr2 * 255), int(gg2 * 255), int(bb2 * 255), a)

im.save(dst, "PNG", optimize=True)
print(f"Wrote {dst}")