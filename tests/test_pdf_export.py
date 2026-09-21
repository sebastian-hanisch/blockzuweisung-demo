"""Tests des PDF-Exports: Sonderzeichen mit den GENAUEN Zeichen (fpdf2 stürzt bei "–", "€", "σ", "λ" ab), Inhalt der Abschnitte, optionale Teile, alle Zustände der Meldung."""

import re

import pytest

import blz_constants as C
import blz_evaluation as E
from blz_pdf_export import generate_blz_pdf, pdf_text

P = E.Params(6, 8, 40, 90, 70, 3, 10)


def texts(data):
    """Alle Textstücke des (unkomprimierten) PDFs als Liste, Latin-1 gelesen, PDF-Escapes aufgelöst."""
    raw = re.findall(rb"\((.*?)\)\s*Tj", data)
    return [t.decode("latin-1").replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\") for t in raw]


@pytest.fixture(scope="module")
def parts():
    res = E.run_week(P, 2017)
    return res, E.diagnose(res), E.price_curve(P, 2017, res), E.sample(P, 3, 3000)


def make(parts, curve=True, sample=True, compress=False, p=P):
    res, diag, cv, sm = parts
    return generate_blz_pdf(p, 2017, res, diag, curve=cv if curve else None, sample=sm if sample else None, compress=compress)


EXPECTED = {"–": "-", "—": "-", "−": "-", "€": "EUR", "Σ": "Summe", "δ": "Delta", "σ": "sigma", "λ": "lambda", "μ": "mu", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "„": '"', "“": '"', "’": "'",
            "·": "*", "±": "+-", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": "", "**": ""}


@pytest.mark.parametrize("char,replacement", list(EXPECTED.items()))
def test_pdf_text_replaces_every_known_troublemaker_with_a_readable_equivalent(char, replacement):
    out = pdf_text(f"a{char}b")
    out.encode("latin-1")
    assert out == f"a{replacement}b"


def test_pdf_text_keeps_umlauts_and_times_sign_and_replaces_unknown():
    assert pdf_text("Füllgrad äöüß ÄÖÜ × 3") == "Füllgrad äöüß ÄÖÜ × 3" and pdf_text("日本語").encode("latin-1") == b"???" and "?" in pdf_text("🏗️ Block")


def test_a_full_pdf_is_valid_and_has_all_sections(parts):
    data = make(parts)
    assert data.startswith(b"%PDF") and data.rstrip().endswith(b"%%EOF")
    t = texts(data)
    joined = "\n".join(t)
    for needle in ("Blockzuweisung: In welchen Block kommen die Exportcontainer?", "Szenario", "Zusammenfassung", "Verfahrensvergleich (diese Woche)", "Preis der Absicherung", "Stichprobe und Urteil",
                   "Hinweise zum Modell", "6 Schiffe, 8 Blöcke im Abstand 100 m, 6275 Exportcontainer", "40 Moves je Stunde und Block; Schiffe rufen bis 90 Moves je Stunde ab",
                   "Spitzenfüllung 70 %, Grenze 864 Container je Block", "sigma 3 h; Preis der Wartezeit lambda = 10 m je min"):
        assert needle in joined, needle
    assert "2017" in t


def test_the_comparison_table_has_a_row_per_method_with_the_numbers(parts):
    res = parts[0]
    t = texts(make(parts, curve=False, sample=False))
    for o in res.outcomes:
        assert C.METHOD_SHORT[o.key] in t
    assert f"{res['gerechnet'].m.distance:.0f}" in t and f"{res['buendeln'].m.stock_over:.0f}" in t and f"{res['abgesichert'].robust.wait:.1f}" in t
    assert "Wartezeit pünktlich (min)" in t and "bei Verspätung (min)" in t


def test_optional_sections_are_left_out_when_not_given(parts):
    joined = "\n".join(texts(make(parts, curve=False, sample=False)))
    assert "Preis der Absicherung" not in joined and "Stichprobe und Urteil" not in joined and "Hinweise zum Modell" in joined
    only_curve = "\n".join(texts(make(parts, curve=True, sample=False)))
    assert "Preis der Absicherung" in only_curve and "Stichprobe und Urteil" not in only_curve
    only_sample = "\n".join(texts(make(parts, curve=False, sample=True)))
    assert "Stichprobe und Urteil" in only_sample and "Preis der Absicherung" not in only_sample


def test_curve_and_edge_tables_list_every_price_and_every_allowed_wait(parts):
    t = texts(make(parts, sample=False))
    for lam in ("1", "2", "5", "10", "20", "50", "100"):
        assert lam in t
    for eps in ("400", "200", "100", "50", "20", "10", "5", "2"):
        assert eps in t
    joined = "\n".join(t)
    assert "kleinstmögliche Wartezeit" in joined and "Bündeln" in joined and "Verteilen" in joined


def test_the_sample_section_has_median_and_percentiles_and_three_verdict_sentences(parts):
    res, diag, cv, sm = parts
    t = texts(make(parts, curve=False))
    joined = "\n".join(t)
    med, lo, hi = E.spread_of(sm, "kranrate", "wait")
    assert f"{med:.1f} [{lo:.1f}; {hi:.1f}]" in t
    med, lo, hi = E.spread_of(sm, "kranrate", "wait_shift")
    assert f"{med:.1f} [{lo:.1f}; {hi:.1f}]" in t and f"{E.spread_of(sm, 'abgesichert', 'wait_shift')[0]:.1f} [" in joined
    assert "Abgesichert gegen Gerechnet, Wartezeit bei Verspätung" in joined and "Gerechnet gegen Kranrate passend, Wartezeit pünktlich" in joined and "Abgesichert gegen Gierig, Zielwert Weg + 10 * Wartezeit" in joined
    assert "Basis: 3 Wochen (Seeds 3000-3002, nicht der eingestellte Seed)" in joined and "**" not in joined


def test_the_summary_carries_the_diagnosis_and_the_storage_warning(parts):
    res, diag, _, _ = parts
    joined = "\n".join(texts(make(parts, curve=False, sample=False)))
    assert "Der wartefreie Plan zerbricht" in joined and "lambda = 10 m je min" in joined
    full = E.run_week(P._replace(fill=90), 2017)
    d = E.diagnose(full)
    data = generate_blz_pdf(P._replace(fill=90), 2017, full, d, compress=False)
    assert "Lagergrenze verletzt: Bündeln um 177 Container" in "\n".join(texts(data))


def test_all_states_of_the_message_render_without_errors():
    for pr in (E.Params(4, 8, 60, 60, 60, 1, 10), E.Params(6, 8, 40, 90, 70, 0, 10), E.Params(8, 6, 30, 120, 90, 6, 50), E.Params(5, 8, 40, 120, 70, 3, 2)):
        res = E.run_week(pr, 2017)
        data = generate_blz_pdf(pr, 2017, res, E.diagnose(res), compress=True)
        assert data.startswith(b"%PDF") and len(data) > 2000


def test_a_week_without_a_storage_limit_says_unlimited():
    from blz_scenario import make_week
    res = E.run_week(P, 2017)
    import dataclasses
    week = make_week(2017, 6, 8, 40.0, 90, None)
    res2 = E.WeekResult(P, 2017, week, res.outcomes)
    joined = "\n".join(texts(generate_blz_pdf(P, 2017, res2, E.diagnose(res2), compress=False)))
    assert "unbegrenzt" in joined and dataclasses.is_dataclass(week)


def test_compression_makes_the_file_smaller_and_still_valid(parts):
    plain, packed = make(parts, compress=False), make(parts, compress=True)
    assert len(packed) < len(plain) and packed.startswith(b"%PDF")


def test_every_text_survives_latin_1(parts):
    for t in texts(make(parts)):
        t.encode("latin-1")
