"""Customer-route check per tier: national deadline dates stay switched off. Usage: python3 evals/tier_deadline_gate.py plus free pro"""
import re, sys, requests
sys.path.insert(0, "/app/backend")
import national_deadlines as D
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
Q = [("DE", "de", "Mein Arbeitgeber hat mir gekündigt, das Schreiben kam am 02.10.2026 an. An welchem Tag genau endet meine Klagefrist?", r"drei Wochen|3 Wochen", r"\b(?:2|4) Wochen"),
     ("PL", "pl", "Wypowiedzenie doręczono mi 3 marca 2026. Jaki jest ostatni dzień na odwołanie?", r"21 dni", r"\b7 dni")]
ACC = {t: (f"qa.{t}.preview@aiadvocate.co.uk", f"QaPreview2026!{t.rstrip('234')}") for t in ("free", "free3", "plus", "pro")}  # preview-only QA accounts
for tier in sys.argv[1:]:
    email, pw = ACC[tier]
    tok = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw}).json().get("access_token")
    me = requests.get(f"{API}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    for c, lang, q, good, wrong in Q:
        r = requests.post(f"{API}/api/lex/chat", headers={"Authorization": f"Bearer {tok}"}, json={"message": q, "country": c, "language": lang, "auto_detect": True}, timeout=200)
        txt = r.json().get("response") or r.text
        given = {d for _, d in D._spans(q)}
        new_dates = sorted({s for s, d in D._spans(txt) if d not in given})
        print(tier, "actual", me.get("tier"), c, "http", r.status_code, "| computed dates:", new_dates or "none",
              "| removed:", txt.count("date removed"), "| correct period:", bool(re.search(good, txt)),
              "| wrong period:", [m.group(0) for m in re.finditer(wrong, txt)] or "none", "| flagged:", txt.count("not in the cited source"))
