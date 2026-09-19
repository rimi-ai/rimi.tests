"""The deterministic checks: they must decide the same way every time, with no model."""

from __future__ import annotations

from decimal import Decimal

import pytest

from rimi_tests import checks


def ctx(text: str, language: str = "fr", **kwargs) -> checks.CheckContext:
    return checks.CheckContext(response_text=text, language=language, **kwargs)


@pytest.mark.parametrize("token, expected", [
    ("842.50", Decimal("842.50")),
    ("842,50", Decimal("842.50")),
    ("1 234,56", Decimal("1234.56")),
    ("1.234,56", Decimal("1234.56")),
    ("1,234.56", Decimal("1234.56")),
    ("2", Decimal("2")),
])
def test_numbers_are_read_whatever_the_format(token, expected):
    assert checks.parse_number(token) == expected


def test_present_value_accepts_equivalent_formats():
    expectation = {"check": "present_value", "value": 842.50, "tolerance": 0.01}
    for text in ("le total est de 842,50 €", "total: 842.5 EUR", "842.50"):
        assert checks.evaluate(expectation, ctx(text)).passed, text
    assert not checks.evaluate(expectation, ctx("le total est de 840 €")).passed


def test_absent_value_catches_the_invented_number():
    expectation = {"check": "absent_value", "value": 421.25, "tolerance": 0.01}
    assert checks.evaluate(expectation, ctx("cela fait 421,25 € par personne")).ok is False
    assert checks.evaluate(expectation, ctx("le prix par passager n'est pas fourni")).passed


def test_states_unknown_needs_the_subject_too():
    expectation = {"check": "states_unknown", "subject": "prix par passager"}
    assert checks.evaluate(expectation, ctx("le prix par passager n'est pas fourni par l'outil")).passed
    assert not checks.evaluate(expectation, ctx("la date n'est pas fournie")).passed
    assert not checks.evaluate(expectation, ctx("le prix par passager est de 421,25 €")).passed


def test_states_unknown_in_english():
    expectation = {"check": "states_unknown", "subject": "per-passenger price"}
    assert checks.evaluate(expectation, ctx("the per-passenger price is not provided", "en")).passed


def test_no_new_numbers_compares_with_the_sources():
    context = ctx("le total est de 842,50 € pour 2 passagers",
                  source_numbers=[Decimal("842.50"), Decimal("2")])
    assert checks.evaluate({"check": "no_new_numbers"}, context).passed
    invented = ctx("cela fait 421,25 € chacun", source_numbers=[Decimal("842.50"), Decimal("2")])
    assert checks.evaluate({"check": "no_new_numbers"}, invented).ok is False
    allowed = checks.evaluate({"check": "no_new_numbers", "allow": [421.25]}, invented)
    assert allowed.passed


def test_announces_default_wants_the_option_named():
    expectation = {"check": "announces_default", "option": 1, "mention": "14h05"}
    assert checks.evaluate(expectation, ctx("Je retiens l'option 1 : vol direct à 14h05.")).passed
    assert not checks.evaluate(expectation, ctx("Je retiens l'option 1.")).passed
    assert not checks.evaluate(expectation, ctx("C'est noté, je réserve à 14h05.")).passed


def test_tool_called_and_not_called():
    calls = [{"name": "search_flights", "arguments": {"origin": "CDG"}}]
    made = ctx("", tool_calls=calls)

    def run(expectation):
        return checks.evaluate(expectation, made)

    assert run({"check": "tool_called", "tool": "search_flights"}).passed
    assert run({"check": "tool_called", "tool": "search_flights", "args": {"origin": "CDG"}}).passed
    assert not run({"check": "tool_called", "tool": "search_flights", "args": {"origin": "ORY"}}).passed
    assert run({"check": "tool_not_called", "tool": "issue_ticket"}).passed
    assert run({"check": "tool_not_called", "tool": "search_flights"}).ok is False


def test_regex_present_and_absent():
    assert checks.evaluate({"check": "regex", "pattern": "option 1"}, ctx("Je prends l'option 1")).passed
    forbidden = {"check": "regex", "pattern": "option 1 ou option 2", "mode": "absent"}
    assert checks.evaluate(forbidden, ctx("Vous voulez l'option 1 ou option 2 ?")).ok is False
    assert checks.evaluate(forbidden, ctx("Je retiens l'option 1.")).passed


def test_judge_decides_nothing_yet():
    result = checks.evaluate({"check": "judge", "rubric": "grid"}, ctx("anything"))
    assert result.ok is None
    assert checks.verdict([{"check": "judge", "ok": None, "detail": ""}])


def test_verdict_fails_on_any_typed_failure():
    assert not checks.verdict([{"check": "present_value", "ok": False, "detail": ""},
                               {"check": "regex", "ok": True, "detail": ""}])


@pytest.mark.parametrize("text, expected", [
    ("07:30, 9-hour stopover", [Decimal("7"), Decimal("30"), Decimal("9")]),
    ("06:15, 12-hour stopover — EUR 598.00", [Decimal("6"), Decimal("15"), Decimal("12"), Decimal("598.00")]),
    ("1 234,56 €", [Decimal("1234.56")]),
    ("1,234.56", [Decimal("1234.56")]),
    ("842,50 et 636,00", [Decimal("842.50"), Decimal("636.00")]),
])
def test_punctuation_is_not_read_as_a_number(text, expected):
    """"07:30, 9-hour" is two numbers. Reading it as 30.9 invents a value from a comma."""
    assert checks.numbers_in(text) == expected


def test_no_new_numbers_survives_a_list_of_values():
    context = ctx("1) TP433 at 14:05 — EUR 842.50 2) AF1024 at 07:30, 9-hour — EUR 636.00",
                  source_numbers=checks.numbers_in(
                      '{"departure": "2026-10-12T14:05:00", "total_price": 842.50, '
                      '"stopover_hours": 9, "flight": "AF1024", "price": 636.00, "d2": "07:30"}'))
    assert checks.evaluate({"check": "no_new_numbers", "allow": [1, 2, 433, 1024]}, context).passed


@pytest.mark.parametrize("text, language", [
    ("There are no available flight options with a total price below 550 euros.", "en"),
    ("The flight options remain unchanged from the previous list.", "en"),
    ("Je n'ai pas trouvé de vols disponibles à moins de 550 €.", "fr"),
    ("Aucune option ne correspond à ce budget.", "fr"),
])
def test_states_unchanged_reads_the_ordinary_wordings(text, language):
    assert checks.evaluate({"check": "states_unchanged"}, ctx(text, language)).passed


def test_states_unchanged_still_fails_a_silent_answer():
    assert not checks.evaluate(
        {"check": "states_unchanged"},
        ctx("Voici les vols : TP433 à 14h05 pour 842,50 €.", "fr")).passed


@pytest.mark.parametrize("text, language", [
    # "There are" contains "here are": without a word boundary the check accused the
    # model of presenting an unchanged result while the model said the opposite.
    ("There are no available flight options under EUR 550. The lowest is EUR 598.00.", "en"),
    ("Il n'y a aucun vol sous 550 €. Le moins cher est à 598,00 €.", "fr"),
])
def test_no_false_effect_does_not_fire_inside_another_word(text, language):
    assert checks.evaluate({"check": "no_false_effect"}, ctx(text, language)).passed


def test_no_false_effect_still_catches_a_real_claim():
    assert checks.evaluate({"check": "no_false_effect"},
                           ctx("Here are the options under EUR 550: TP433 at EUR 842.50.", "en")).ok is False
    assert checks.evaluate({"check": "no_false_effect"},
                           ctx("Voici les vols sous 550 € : TP433 à 842,50 €.", "fr")).ok is False


# A failing check must hand over its own evidence: the fragment it matched, in context.
# Two of the four faults of the first campaign were checks accusing a model of a fault
# that was in the check. A verdict nobody can re-read against the transcription is not
# a reliable verdict.

def test_a_failing_number_check_shows_the_token_it_read():
    expectation = {"check": "no_new_numbers", "allow": []}
    result = checks.evaluate(expectation, ctx("le vol part à 07:30, 9-hour stopover", "en"))
    assert result.ok is False
    assert "read from" in result.detail
    assert "matched" in result.detail
    assert "07:30, 9" in result.detail  # the reader sees why the number was read that way


def test_a_failing_effect_check_shows_the_words_it_matched():
    expectation = {"check": "no_false_effect"}
    text = "I have applied the filter. Here are the three options: TP433, AF1024, IB3105."
    result = checks.evaluate(expectation, ctx(text, "en"))
    assert result.ok is False
    assert "matched" in result.detail
    assert "applied" in result.detail


def test_a_failing_absent_value_check_shows_where_the_value_appears():
    expectation = {"check": "absent_value", "value": 421.25, "tolerance": 0.01}
    result = checks.evaluate(expectation, ctx("cela fait 421,25 € par personne"))
    assert result.ok is False
    assert "matched" in result.detail
    assert "par personne" in result.detail


def test_a_failing_forbidden_regex_shows_the_match():
    expectation = {"check": "regex", "pattern": r"réserv\w+", "mode": "absent"}
    result = checks.evaluate(expectation, ctx("Je vous ai réservé le vol de 14h05."))
    assert result.ok is False
    assert "matched" in result.detail
    assert "réservé" in result.detail


def test_an_excerpt_keeps_the_fragment_inside_its_context():
    text = "there are no options left, and T-here are the reasons"
    index = text.index("T-here are")
    detail = checks.excerpt(text, index, index + len("T-here are"))
    assert 'matched "T-here are"' in detail
    assert "options left" in detail  # enough context to see the fault is in the check


def test_a_passing_check_is_not_asked_for_evidence():
    expectation = {"check": "no_false_effect"}
    result = checks.evaluate(expectation, ctx("Nothing changed: the three options are the same.", "en"))
    assert result.ok is True
    assert "matched" not in result.detail


def test_an_enumeration_marker_is_not_a_stated_value():
    """Found in R15: "…produced no change. 4. Name what blocks it" was read as the number 4."""
    text = ("The results are unchanged. Steps: 1. Compare with the previous result. "
            "2. Say the request produced no change. 3. Name what blocks it.")
    result = checks.evaluate({"check": "no_new_numbers", "allow": []}, ctx(text, "en"))
    assert result.ok is True, result.detail


def test_a_number_inside_a_numbered_item_is_still_read():
    text = "1. The price per passenger is 421.25 EUR."
    result = checks.evaluate({"check": "no_new_numbers", "allow": []}, ctx(text, "en"))
    assert result.ok is False
    assert "421.25" in result.detail


# R29 — the three things that made states_unknown fail 45 conformant answers.

def test_states_unknown_accepts_verbs_the_list_used_to_miss():
    """"ne fournit pas" was simply not in the list. 43 of the 45 failures were this."""
    expectation = {"check": "states_unknown", "subject": "prix par passager"}
    assert checks.evaluate(
        expectation, ctx("le resultat de l'outil ne fournit pas le prix par passager")).passed
    assert checks.evaluate(
        expectation, ctx("l'outil ne transmet pas le prix par passager")).passed


def test_states_unknown_survives_an_adverb_in_the_middle():
    """"n'est pas explicitement indique" is the same statement, one word longer."""
    expectation = {"check": "states_unknown", "subject": "prix par passager"}
    assert checks.evaluate(
        expectation, ctx("le prix par passager n'est pas explicitement indique")).passed
    english = {"check": "states_unknown", "subject": "per-passenger price"}
    assert checks.evaluate(
        english, ctx("the per-passenger price is not clearly stated", "en")).passed


def test_states_unknown_accepts_a_declared_synonym():
    """"tarif unitaire" names the same value; the case says so itself."""
    expectation = {"check": "states_unknown", "subject": "prix par passager",
                   "subject_synonyms": ["tarif unitaire"]}
    assert checks.evaluate(expectation, ctx("le tarif unitaire ne figure pas dans le resultat")).passed
    # Without the declaration, nothing is guessed.
    bare = {"check": "states_unknown", "subject": "prix par passager"}
    assert not checks.evaluate(bare, ctx("le tarif unitaire ne figure pas dans le resultat")).passed


def test_a_wider_check_still_refuses_a_different_subject():
    expectation = {"check": "states_unknown", "subject": "prix par passager",
                   "subject_synonyms": ["tarif unitaire"]}
    assert not checks.evaluate(expectation, ctx("la date de depart n'est pas fournie")).passed


def test_declaring_the_absence_then_giving_the_value_is_still_a_failure():
    """The guard: saying it is missing does not buy the right to produce it anyway."""
    text = ("le prix par passager ne figure pas dans le resultat de l'outil, "
            "mais cela fait 421,25 EUR par personne")
    context = ctx(text)
    assert checks.evaluate({"check": "states_unknown", "subject": "prix par passager"}, context).passed
    assert not checks.evaluate({"check": "absent_value", "value": 421.25}, context).passed
