"""Lex reliability guards: cross-chat memory gate, research-failure handling, citation checks, UK nation detection."""
import os
import re
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------- cross-conversation memory
# Off unless the platform flag is on AND the customer has explicitly opted in (no opt-in UI exists yet).


def cross_memory_enabled(user: dict) -> bool:
    return os.environ.get("LEX_CROSS_MEMORY_ENABLED", "") == "1" and \
        bool(((user or {}).get("memory_consent") or {}).get("cross_chat") is True)


async def build_cross_memory(db, user: dict, session_id: str, decrypt: Callable) -> Tuple[str, List[dict]]:
    if not cross_memory_enabled(user):
        return "", []
    pipeline = [
        {"$match": {"user_id": user["id"], "session_id": {"$ne": session_id}}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$session_id", "first_message": {"$last": "$user_message"},
                    "category": {"$first": "$category"}, "last_at": {"$first": "$created_at"}}},
        {"$sort": {"last_at": -1}}, {"$limit": 4},
    ]
    indexed = []
    try:
        async for s in db.conversations.aggregate(pipeline):
            try:
                txt = (decrypt(s.get("first_message")) or "").replace("\n", " ").strip()
            except Exception:
                continue
            if txt:
                indexed.append({"n": len(indexed) + 1, "session_id": s["_id"],
                                "topic": txt[:90] + ("…" if len(txt) > 90 else ""), "category": s.get("category") or "ask_lex"})
    except Exception:
        return "", []
    if not indexed:
        return "", []
    lines = "\n".join(f"#{c['n']} [{c['category']}] {c['topic']}" for c in indexed)
    block = ("\n\nOTHER, SEPARATE CONVERSATIONS THIS CUSTOMER HAS HAD (shown with their consent):\n" + lines +
             "\n\nSEPARATE-MATTERS RULE: these are different legal matters. Never import facts, dates, names or amounts from "
             "them into this answer. Only if the NEW question names the same specific person, company, landlord, property or "
             "contract, say so explicitly (e.g. 'In a separate conversation you mentioned…'), ask the customer to confirm the "
             "detail is the same before relying on it, and add the [CONNECTED_TO: #N short topic] line. Otherwise omit it.")
    return block, indexed


# ---------------------------------------------------------------- risk + research availability
HIGH_RISK_RE = re.compile(
    r"\b(evict\w*|possession|bailiff\w*|homeless\w*|section (8|21|173)|notice to (quit|leave)|dismiss\w*|sacked|fired|"
    r"locked (me )?out|lock(ed|ing)? me out|changed the locks?|kick(ed|ing)? (me|us) out|thr(ew|own) (me|us) out|"
    r"(made|making) (me|us) leave|(belongings|things|stuff) (on|in|into) the street|illegal(ly)? evict\w*|"
    r"tribunal|redundan\w*|deport\w*|removal|asylum|overstay\w*|visa|ilr|indefinite leave|"
    r"refus\w* (my |the |our )?(visa|asylum|leave|application|claim|benefit|entry|settlement|citizenship)|arrest\w*|charged|"
    r"police|court|hearing|summons|injunction|deadline|time limit|limitation|appeal|domestic abuse|non-molestation|"
    r"custody|child arrangements|social services|bankrupt\w*|ccj|county court judgment|enforcement|repossess\w*|"
    r"prosecut\w*|criminal|offence|bail|prison|sentenc\w*|harass\w*|discriminat\w*)\b", re.I)
HIGH_RISK_CATEGORIES = {"court_prep", "employment", "immigration", "medical_negligence"}
RESEARCH_FAILED = {"quota_exhausted", "unavailable", "no_results", "not_configured"}

TOPIC_RES = {
    "employment": re.compile(r"\b(employ\w*|jobs?|dismiss\w*|sacked|fired|redundan\w*|tribunal|acas|wages?|boss|workplace)\b", re.I),
    "housing": re.compile(r"\b(landlords?|tenan\w*|rent\w*|evict\w*|deposits?|section (8|21|173)|notice to (quit|leave)|"
                          r"housing|flat|house|property|occupation contract)\b", re.I),
    "immigration": re.compile(r"\b(visas?|ilr|indefinite leave|settle\w*|citizen\w*|naturalis\w*|home office|asylum|"
                              r"overstay\w*|immigra\w*|brp|evisa)\b", re.I),
    "benefits": re.compile(r"\b(benefits?|universal credit|pip|esa|dwp|reconsideration|disability payment)\b", re.I),
    "family": re.compile(r"\b(divorc\w*|separat\w*|custody|child arrangements?|child maintenance|family court|"
                         r"ex-?(wife|husband|partner))\b", re.I),
    "court": re.compile(r"\b(court|claim form|defence|ccj|summons|hearing|small claims?|simple procedure|sheriff)\b", re.I),
}
NEXT_STEPS = {
    "employment": "Acas helpline 0300 123 1100 (acas.org.uk); in Northern Ireland the Labour Relations Agency (lra.org.uk)",
    "housing": "Shelter (England), Shelter Cymru (Wales), Shelter Scotland, Housing Advice NI, or your local council's housing team",
    "immigration": "GOV.UK visa pages and a regulated immigration adviser (OISC-registered adviser or solicitor)",
    "benefits": "Citizens Advice, GOV.UK (DWP), mygov.scot (Social Security Scotland) or nidirect (Northern Ireland)",
    "family": "GOV.UK family court guidance, Citizens Advice, or a family solicitor (Law Society 'Find a Solicitor')",
    "court": "the court or tribunal named on your papers, GOV.UK court guidance, and Citizens Advice",
    "general": "Citizens Advice (citizensadvice.org.uk) or a solicitor via the Law Society's 'Find a Solicitor'",
}


def topics_of(text: str) -> List[str]:
    return [t for t, rx in TOPIC_RES.items() if rx.search(text or "")] or ["general"]


def risk_level(message: str, category: Optional[str]) -> str:
    return "high" if (category in HIGH_RISK_CATEGORIES or HIGH_RISK_RE.search(message or "")) else "low"


def research_block(status: str, risk: str, topics: List[str]) -> str:
    if status == "ok":
        return ("\n\nSOURCE HONESTY: only the numbered sources above were retrieved. Do not say they were 'independently "
                "verified', and do not claim you checked anything beyond them.")
    if status not in RESEARCH_FAILED:
        return ""
    steps = "; ".join(NEXT_STEPS[t] for t in topics if t in NEXT_STEPS)
    out = ("\n\nLIVE LEGAL RESEARCH WAS NOT AVAILABLE FOR THIS ANSWER (no current sources were retrieved).\n"
           "- You MUST NOT say or imply that you checked, looked up or verified current legislation, guidance or case law.\n"
           "- Early in the answer, tell the customer in one plain sentence (in their language) that you could not check "
           "current official sources just now, so they should confirm key points before acting.\n"
           "- Do not use numbered citations like [1]. Do not give URLs to specific pages; name the official organisation instead.\n"
           "- If you are not certain of a section number or case name, do not give one.")
    if risk == "high":
        out += ("\n- THIS IS A HIGH-RISK MATTER. Give the general principles and the options, but NO definitive conclusions "
                "(e.g. do not say a notice 'is invalid', a claim 'will succeed', or give an exact deadline date unless the app "
                "calculated it below). Set [CONFIDENCE: LOW] or [CONFIDENCE: MEDIUM].\n"
                f"- End the main answer with clear official next steps: {steps}.")
    return out


# ---------------------------------------------------------------- deterministic notes (inserted before disclaimer/markers)
NOTES = {
    "research": {
        "en": "Note: I couldn't check current official sources for this answer, so it is based on general legal knowledge. Please confirm the key points with an official source or a qualified adviser before you act.",
        "es": "Nota: no he podido consultar fuentes oficiales actualizadas para esta respuesta, así que se basa en conocimientos jurídicos generales. Confirme los puntos clave con una fuente oficial o un asesor cualificado antes de actuar.",
        "fr": "Remarque : je n'ai pas pu consulter de sources officielles à jour pour cette réponse ; elle repose sur des connaissances juridiques générales. Vérifiez les points essentiels auprès d'une source officielle ou d'un conseiller qualifié avant d'agir.",
        "ar": "ملاحظة: لم أتمكن من مراجعة المصادر الرسمية الحالية لهذه الإجابة، لذا فهي مبنية على معرفة قانونية عامة. يُرجى التحقق من النقاط الأساسية من مصدر رسمي أو مستشار مؤهل قبل اتخاذ أي إجراء.",
        "pl": "Uwaga: nie mogłem sprawdzić aktualnych oficjalnych źródeł dla tej odpowiedzi, więc opiera się ona na ogólnej wiedzy prawnej. Przed podjęciem działań potwierdź kluczowe kwestie w oficjalnym źródle lub u wykwalifikowanego doradcy.",
        "de": "Hinweis: Ich konnte für diese Antwort keine aktuellen offiziellen Quellen prüfen; sie beruht auf allgemeinem Rechtswissen. Bitte bestätigen Sie die wichtigsten Punkte bei einer offiziellen Stelle oder einer qualifizierten Beratung, bevor Sie handeln.",
        "hi": "नोट: मैं इस उत्तर के लिए वर्तमान आधिकारिक स्रोतों की जाँच नहीं कर सका, इसलिए यह सामान्य कानूनी जानकारी पर आधारित है। कोई कदम उठाने से पहले मुख्य बातों की पुष्टि किसी आधिकारिक स्रोत या योग्य सलाहकार से करें।",
        "ur": "نوٹ: میں اس جواب کے لیے موجودہ سرکاری ذرائع چیک نہیں کر سکا، اس لیے یہ عمومی قانونی معلومات پر مبنی ہے۔ کوئی قدم اٹھانے سے پہلے اہم نکات کی تصدیق کسی سرکاری ذریعے یا مستند مشیر سے کریں۔",
        "it": "Nota: non ho potuto consultare fonti ufficiali aggiornate per questa risposta, quindi si basa su conoscenze giuridiche generali. Verifica i punti chiave con una fonte ufficiale o un consulente qualificato prima di agire.",
        "pt": "Nota: não consegui consultar fontes oficiais atualizadas para esta resposta, por isso baseia-se em conhecimentos jurídicos gerais. Confirme os pontos principais junto de uma fonte oficial ou de um consultor qualificado antes de agir.",
        "zh": "提示：本回答未能查阅最新的官方来源，因此基于一般法律知识。采取行动前，请通过官方来源或合格顾问核实关键要点。",
    },
    "cut": {
        "en": "This answer was cut short. Reply \"continue\" and Lex will finish it.",
        "es": "Esta respuesta se ha cortado. Responda \"continuar\" y Lex la terminará.",
        "fr": "Cette réponse a été coupée. Répondez « continuer » et Lex la terminera.",
        "ar": "انقطعت هذه الإجابة. اكتب \"تابع\" وسيكملها Lex.",
        "pl": "Ta odpowiedź została ucięta. Napisz „kontynuuj”, a Lex ją dokończy.",
        "de": "Diese Antwort wurde abgeschnitten. Antworten Sie mit „weiter“ und Lex schreibt sie zu Ende.",
        "hi": "यह उत्तर बीच में कट गया। \"जारी रखें\" लिखें और Lex इसे पूरा करेगा।",
        "ur": "یہ جواب ادھورا رہ گیا۔ \"جاری رکھیں\" لکھیں اور Lex اسے مکمل کرے گا۔",
        "it": "Questa risposta è stata interrotta. Rispondi \"continua\" e Lex la completerà.",
        "pt": "Esta resposta foi interrompida. Responda \"continuar\" e o Lex termina-a.",
        "zh": "此回答被截断了。回复“继续”，Lex 会把它写完。",
    },
    "citations": {
        "en": "Source check: some legal references in this answer could not be matched to a source the app retrieved, so unmatched links or numbers were removed. Check any case or section on legislation.gov.uk or caselaw.nationalarchives.gov.uk before relying on it.",
        "es": "Verificación de fuentes: algunas referencias legales de esta respuesta no coinciden con una fuente obtenida por la app, por lo que se eliminaron los enlaces o números no verificados. Compruebe cualquier caso o artículo en legislation.gov.uk o caselaw.nationalarchives.gov.uk antes de confiar en él.",
        "fr": "Vérification des sources : certaines références juridiques de cette réponse ne correspondent à aucune source récupérée par l'application ; les liens ou numéros non vérifiés ont été retirés. Vérifiez toute décision ou disposition sur legislation.gov.uk ou caselaw.nationalarchives.gov.uk avant de vous y fier.",
        "ar": "التحقق من المصادر: تعذّر مطابقة بعض المراجع القانونية في هذه الإجابة مع مصدر استرجعه التطبيق، لذا حُذفت الروابط أو الأرقام غير المطابقة. تحقق من أي قضية أو مادة عبر legislation.gov.uk أو caselaw.nationalarchives.gov.uk قبل الاعتماد عليها.",
        "pl": "Sprawdzenie źródeł: niektórych odniesień prawnych w tej odpowiedzi nie udało się dopasować do źródła pobranego przez aplikację, więc niezweryfikowane linki lub numery usunięto. Sprawdź każdą sprawę lub przepis na legislation.gov.uk lub caselaw.nationalarchives.gov.uk, zanim na nich polegasz.",
        "de": "Quellenprüfung: Einige rechtliche Verweise in dieser Antwort konnten keiner von der App abgerufenen Quelle zugeordnet werden; nicht zuordenbare Links oder Nummern wurden entfernt. Prüfen Sie Urteile oder Paragrafen auf legislation.gov.uk oder caselaw.nationalarchives.gov.uk, bevor Sie sich darauf verlassen.",
        "hi": "स्रोत जाँच: इस उत्तर के कुछ कानूनी संदर्भ ऐप द्वारा प्राप्त किसी स्रोत से मेल नहीं खाए, इसलिए असत्यापित लिंक या नंबर हटा दिए गए। किसी भी केस या धारा पर भरोसा करने से पहले legislation.gov.uk या caselaw.nationalarchives.gov.uk पर जाँच लें।",
        "ur": "ذرائع کی جانچ: اس جواب کے کچھ قانونی حوالے ایپ کے حاصل کردہ کسی ذریعے سے میل نہیں کھا سکے، اس لیے غیر تصدیق شدہ لنکس یا نمبر ہٹا دیے گئے۔ کسی بھی کیس یا دفعہ پر انحصار سے پہلے legislation.gov.uk یا caselaw.nationalarchives.gov.uk پر جانچ کریں۔",
        "it": "Verifica delle fonti: alcuni riferimenti normativi di questa risposta non corrispondono a una fonte recuperata dall'app, quindi link o numeri non verificati sono stati rimossi. Controlla ogni sentenza o articolo su legislation.gov.uk o caselaw.nationalarchives.gov.uk prima di farvi affidamento.",
        "pt": "Verificação de fontes: algumas referências legais desta resposta não correspondem a uma fonte obtida pela app, por isso os links ou números não verificados foram removidos. Confirme qualquer caso ou secção em legislation.gov.uk ou caselaw.nationalarchives.gov.uk antes de confiar nela.",
        "zh": "来源核查：本回答中的部分法律引用无法与应用检索到的来源对应，因此已删除未核实的链接或编号。在依赖任何判例或条文之前，请在 legislation.gov.uk 或 caselaw.nationalarchives.gov.uk 上核实。",
    },
}


def note(kind: str, language: str) -> str:
    return NOTES[kind].get((language or "en")[:2].lower(), NOTES[kind]["en"])


def append_cut_note(text: str, language: str) -> str:
    return (text or "").rstrip() + "\n\n" + note("cut", language)


_CUTS = ("[CONFIDENCE:", "[SOURCES:", "[CONNECTED_TO:", "[[PDF:", "\nDisclaimer:", "\n**Disclaimer")


def insert_before_tail(text: str, extra: str) -> str:
    cut = min([i for i in (text.find(c) for c in _CUTS) if i >= 0] or [len(text)])
    return text[:cut].rstrip() + "\n\n" + extra + "\n\n" + text[cut:].lstrip("\n")


# ---------------------------------------------------------------- citation verification
OFFICIAL_DOMAINS = (
    "gov.uk", "gov.wales", "gov.scot", "mygov.scot", "acas.org.uk", "lra.org.uk", "citizensadvice.org.uk", "cas.org.uk",
    "adviceni.net", "shelter.org.uk", "sheltercymru.org.uk", "housingadviceni.org", "lawsociety.org.uk", "lawscot.org.uk",
    "lawsoc-ni.org", "judiciary.uk", "scotcourts.gov.uk", "bailii.org", "nhs.uk", "ico.org.uk",
    "financial-ombudsman.org.uk", "supremecourt.uk", "nidirect.gov.uk",
)
_MD_LINK = re.compile(r"\[([^\]\n]{1,200})\]\((https?://[^)\s]+)\)")
_URL = re.compile(r"https?://[^\s)\]>\"'<]+")
_NUM_MARK = re.compile(r"\s?\[(\d{1,2}(?:\s*[,\u2013-]\s*\d{1,2})*)\](?!\()")
_ACT = re.compile(r"\b((?:[A-Z][A-Za-z'’]+|of|and|the|\(\w+\))(?:\s+(?:[A-Z][A-Za-z'’]+|of|and|the|\([A-Za-z ]+\)))*\s+Act)\s+((?:19|20)\d{2})")
_SECTION = re.compile(r"\b(?:section|s\.?)\s?(\d{1,4}[A-Z]?)\b", re.I)
_NEUTRAL = re.compile(r"\[(?:19|20)\d{2}\]\s+(?:UKSC|UKHL|UKPC|EWCA|EWHC|EWFC|EWCOP|UKUT|UKFTT|UKEAT|EAT|CSIH|CSOH|HCJAC|"
                      r"NICA|NIQB|NIKB|NICh|NIFam|AC|QB|KB|Ch|Fam|WLR|ICR|IRLR|HLR|All ER)\b[^\n;]{0,20}")
_CASE_NAME = re.compile(r"\b([A-Z][A-Za-z'&.\-]+(?:\s[A-Z][A-Za-z'&.\-]+){0,3})\s+v\.?\s+([A-Z][A-Za-z'&.\-]+(?:\s[A-Z][A-Za-z'&.\-]+){0,3})")


def _norm(url: str) -> str:
    p = urlparse(url.strip().rstrip(".,;:"))
    host = (p.netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host + (p.path or "").rstrip("/").lower()


def _official(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def _check_url(url: str, retrieved: List[str]) -> Tuple[str, str]:
    """Returns (verdict, replacement_url). verdict: retrieved | signpost | rerouted | removed."""
    n = _norm(url)
    if any(n == r or r.startswith(n + "/") or n.startswith(r + "/") for r in retrieved if r):
        return "retrieved", url
    host = n.split("/", 1)[0]
    depth = len([s for s in n.split("/")[1:] if s])
    if _official(host):
        return ("signpost", url) if depth <= 1 else ("rerouted", f"https://{'www.' if host.count('.') <= 1 else ''}{host}")
    return "removed", ""


def _refs_supported(sentence: str, src: str) -> Optional[bool]:
    acts = _ACT.findall(sentence)
    secs = _SECTION.findall(sentence)
    if not acts and not secs:
        return None
    for name, year in acts:
        core = re.sub(r"^(the|and|of)\s+", "", name.strip(), flags=re.I).lower()
        if core in src and year in src:
            return True
    for s in secs:
        if re.search(rf"\b(section|s\.?)\s?{re.escape(s.lower())}\b", src):
            return True
    return False


def verify_citations(text: str, citations: List[dict], sources: List[dict]) -> Tuple[str, dict]:
    """Strips citation numbers/URLs that don't match retrieved sources; drops [n] where the source
    doesn't mention the Act/section claimed in that sentence. Returns (text, report)."""
    rep = {"removed_markers": 0, "unsupported_markers": 0, "urls_removed": 0, "urls_rerouted": 0,
           "unverified_case_refs": [], "per_source": {}}
    valid = {int(c["n"]) for c in citations or [] if str(c.get("n", "")).isdigit()}
    src_by_n = {int(s["n"]): ((s.get("title") or "") + " " + (s.get("content") or "")).lower() for s in sources or []}
    retrieved = [_norm(c.get("url") or "") for c in citations or []]
    stash: List[str] = []

    def md(m):
        verdict, new = _check_url(m.group(2), retrieved)
        if verdict == "removed":
            rep["urls_removed"] += 1
            return m.group(1)
        if verdict == "rerouted":
            rep["urls_rerouted"] += 1
        stash.append(f"[{m.group(1)}]({new})")
        return f"\x00{len(stash) - 1}\x00"

    def bare(m):
        verdict, new = _check_url(m.group(0), retrieved)
        if verdict == "removed":
            rep["urls_removed"] += 1
            return "(link removed — not a verified source)"
        if verdict == "rerouted":
            rep["urls_rerouted"] += 1
        return new

    out = _URL.sub(bare, _MD_LINK.sub(md, text or ""))
    out = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], out)

    def fix_sentence(sent: str) -> str:
        def mark(m):
            nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
            keep = []
            for n in nums:
                if n not in valid:
                    rep["removed_markers"] += 1
                    continue
                ok = _refs_supported(sent, src_by_n.get(n, "")) if n in src_by_n else None
                rep["per_source"].setdefault(n, set()).add({True: "supported", False: "not_confirmed", None: "unchecked"}[ok])
                if ok is False:
                    rep["unsupported_markers"] += 1
                    continue
                keep.append(n)
            return (" [" + "][".join(str(n) for n in keep) + "]") if keep else ""
        return _NUM_MARK.sub(mark, sent)

    out = "".join(fix_sentence(p) for p in re.split(r"((?<=[.!?])\s+|\n)", out))
    all_src = " ".join(src_by_n.values())
    for m in list(_NEUTRAL.finditer(out)) + list(_CASE_NAME.finditer(out)):
        ref = m.group(0).strip()
        key = ref.lower()[:40] if m.re is _NEUTRAL else m.group(1).lower().split()[-1]
        if key not in all_src and ref not in rep["unverified_case_refs"]:
            rep["unverified_case_refs"].append(ref)
    for c in citations or []:
        seen = rep["per_source"].get(int(c["n"]), set())
        c["claim_check"] = ("supported" if "supported" in seen else "not_confirmed" if seen == {"not_confirmed"}
                            else "unchecked" if seen else "not_cited")
    rep["per_source"] = {k: sorted(v) for k, v in rep["per_source"].items()}
    return out, rep


_VERIFIED_CLAIM = re.compile(r"\b(I(?:'ve| have)\s+(?:just\s+)?(?:checked|verified|confirmed|looked up)|independently verified|"
                             r"(?:according to|based on) (?:the )?(?:latest|current|live) (?:research|sources|search))", re.I)


def finalize_answer(text: str, *, citations: List[dict], sources: List[dict], research_status: str, risk: str,
                    language: str, legal_question: bool) -> Tuple[str, dict]:
    out, rep = verify_citations(text, citations, sources)
    failed = research_status in RESEARCH_FAILED and legal_question
    notes = []
    if failed and (risk == "high" or _VERIFIED_CLAIM.search(out)):
        notes.append(note("research", language))
        if risk == "high":
            out = re.sub(r"\[CONFIDENCE:\s*HIGH\]", "[CONFIDENCE: MEDIUM]", out)
    if rep["removed_markers"] or rep["unsupported_markers"] or rep["urls_removed"] or rep["urls_rerouted"] or \
            (rep["unverified_case_refs"] and (failed or research_status == "ok")):
        notes.append(note("citations", language))
    if notes:
        out = insert_before_tail(out, "\n\n".join(notes))
    rep.update(research_status=research_status, risk=risk, notes_added=len(notes))
    return out, rep


# ---------------------------------------------------------------- UK nation detection
NATIONS = ("england", "wales", "scotland", "northern_ireland")
LABEL = {"england": "England", "wales": "Wales", "scotland": "Scotland", "northern_ireland": "Northern Ireland"}
_STRONG = {
    "wales": r"wales|cymru|renting homes(?: \(wales\))? act|occupation contract|contract[- ]holders?|section 173|s\.?\s?173 notice|rent smart wales",
    "scotland": r"scotland|scottish|scots law|sheriff court|court of session|private residential tenancy|notice to leave|"
                r"procurator fiscal|simple procedure|housing and property chamber|social security scotland|adult disability payment",
    "northern_ireland": r"northern ireland|n\.\s?ireland|northern irish|labour relations agency|industrial tribunal|nidirect|"
                        r"housing executive|nihe",
    "england": r"england|english law|renters'? rights act|section 21|s\.?\s?21 notice|assured shorthold",
}
_STRONG_RE = {k: re.compile(rf"\b({v})\b", re.I) for k, v in _STRONG.items()}
_PLACES = {
    "wales": "cardiff|swansea|wrexham|aberystwyth|llanelli|merthyr tydfil|bridgend|caerphilly|pontypridd|carmarthen|rhyl|barry",
    "scotland": "edinburgh|glasgow|aberdeen|dundee|inverness|stirling|paisley|falkirk|kilmarnock|livingston|east kilbride|ayr",
    "northern_ireland": "belfast|derry|londonderry|lisburn|newry|armagh|ballymena|coleraine|omagh|enniskillen|craigavon",
    "england": "london|manchester|birmingham|leeds|liverpool|bristol|sheffield|nottingham|leicester|coventry|bradford|brighton|"
               "southampton|portsmouth|plymouth|reading|oxford|cambridge|york|norwich|hull|exeter|derby",
}
_PLACE_RE = {k: re.compile(rf"\b({v})\b", re.I) for k, v in _PLACES.items()}
AMBIGUOUS_PLACES = re.compile(r"\b(bangor|newcastle|newport|perth|richmond)\b", re.I)
_LIVES = re.compile(r"(i live|i'm living|i am living|i'm based|i am based|i'm in|i am in|i moved to|i've moved to|i reside|"
                    r"i'm from|i am from|living in|based in|my home is)\s+(?:in\s+)?(?:\w+\s+){0,2}$", re.I)
_MATTER = re.compile(r"(property|house|flat|home i rent|rental|tenancy|landlord|letting|job|work(?:ed|ing)?|employer|office|"
                     r"factory|shop|store|accident|incident|court|tribunal|arrested|police|council|bought|buying|selling|"
                     r"rent(?:ing)?)\b[^.\n]{0,30}\b(in|at|near)\s+(?:\w+\s+){0,1}$", re.I)
_EXPLICIT = re.compile(r"\b(?:under|apply|using|in)\s+(scots|scottish|welsh|english|northern irish|ni)\s+law\b", re.I)
_EXPLICIT_MAP = {"scots": "scotland", "scottish": "scotland", "welsh": "wales", "english": "england",
                 "northern irish": "northern_ireland", "ni": "northern_ireland"}


def _group(nation: Optional[str], topic: str) -> Optional[str]:
    if not nation:
        return None
    if topic == "immigration":
        return "uk"
    if topic == "employment":
        return "ni" if nation == "northern_ireland" else "gb"
    if topic in ("family", "court", "general", "benefits") and nation in ("england", "wales"):
        return "ew"
    return nation


def _scan(text: str) -> Dict[str, set]:
    found = {"lives": set(), "matter": set(), "mention": set(), "ambiguous": set()}
    t = re.sub(r"\bengland\s*(?:and|&)\s*wales\b", " ", text or "", flags=re.I)
    for nation in NATIONS:
        for m in _STRONG_RE[nation].finditer(t):
            before = t[max(0, m.start() - 60):m.start()]
            word = m.group(0).lower()
            is_place_name = word in ("wales", "cymru", "scotland", "northern ireland", "n. ireland", "england")
            if _LIVES.search(before):
                found["lives"].add(nation)
            elif not is_place_name or _MATTER.search(before):
                found["matter"].add(nation)
            else:
                found["mention"].add(nation)
        for m in _PLACE_RE[nation].finditer(t):
            before = t[max(0, m.start() - 60):m.start()]
            if _LIVES.search(before):
                found["lives"].add(nation)
            elif _MATTER.search(before):
                found["matter"].add(nation)
            else:
                found["mention"].add(nation)
    found["ambiguous"] = {m.group(0) for m in AMBIGUOUS_PLACES.finditer(t)}
    return found


def assess_jurisdiction(message: str, history_text: str, profile: Optional[str], country: Optional[str],
                        category: Optional[str] = None) -> dict:
    """Separates where the customer is from which UK nation's law governs the matter; flags conflicts."""
    res = {"applicable": None, "conflict": False, "reason": "", "block": "", "deadline_jurisdiction": profile or "unknown"}
    if (country or "GB").upper() not in ("GB", "UK"):
        return res
    profile = (profile or "").lower() or None
    topic = next((t for t in topics_of(message + " " + (history_text or "")) if t != "general"), "general")
    explicit = _EXPLICIT.search(message or "")
    if explicit:
        nation = _EXPLICIT_MAP[explicit.group(1).lower()]
        res.update(applicable=nation, deadline_jurisdiction=nation, reason=f"customer explicitly asked about {LABEL[nation]} law")
        res["block"] = (f"\n\nJURISDICTION FOR THIS QUESTION: the customer explicitly asked about {LABEL[nation]} law — apply it "
                        "for this answer and say so. Their saved profile setting is unchanged.")
        return res
    cur, hist = _scan(message), _scan(history_text or "")
    matter = cur["matter"] or hist["matter"]
    lives = cur["lives"] or hist["lives"]
    mention = cur["mention"]
    groups = {_group(n, topic) for n in matter} - {None}
    clue_text = ", ".join(LABEL[n] for n in sorted(matter | lives | mention))
    question = None
    if len(groups) > 1:
        question = f"the details point to more than one UK nation ({clue_text})"
    elif matter:
        nation = sorted(matter)[0]
        if profile and _group(profile, topic) != _group(nation, topic):
            question = (f"the customer's saved setting is {LABEL.get(profile, profile)} but the matter appears to be in "
                        f"{LABEL[nation]}")
        elif not profile and not _STRONG_RE[nation].search(f"{message}\n{history_text or ''}"):
            question = f"the only clue is a place name suggesting {LABEL[nation]}"
        else:
            res.update(applicable=nation, deadline_jurisdiction=nation,
                       reason=f"matter located in {LABEL[nation]}")
    elif lives and profile and any(_group(n, topic) != _group(profile, topic) for n in lives):
        question = (f"the customer says they live in {', '.join(LABEL[n] for n in sorted(lives))} but their saved setting is "
                    f"{LABEL.get(profile, profile)}, and where they live may not be where the matter is governed")
    elif (mention - ({profile} if profile else set())) and profile and \
            any(_group(n, topic) != _group(profile, topic) for n in mention):
        question = f"the message mentions {clue_text} while the saved setting is {LABEL.get(profile, profile)}"
    if cur["ambiguous"] and not question and not matter:
        res["reason"] = f"ambiguous place name(s) ignored: {', '.join(sorted(cur['ambiguous']))}"
    if question and topic != "immigration":
        res.update(conflict=True, reason=question, deadline_jurisdiction="unknown")
        res["block"] = (f"\n\nJURISDICTION CHECK NEEDED: {question}. A place name alone does not decide which law applies "
                        "(e.g. housing law follows where the property is; employment law differs only for Northern Ireland). "
                        "Begin your answer with ONE short, targeted question asking which UK nation the matter is in "
                        "(for example, where the property/workplace/court is). Then give general information that does not "
                        "depend on the answer, clearly caveated, and briefly note where the rules differ between nations. "
                        "Do not give nation-specific deadlines or conclusions until it is confirmed. Do not say you have "
                        "changed their saved location.")
    elif res["applicable"] and res["applicable"] != profile:
        res["block"] = (f"\n\nJURISDICTION FOR THIS MATTER: {res['reason']} — apply {LABEL[res['applicable']]} law where it "
                        "differs, and mention this briefly. The customer's saved setting is unchanged.")
    return res
