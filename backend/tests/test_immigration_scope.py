import immigration_scope as S


def test_applies_uk_immigration_but_not_employment_settlement():
    assert S.applies("My visa expires next month, can I apply for ILR?", "GB")
    assert S.applies("Home Office refused my spouse visa", "ES")
    assert S.applies("anything", "GB", "immigration")
    assert not S.applies("My employer offered a settlement agreement", "GB")
    assert not S.applies("My landlord kept my deposit", "GB")
    assert not S.applies("Do I need a visado for Spain?", "ES")


def test_enforce_removes_individual_determinations_and_keeps_general_rules():
    ans = ("Applicants for ILR usually need 5 years' continuous residence. You would qualify for ILR in March. "
           "I recommend that you appeal the refusal. You should speak to a regulated adviser.\n"
           "- Your best option is to switch to a Skilled Worker visa.\n- The fee is set by the Home Office.")
    out, n = S.enforce(ans)
    assert n == 3
    assert "usually need 5 years" in out and "fee is set" in out and "speak to a regulated adviser" in out
    assert "You would qualify" not in out and "I recommend that you appeal" not in out and "best option" not in out
    assert "general information only" in out and "gov.uk/find-an-immigration-adviser" in out


def test_enforce_catches_eligibility_and_prospects_phrasing():
    for s in ("You are eligible for settled status.", "You don't qualify for a partner visa.",
              "Your appeal is likely to succeed.", "You have a strong case for a fresh claim.",
              "You should request an administrative review."):
        out, n = S.enforce(s)
        assert n == 1, s


def test_blocked_templates_and_practice_role():
    assert {"immigration_letter", "asylum_statement"} <= S.BLOCKED_TEMPLATES
    assert "immigration" in S.BLOCKED_PRACTICE
