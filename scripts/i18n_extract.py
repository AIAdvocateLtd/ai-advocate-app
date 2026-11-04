"""Extract translatable UI text from the React source + public HTML pages.

Usage: python3 /app/scripts/i18n_extract.py  -> writes /app/scripts/i18n_source.json
Re-run after adding new screens, then run i18n_translate.py.
"""
import html as _html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

SRC = Path("/app/frontend/src")
PUB = Path("/app/frontend/public")
SKIP_FILES = {"i18n.js", "AdminFinance.js", "AdminSubscribers.js", "AdminStripeResync.js", "AdminLexLessons.js",
              "FirmPortal.js", "FirmSign.jsx", "sentry.js", "analytics.js", "nativeBridge.js", "vaultCrypto.js",
              "vaultBiometric.js", "appBadge.js", "icons.js"}
HTML_PAGES = ["welcome.html", "guides/*.html", "privacy.html", "terms.html", "*.html"]
SKIP_HTML = {"intro-pack.html", "pitch-card.html", "index.html"}

CODEY = re.compile(r"var\(--|rgba?\(|\bpx\b|\d+px|https?://|/api/|=>|\.js\b|\.png|\.svg|^#|^\.|^[\w-]+:[\w-]+$|"
                   r"\b(flex|grid|inline|absolute|relative|solid|dashed|ease|bold|uppercase|nowrap|pointer|center)\b|"
                   r"\{|\}|\$\{|^\s*[a-z]+[A-Z]\w*\s*$|^[a-z0-9_\-./:]+$|^[A-Z0-9_]+$|\\u|data-testid|className")
WORD = re.compile(r"[A-Za-z]{3,}")


def keep(s: str) -> bool:
    s = s.strip()
    if len(s) < 2 or len(s) > 1200 or not WORD.search(s):
        return False
    if CODEY.search(s) or re.search(r"function |\]\.|\.map\(|\(\s*$|^[,\]\)]\s*[\],\)]|failed$|^App |_\w+:", s):
        return False
    if " " not in s and not re.fullmatch(r"[A-Z][a-z]+[!?.:]?", s):
        return False
    return True


def from_js(text: str) -> set:
    out = set()
    for m in re.finditer(r"[>}]([^<>{}`]+?)(?=[<{])", text):
        seg = _html.unescape(" ".join(m.group(1).split()))
        seg = re.sub(r"^[.,;:·—–\-)\s]+", "", seg)
        seg = re.sub(r"[\s(:]+$", "", seg)
        if keep(seg) and not re.search(r"[;=]|&&|\|\||\)\s*$", seg):
            out.add(seg)
    for rx in (r'"((?:[^"\\\n]|\\.){0,1200})"', r"'((?:[^'\\\n]|\\.){0,1200})'", r"`([^`$\\]{0,1200})`"):
        for m in re.finditer(rx, text):
            s = m.group(1).replace("\\'", "'").replace('\\"', '"').replace("\\n", " ")
            s = " ".join(s.split())
            if keep(s):
                out.add(s)
    return out


class _P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.out = set()

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "code"):
            self.skip += 1
        for k, v in attrs:
            if k in ("placeholder", "title", "aria-label", "alt") and v and keep(v):
                self.out.add(" ".join(v.split()))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "code") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        s = " ".join(data.split())
        if not self.skip and s and WORD.search(s) and len(s) <= 2000:
            self.out.add(s)


def main():
    strings = set()
    for f in list(SRC.glob("*.js")) + list(SRC.glob("*.jsx")):
        if f.name not in SKIP_FILES:
            strings |= from_js(f.read_text(errors="ignore"))
    seen = set()
    for pat in HTML_PAGES:
        for f in PUB.glob(pat):
            if f.name in SKIP_HTML or f in seen:
                continue
            seen.add(f)
            p = _P()
            p.feed(f.read_text(errors="ignore"))
            strings |= p.out
    be = Path("/app/backend")
    for m in re.finditer(r'HTTPException\(\s*\d+\s*,\s*(?:detail\s*=\s*)?"([^"{}\n]{4,300})"', (be / "server.py").read_text()):
        if WORD.search(m.group(1)):
            strings.add(" ".join(m.group(1).split()))
    for m in re.finditer(r'^\s*"([A-Z][^"{}\n]{4,120})", (?:limit|end|due|exp|early|when|co|final|earliest)\b',
                         (be / "deadline_calc.py").read_text(), re.M):
        strings.add(m.group(1))
    fb = Path("/app/scripts/i18n_fallback.json")  # English fallbacks from i18n.js (see README note in this file)
    if fb.exists():
        strings |= set(json.loads(fb.read_text()))
    out = sorted(strings)
    Path("/app/scripts/i18n_source.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(len(out), "strings,", sum(len(s) for s in out), "chars,", len(seen), "html pages")


if __name__ == "__main__":
    main()
