"""Refresh the bundled official German law XML (gesetze-im-internet.de downloads). Run in preview before a deploy:
python3 scripts_refresh_de_official.py — production cannot reach gesetze-im-internet.de, so it uses these copies."""
import pathlib
import sys

import httpx

LAWS = ["bgb", "kschg", "agg", "milog", "aufenthg_2004"]
OUT = pathlib.Path(__file__).parent / "data" / "de"

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for law in LAWS:
        r = httpx.get(f"https://www.gesetze-im-internet.de/{law}/xml.zip", timeout=60,
                      headers={"User-Agent": "AIAdvocate/1.0 (+https://aiadvocate.co.uk)"})
        if r.status_code != 200:
            sys.exit(f"{law}: HTTP {r.status_code}")
        (OUT / f"{law.split('_')[0]}.xml.zip").write_bytes(r.content)
        print(law, len(r.content))
