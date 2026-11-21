"""Live end-to-end reliability check of Lex's answer pipeline (real model). Usage: python3 lex_reliability.py <API> [ids]"""
import json, re, sys, time, requests

API = sys.argv[1]
H = {"Authorization": "Bearer " + requests.post(f"{API}/api/auth/login", json={"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}).json()["access_token"]}
CASES = [
    # id, country, lang, question, required-any regex, forbidden regex, (claim regex, citation url regex) or None, required url regex
    ("pl", "PL", "pl", "Pracodawca mnie zwolnił. Ile mam czasu na odwołanie do sądu pracy?", r"21 dni", r"\b7 dni\b|siedmiu dni",
     (r"21 dni", r"sejm\.gov\.pl.*#art-264"), r"sejm\.gov\.pl"),
    ("de", "DE", "de", "Mein Arbeitgeber hat mir gekündigt. Bis wann muss ich Kündigungsschutzklage erheben?", r"drei Wochen|3 Wochen", r"vier Wochen|zwei Wochen",
     (r"drei Wochen|3 Wochen", r"gesetze-im-internet\.de/kschg/__4"), r"gesetze-im-internet\.de"),
    ("es", "ES", "es", "Me han despedido. ¿Qué plazo tengo para reclamar contra el despido?", r"20 días|veinte días", r"30 días|treinta días",
     (r"20 días|veinte días", r"boe\.es"), r"boe\.es"),
    ("it", "IT", "it", "Sono stato licenziato. Entro quanto tempo devo impugnare il licenziamento?", r"60 giorni|sessanta giorni", None,
     (r"60 giorni|sessanta giorni", r"normattiva\.it.*604"), r"normattiva\.it"),
    ("uk", "GB", "en", "I was unfairly dismissed last week after 4 years. How long do I have to bring a claim?", r"three months|3 months", None,
     None, r"legislation\.gov\.uk|acas\.org\.uk"),
    ("eu", "ES", "en", "I live in Spain and bought a phone online from a German shop. It broke after 3 months. What are my rights?", r"Spain|Spanish", None,
     None, r"europa\.eu|boe\.es|gesetze-im-internet"),
    ("usfed", "US", "en", "A debt collector keeps calling me at work even though I told them my employer doesn't allow it. Is that allowed?", r"1692c|Fair Debt", None,
     (r"1692c", r"govinfo\.gov.*1692c"), r"govinfo\.gov"),
    ("tx", "US", "en", "My landlord in Texas has kept my whole security deposit a month after I moved out. What can I do?", r"Texas", None, None, None),
    ("xb", "GB", "en", "I live in Poland and work there for a German company. They fired me without notice. Which country's law applies and what can I do?", r"Poland|Polish", None, None, None),
]


def check(case):
    cid, c, lang, q, need, bad, claim, url_need = case
    t = time.time()
    r = requests.post(f"{API}/api/lex/chat", headers=H, json={"message": q, "country": c, "language": lang, "auto_detect": True}, timeout=200)
    d = r.json()
    txt, cites = d.get("response") or "", d.get("citations") or []
    res = {"id": cid, "http": r.status_code, "secs": round(time.time() - t, 1), "fails": []}
    if not re.search(need, txt, re.I):
        res["fails"].append(f"missing {need}")
    if bad and re.search(bad, txt, re.I):
        res["fails"].append(f"contains forbidden {bad}")
    urls = [x.get("url") or "" for x in cites]
    if url_need and not any(re.search(url_need, u) for u in urls):
        res["fails"].append(f"no citation matching {url_need}")
    if claim:
        by_n = {str(x.get("n")): x.get("url") or "" for x in cites}
        ok = False
        for m in re.finditer(claim[0], txt, re.I):  # the first citation marker after the claim (same or next line)
            nxt = re.search(r"(?:\s*\[\d+\])+", txt[m.end(): m.end() + 250])
            for n in re.findall(r"\d+", nxt.group(0) if nxt else ""):
                ok |= bool(re.search(claim[1], by_n.get(n, "")))
        res["claim_supported_by_matching_citation"] = ok
        if not ok:
            res["fails"].append(f"claim {claim[0]} not tied to a citation matching {claim[1]}")
    if cid == "tx":
        res["federal_used"] = any("govinfo" in u or "ecfr" in u for u in urls)
        if res["federal_used"]:
            res["fails"].append("federal source cited for a state-law question")
        res["limitation_stated"] = bool(re.search(r"could not|couldn't|not (?:been )?(?:able to )?(?:verif|confirm|retriev)|unverified|not confirmed", txt, re.I))
        if not res["limitation_stated"]:
            res["fails"].append("no limitation statement")
    if cid == "xb":
        res["names_both"] = bool(re.search(r"German", txt) and re.search(r"Poland|Polish", txt))
        if not res["names_both"]:
            res["fails"].append("does not name both jurisdictions")
    res["citations"] = [(x.get("n"), (x.get("title") or "")[:70], x.get("url")) for x in cites][:8]
    res["answer_head"] = txt[:700]
    return res


ids = sys.argv[2:] or [c[0] for c in CASES]
out = [check(c) for c in CASES if c[0] in ids]
for o in out:
    print(f"{o['id']:6} {'PASS' if not o['fails'] else 'FAIL'} {o['secs']}s {o['fails']}")
json.dump(out, open(f"/tmp/reliability_{int(time.time())}.json", "w"), ensure_ascii=False, indent=1)
