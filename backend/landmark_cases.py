"""Sourced list of well-known UK court decisions (Lex 2.0 Phase 2E corrections, checked 18 Nov 2026).
Each entry's BAILII URL was fetched and its title matched (for Bolam and Western Excavating, which BAILII does not host,
the URL is a later judgment quoting the case and citation). This list confirms only that the
decision exists under that name and citation. It has NOT been reviewed by a qualified lawyer and does not confirm how
Lex applies any case. Fields: (claimant/first-party words, respondent/second-party words, display name, citations, url, area)."""
import re
from typing import List, Optional

REVIEW_STATUS = "sourced (existence and citation checked) — not reviewed by a qualified lawyer"
CHECKED = "2026-11-18"
B = "https://www.bailii.org"

CASES = [
    ("parkingeye", "beavis", "ParkingEye Ltd v Beavis", ["[2015] UKSC 67"], f"{B}/uk/cases/UKSC/2015/67.html", "parking / penalties"),
    ("cavendish", "makdessi", "Cavendish Square Holding BV v Makdessi", ["[2015] UKSC 67"], f"{B}/uk/cases/UKSC/2015/67.html", "contract / penalties"),
    ("bolam", "friern", "Bolam v Friern Hospital Management Committee", ["[1957] 1 WLR 582"], f"{B}/uk/cases/UKSC/2015/11.html", "clinical negligence (cited and discussed in Montgomery [2015] UKSC 11)"),
    ("bolitho", "hackney", "Bolitho v City and Hackney Health Authority", ["[1997] UKHL 46", "[1998] AC 232"], f"{B}/uk/cases/UKHL/1997/46.html", "clinical negligence"),
    ("montgomery", "lanarkshire", "Montgomery v Lanarkshire Health Board", ["[2015] UKSC 11"], f"{B}/uk/cases/UKSC/2015/11.html", "clinical negligence / consent"),
    ("chester", "afshar", "Chester v Afshar", ["[2004] UKHL 41"], f"{B}/uk/cases/UKHL/2004/41.html", "clinical negligence / causation"),
    ("donoghue", "stevenson", "Donoghue v Stevenson", ["[1932] UKHL 100", "[1932] AC 562"], f"{B}/uk/cases/UKHL/1932/100.html", "negligence"),
    ("caparo", "dickman", "Caparo Industries plc v Dickman", ["[1990] UKHL 2", "[1990] 2 AC 605"], f"{B}/uk/cases/UKHL/1990/2.html", "negligence"),
    ("robinson", "yorkshire", "Robinson v Chief Constable of West Yorkshire Police", ["[2018] UKSC 4"], f"{B}/uk/cases/UKSC/2018/4.html", "negligence"),
    ("polkey", "dayton", "Polkey v A E Dayton Services Ltd", ["[1987] UKHL 8", "[1988] AC 344"], f"{B}/uk/cases/UKHL/1987/8.html", "employment / unfair dismissal"),
    ("western excavating", "sharp", "Western Excavating (ECC) Ltd v Sharp", ["[1978] QB 761", "[1978] 1 QB 761"], f"{B}/ew/cases/EWCA/Civ/2018/978.html", "employment / constructive dismissal (cited in Kaur v Leeds Teaching Hospitals [2018] EWCA Civ 978)"),
    ("malik", "bank of credit", "Malik v Bank of Credit and Commerce International SA", ["[1997] UKHL 23"], f"{B}/uk/cases/UKHL/1997/23.html", "employment / trust and confidence"),
    ("uber", "aslam", "Uber BV v Aslam", ["[2021] UKSC 5"], f"{B}/uk/cases/UKSC/2021/5.html", "employment / worker status"),
    ("autoclenz", "belcher", "Autoclenz Ltd v Belcher", ["[2011] UKSC 41"], f"{B}/uk/cases/UKSC/2011/41.html", "employment / worker status"),
    ("pimlico", "smith", "Pimlico Plumbers Ltd v Smith", ["[2018] UKSC 29"], f"{B}/uk/cases/UKSC/2018/29.html", "employment / worker status"),
    ("hendricks", "metropolis", "Hendricks v Commissioner of Police of the Metropolis", ["[2002] EWCA Civ 1686"], f"{B}/ew/cases/EWCA/Civ/2002/1686.html", "discrimination / continuing acts"),
    ("northern ireland", "agnew", "Chief Constable of the Police Service of Northern Ireland v Agnew", ["[2023] UKSC 33"], f"{B}/uk/cases/UKSC/2023/33.html", "holiday pay / series of deductions"),
    ("royal mail", "efobi", "Royal Mail Group Ltd v Efobi", ["[2021] UKSC 33"], f"{B}/uk/cases/UKSC/2021/33.html", "discrimination / burden of proof"),
    ("essop", "home office", "Essop v Home Office", ["[2017] UKSC 27"], f"{B}/uk/cases/UKSC/2017/27.html", "indirect discrimination"),
    ("harpur", "brazel", "Harpur Trust v Brazel", ["[2022] UKSC 21"], f"{B}/uk/cases/UKSC/2022/21.html", "holiday pay"),
    ("stack", "dowden", "Stack v Dowden", ["[2007] UKHL 17"], f"{B}/uk/cases/UKHL/2007/17.html", "cohabitants / property"),
    ("jones", "kernott", "Jones v Kernott", ["[2011] UKSC 53"], f"{B}/uk/cases/UKSC/2011/53.html", "cohabitants / property"),
    ("white", "white", "White v White", ["[2000] UKHL 54"], f"{B}/uk/cases/UKHL/2000/54.html", "divorce / finances"),
    ("radmacher", "granatino", "Radmacher v Granatino", ["[2010] UKSC 42"], f"{B}/uk/cases/UKSC/2010/42.html", "nuptial agreements"),
    ("owens", "owens", "Owens v Owens", ["[2018] UKSC 41"], f"{B}/uk/cases/UKSC/2018/41.html", "divorce (pre-2022 law)"),
    ("street", "mountford", "Street v Mountford", ["[1985] UKHL 4", "[1985] AC 809"], f"{B}/uk/cases/UKHL/1985/4.html", "lease or licence"),
    ("manchester city council", "pinnock", "Manchester City Council v Pinnock", ["[2010] UKSC 45"], f"{B}/uk/cases/UKSC/2010/45.html", "possession / proportionality"),
    ("hotak", "southwark", "Hotak v London Borough of Southwark", ["[2015] UKSC 30"], f"{B}/uk/cases/UKSC/2015/30.html", "homelessness"),
    ("superstrike", "rodrigues", "Superstrike Ltd v Rodrigues", ["[2013] EWCA Civ 669"], f"{B}/ew/cases/EWCA/Civ/2013/669.html", "tenancy deposits"),
    ("hadley", "baxendale", "Hadley v Baxendale", ["[1854] EWHC J70"], f"{B}/ew/cases/EWHC/Exch/1854/J70.html", "contract / damages"),
    ("carlill", "carbolic", "Carlill v Carbolic Smoke Ball Co", ["[1892] EWCA Civ 1"], f"{B}/ew/cases/EWCA/Civ/1892/1.html", "contract formation"),
    ("photo production", "securicor", "Photo Production Ltd v Securicor Transport Ltd", ["[1980] UKHL 2"], f"{B}/uk/cases/UKHL/1980/2.html", "contract / exclusion clauses"),
    ("arnold", "britton", "Arnold v Britton", ["[2015] UKSC 36"], f"{B}/uk/cases/UKSC/2015/36.html", "contract interpretation"),
    ("cart", "upper tribunal", "R (Cart) v Upper Tribunal", ["[2011] UKSC 28"], f"{B}/uk/cases/UKSC/2011/28.html", "judicial review of tribunals"),
    ("zh", "home department", "ZH (Tanzania) v Secretary of State for the Home Department", ["[2011] UKSC 4"], f"{B}/uk/cases/UKSC/2011/4.html", "immigration / children's best interests"),
    ("hj", "home department", "HJ (Iran) v Secretary of State for the Home Department", ["[2010] UKSC 31"], f"{B}/uk/cases/UKSC/2010/31.html", "asylum"),
    ("agyarko", "home department", "R (Agyarko) v Secretary of State for the Home Department", ["[2017] UKSC 11"], f"{B}/uk/cases/UKSC/2017/11.html", "immigration / Article 8"),
    ("unison", "lord chancellor", "R (UNISON) v Lord Chancellor", ["[2017] UKSC 51"], f"{B}/uk/cases/UKSC/2017/51.html", "access to tribunals"),
    ("denton", "white", "Denton v TH White Ltd", ["[2014] EWCA Civ 906"], f"{B}/ew/cases/EWCA/Civ/2014/906.html", "civil procedure / relief from sanctions"),
    ("mitchell", "news group", "Mitchell v News Group Newspapers Ltd", ["[2013] EWCA Civ 1537"], f"{B}/ew/cases/EWCA/Civ/2013/1537.html", "civil procedure / relief from sanctions"),
    ("barton", "wright hassall", "Barton v Wright Hassall LLP", ["[2018] UKSC 12"], f"{B}/uk/cases/UKSC/2018/12.html", "civil procedure / service"),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\[\] ]", " ", (s or "").lower())).strip()


def find(left: str, right: str) -> Optional[tuple]:
    """Entry whose party words appear in the two sides of a 'X v Y' reference (either order)."""
    a, b = f" {_norm(left)} ", f" {_norm(right)} "
    for e in CASES:
        p, q = f" {e[0]} ", f" {e[1]} "
        if (p in a and q in b) or (p in b and q in a):
            return e
    return None


def cite_matches(entry: tuple, cite: str) -> bool:
    c = _norm(cite)
    return not c or any(_norm(x) in c or c in _norm(x) for x in entry[3])


def citation(entry: tuple) -> dict:
    return {"title": f"{entry[2]} {'; '.join(entry[3])} — app's sourced case list ({REVIEW_STATUS}; does not confirm "
                     "how this answer applies it)", "url": entry[4], "source": "landmark_case", "claim_check": "status_checked"}


def names() -> List[str]:
    return [e[2] for e in CASES]
