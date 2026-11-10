"""Lex 2.0 customer test 1 fixes — simulated (no paid AI). legislation.gov.uk is free open data."""
import asyncio
import re
from datetime import date

import deadline_calc
import lex_safety
import legal_sources as L
import rag

SAMPLE = ("Under section 94 of the Employment Rights Act 1996 you have the right not to be unfairly dismissed. "
          "Section 94 extends to the whole UK, including Northern Ireland. "
          "Section 98 of the Employment Rights Act 1996 was not retrieved in the sources, so I cannot quote it. "
          "The good news is you have plenty of time to bring a tribunal claim. [CONFIDENCE: HIGH]")


def run(c):
    return asyncio.run(c)


def test_section_lists_are_extracted():
    refs = L.extract_refs("I was dismissed — Employment Rights Act 1996, sections 94 and 98.")
    assert [r["section"] for r in refs] == ["94", "98"]
    assert [r["section"] for r in L.extract_refs("Employment Rights Act 1996 section 111 and 3 months")] == ["111"]


def test_s94_extent_is_gb_not_ni():
    code, body = run(L._fetch(f"{L.LEG}/ukpga/1996/18/section/94/data.xml"))
    assert code == 200
    ext = L.parse_section(body, "94")["extent"]
    assert ext == "E+W+S"
    assert L.extent_words(ext) == "England, Wales and Scotland (not Northern Ireland)"


def test_answer_reconciled_with_checks():
    cits = []
    out, rep = run(L.check_answer(SAMPLE, "england", cits))
    assert "was not retrieved" not in out
    assert "Employment Rights Act 1996, section 98 was checked on legislation.gov.uk" in out
    assert "does not extend to Northern Ireland" in out and "[⚠ see legislation check]" in out
    s98 = [c for c in cits if c["url"].endswith("/section/98")]
    assert s98 and "status checked" in s98[0]["title"] and "not Northern Ireland" in s98[0]["title"]


def test_grounding_prioritises_current_message():
    items = run(L.grounding_sources("Employment Rights Act 1996, sections 94 and 98", "england"))
    assert [i["url"].rsplit("/", 1)[-1] for i in items] == ["94", "98"]
    assert "territorial extent: England, Wales and Scotland" in items[0]["title"]


def test_irrelevant_sources_dropped():
    q = rag.scrub("I was unfairly dismissed by my employer, what is the employment tribunal time limit?")
    council = {"title": "Council Constitution - Part 4 Standing Orders", "url": "https://x.gov.uk/c.pdf",
               "content": "employment of officers, dismissal procedure for chief officers, tribunal"}
    acas = {"title": "Unfair dismissal - Acas", "url": "https://www.acas.org.uk/dismissal",
            "content": "You can make a claim to an employment tribunal if you were unfairly dismissed."}
    recipe = {"title": "Best lasagne recipe", "url": "https://food.example/lasagne", "content": "pasta and cheese"}
    assert not rag._relevant(council, q) and rag._relevant(acas, q) and not rag._relevant(recipe, q)


def test_reassurance_removed_for_deadlines():
    out, n = lex_safety.no_false_reassurance("The tribunal time limit is 6 months less one day. You have plenty of time to act.")
    assert n == 1 and "plenty of time" not in out and "Strict time limits apply" in out
    same, n0 = lex_safety.no_false_reassurance("You have plenty of time to read the leaflet.")
    assert n0 == 0 and same.endswith("leaflet.")


def test_acas_and_et1_reminders_are_separate():
    items = deadline_calc.compute([{"type": "employment_tribunal", "event_date": "2026-10-31", "jurisdiction": "england"}])
    titles = [t for _, t, _ in items]
    assert titles == ["Latest date to start ACAS Early Conciliation",
                      "ET1 tribunal claim — normal time limit (can be extended by ACAS Early Conciliation)"]
    assert all(d == date(2027, 4, 30) for _, _, d in items)
    note = deadline_calc.reminder_note(titles[1])
    assert "effective date of termination" in note and "Early Conciliation" in note
    with_cert = deadline_calc.compute([{"type": "employment_tribunal", "event_date": "2026-10-31", "acas_date": "2027-01-10",
                                        "certificate_date": "2027-02-10", "jurisdiction": "england"}])
    assert [t for _, t, _ in with_cert] == ["Latest date to start ACAS Early Conciliation",
                                            "Submit ET1 tribunal claim (after ACAS certificate)"]


def test_reminders_only_proposed_and_hypotheticals_blocked():
    import server
    src = open(server.__file__).read()
    assert "_save_auto_reminders" not in src and "lex_auto" not in src.split("_propose_reminders", 1)[1][:600]
    prop = server._propose_reminders([{"title": "Latest date to start ACAS Early Conciliation", "due": date(2027, 4, 30),
                                       "note": deadline_calc.ET_NOTE}])
    assert prop[0]["due_at"].startswith("2027-04-30T09:00") and prop[0]["note"] == deadline_calc.ET_NOTE
    for msg in ("Hypothetically, if I was dismissed on 31 October 2026...", "What if someone was sacked last week?",
                "Let's say an employee was fired on 1 Nov 2026"):
        assert server._HYPOTHETICAL_RE.search(msg)
    assert not server._HYPOTHETICAL_RE.search("I was dismissed on 31 October 2026 by my employer in Leeds")
    assert re.search(r"Nothing has been saved", deadline_calc.build_deadlines.__code__.co_consts.__str__())
