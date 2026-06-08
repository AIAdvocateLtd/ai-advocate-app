"""Bundle the 4 LinkedIn hero screenshots into a single A4-portrait PDF the
founder can tap, download, and share. One image per page, full-bleed, centered."""
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

SRC = Path("/app/frontend/public/instagram-pack/real-screens")
OUT = Path("/app/frontend/public/instagram-pack/linkedin-hero-pack.pdf")

# 4 hero shots in order — letter threat meter, chat, reply drafting, cost estimator
SHOTS = [
    ("11_letter_library.png",         "Letter Reader — threat meter"),
    ("21_ask_lex_typed.png",          "Ask Lex — chat in action"),
    ("12_letter_writer_modal.png",    "Letter Writer — three-tone reply drafting"),
    ("16_cost_result_premium.png",    "Lawyer cost estimator"),
]

PAGE_W, PAGE_H = A4
MARGIN = 36  # points (≈ 12.7mm)

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("AI Advocate — LinkedIn hero pack")
    c.setAuthor("AI Advocate")
    c.setSubject("4 hero screenshots for the LinkedIn launch post.")

    for fname, caption in SHOTS:
        src = SRC / fname
        if not src.exists():
            print(f"  ⚠ missing: {src}")
            continue
        img = ImageReader(str(src))
        iw, ih = img.getSize()

        # Caption strip at the top
        c.setFillColorRGB(0.10, 0.07, 0.0)
        c.rect(0, PAGE_H - 36, PAGE_W, 36, fill=1, stroke=0)
        c.setFillColorRGB(0.97, 0.79, 0.28)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 24, caption)

        # Available area below caption
        avail_w = PAGE_W - 2 * MARGIN
        avail_h = PAGE_H - 36 - 2 * MARGIN - 24  # leave room for footer
        scale = min(avail_w / iw, avail_h / ih)
        draw_w, draw_h = iw * scale, ih * scale
        x = (PAGE_W - draw_w) / 2
        y = MARGIN + 24 + (avail_h - draw_h) / 2

        # Soft drop-shadow
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillAlpha(0.15)
        c.roundRect(x + 4, y - 4, draw_w, draw_h, 12, fill=1, stroke=0)
        c.setFillAlpha(1.0)

        c.drawImage(img, x, y, width=draw_w, height=draw_h,
                    preserveAspectRatio=True, mask='auto')

        # Footer
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica", 9)
        c.drawCentredString(PAGE_W / 2, 18, "aiadvocate.co.uk · share this pack with your post")

        c.showPage()

    c.save()
    print(f"\n✓ PDF saved: {OUT}")
    size_kb = OUT.stat().st_size // 1024
    print(f"  {size_kb} KB")


if __name__ == "__main__":
    main()
