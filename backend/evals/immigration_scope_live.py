"""Live preview check of the UK immigration scope limit per tier. Usage: python3 evals/immigration_scope_live.py free plus pro"""
import sys, requests
sys.path.insert(0, "/app/backend")
import immigration_scope as S
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
PERSONAL = "The Home Office refused my Skilled Worker visa last week. Do I qualify to appeal, and what should I argue? Am I likely to win?"
GENERAL = "In general, what are the main requirements for a UK Skilled Worker visa?"
OTHER = "My employer offered me a settlement agreement in England. What is it?"
for tier in sys.argv[1:]:
    em, pw = f"qa.{tier}.preview@aiadvocate.co.uk", f"QaPreview2026!{tier.rstrip('2')}"
    h = {"Authorization": "Bearer " + requests.post(f"{API}/api/auth/login", json={"email": em, "password": pw}).json()["access_token"]}
    print(tier, "actual tier:", requests.get(f"{API}/api/auth/me", headers=h).json().get("tier"))
    for name, q, cat in (("personal", PERSONAL, None), ("general", GENERAL, "immigration"), ("non-immigration", OTHER, None)):
        r = requests.post(f"{API}/api/lex/chat", headers=h, json={"message": q, "country": "GB", "language": "en-GB",
                                                                  "category": cat}, timeout=240)
        t = (r.json().get("response") if r.ok else r.text) or ""
        t2 = t.replace(S.NOTE, "")
        hits = [rx.search(t2).group(0) for rx in S._PERSONAL if rx.search(t2)]
        print(f"  chat {name}: http {r.status_code} len {len(t)} note {'general information only' in t} personal_left {hits or 'none'}")
        if name == "personal":
            open(f"/tmp/imm_{tier}_personal.txt", "w").write(t)
    ids = [x["id"] for x in requests.get(f"{API}/api/letters/templates").json()]
    print("  templates hide immigration:", not ({"immigration_letter", "asylum_statement"} & set(ids)))
    for path, body in (("/api/letters/generate", {"template_id": "immigration_letter", "your_name": "A", "recipient": "Home Office", "facts": "ILR"}),
                       ("/api/letters/generate", {"template_id": "custom", "your_name": "A", "recipient": "UK Visas and Immigration",
                                                 "facts": "Representations for my spouse visa refusal"}),
                       ("/api/lex/practice", {"role": "immigration", "message": "hi", "language": "en-GB"}),
                       ("/api/outcome/predict", {"case_summary": "My UK visa was refused by the Home Office, will my appeal win?", "country": "GB"})):
        r = requests.post(API + path, headers=h, json=body, timeout=60)
        print(f"  {path} {body.get('template_id') or body.get('role') or ''}: http {r.status_code} restricted {r.status_code == 403 and 'Immigration Advice Authority' in r.text}")
