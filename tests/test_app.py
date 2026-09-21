"""AppTest: Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, Kennzahlen im 2 x 2-Raster, die bedingte Meldung in allen Zuständen, Knopf-Pfade (Kurve und Kante, Stichprobe mit
Urteil), Verfahrensvergleich, PDF, Texte. Zahlen der Rechenverfahren nur mit Abstand (die Aufteilung des LP kann zwischen Löserversionen abweichen); die der Regeln exakt."""

import pathlib
import re

import pytest
from streamlit.proto.Metric_pb2 import Metric as MetricProto
from streamlit.testing.v1 import AppTest

import blz_constants as C
import blz_evaluation as E
import blz_lp as L
from blz_presets import SETTING_SPECS

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
FOOTER = ("Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
          "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
          "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)")


@pytest.fixture(autouse=True)
def clean_cache():
    """st.cache_data ist prozessweit: Tests, die Funktionen ersetzen, dürfen keine zwischengespeicherten Ergebnisse anderer Tests sehen."""
    import streamlit as st
    st.cache_data.clear()
    yield


def fresh(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def set_and_run(at, **values):
    for key, value in values.items():
        widget = at.number_input(key=key) if key.endswith("_input") else (at.select_slider(key=key) if key == "lam_slider" else at.slider(key=key))
        widget.set_value(value)
    at.run()
    assert not at.exception, at.exception
    return at


def click(at, label=None, key=None):
    next(b for b in at.button if (b.label == label if label else b.key == key)).click().run()
    assert not at.exception, at.exception
    return at


def main_metrics(at):
    return [(m.label, m.value, m.delta) for m in at.metric[:4]]


def num(text):
    return float(re.match(r"[-+]?[\d.]+", text).group())


def message(at, needle):
    for group in (at.success, at.warning, at.info):
        for x in group:
            if needle in x.value:
                return x
    return None


def all_texts(at):
    return [x.value for group in (at.markdown, at.caption, at.success, at.info, at.warning) for x in group]


@pytest.fixture(scope="module")
def default_app():
    """Ein Lauf der Voreinstellung für die vielen lesenden Tests (AppTest-Läufe kosten Sekunden)."""
    import streamlit as st
    st.cache_data.clear()
    return fresh()


# ---------------------------------------------------------------------------------------------------
# Skelett
# ---------------------------------------------------------------------------------------------------
def test_skeleton_and_footer(default_app):
    at = default_app
    assert [h.value for h in at.sidebar.header] == ["⚙️ Einstellungen"]                 # genau EIN Header
    assert len(at.title) == 1 and "Blockzuweisung" in at.title[0].value
    assert any(v.value.startswith("## 🎯") for v in at.markdown)
    assert [s.value for s in at.subheader] == ["📐 Was kostet die Absicherung gegen verspätete Schiffe?"]
    assert [e.label for e in at.expander] == ["🔧 Wie wir das erreichen – Verfahren im Vergleich", "Wie funktioniert diese Demo?", "📐 Mathematische Formulierung"]
    assert any(c.value == FOOTER for c in at.caption)
    presets = [b.label for b in at.button if b.label in C.PRESETS]
    assert presets == list(C.PRESETS) and len(presets) == 5 and all(len(n) <= 16 for n in presets)
    assert all(b.help for b in at.button if b.label in C.PRESETS)
    assert [s.label for s in at.sidebar.slider] == ["Schiffe", "Blöcke", "Abrufrate je Block (Moves/h)", "Abrufrate der Schiffe bis (Moves/h)", "Lagerfüllung im Spitzenbestand (%)", "Verspätung σ (h)"]
    assert [s.label for s in at.sidebar.select_slider] == ["Preis der Wartezeit λ (m je min)"] and list(at.sidebar.select_slider[0].options) == ["2", "5", "10", "20", "50"]
    assert [n.label for n in at.sidebar.number_input] == ["Seed"] and any(b.label == "🎲 Neue Woche" for b in at.sidebar.button)
    assert [b.key for b in at.button if b.key in ("curve_button", "sample_button")] == ["curve_button", "sample_button"]


def test_main_metrics_are_2x2_with_signed_deltas_against_kranrate_passend(default_app):
    m = main_metrics(default_app)
    assert [x[0] for x in m] == ["Fahrweg", "Wartezeit pünktlich", "Wartezeit bei Verspätung", "Größter Beladeverzug"] and all(len(x[0]) <= 26 for x in m)
    assert 292 < num(m[0][1]) < 305 and m[0][1].endswith(" m") and m[0][2].startswith("+") and m[0][2].endswith(" m")                     # abgesichert: 298 m, +39 m gegen Kranrate passend (259,6 m)
    assert m[1][1].endswith(" min") and num(m[1][1]) < 1.0 and m[1][2] == "-20.5 min"                                                        # Kranrate passend wartet pünktlich 20,5 min
    assert 5 < num(m[2][1]) < 14 and m[2][2].startswith("-4") and m[3][2].startswith("-1")
    colors = [x.proto.color for x in default_app.metric[:4]]
    assert colors == [MetricProto.RED, MetricProto.GREEN, MetricProto.GREEN, MetricProto.GREEN]                                            # weniger Wartezeit = besser = grün; mehr Weg = rot ("inverse")


def test_the_caption_states_rate_peak_demand_and_storage_limit(default_app):
    cap = [c.value for c in default_app.caption if "Blöcke liefern zusammen" in c.value][0]
    assert cap.startswith("8 Blöcke liefern zusammen 320 Moves je Stunde; der Spitzenbedarf der 6 Schiffe liegt bei 73 % davon; Lagergrenze 864 Container je Block (Lagerfüllung 70 %); Verspätung σ = 3 h.")


def test_the_settings_helps_state_the_derived_values(default_app):
    by_label = {s.label: s.help for s in default_app.sidebar.slider}
    assert "73 % der Gesamtrate" in by_label["Abrufrate je Block (Moves/h)"] and "Ruhige Woche 29 %" in by_label["Abrufrate je Block (Moves/h)"]
    assert "jetzt 864 Container je Block" in by_label["Lagerfüllung im Spitzenbestand (%)"]
    assert "Bei 0 gibt es keine Verspätung" in by_label["Verspätung σ (h)"]


def test_the_core_section_metrics_and_the_buttons_before_anything_is_computed(default_app):
    at = default_app
    core = at.metric[4:7]
    assert [m.label for m in core] == ["Mehrweg der Absicherung", "Verspätung, Gerechnet", "Verspätung, abgesichert"]
    assert core[0].value.startswith("+3") and core[0].delta.endswith(" %") and num(core[1].value) > 30 and 5 < num(core[2].value) < 14 and core[2].delta.startswith("-")
    assert message(at, "Die Kurve ist für diese Woche noch nicht gerechnet") is not None and message(at, "Die Stichprobe ist für diese Einstellungen noch nicht gerechnet") is not None
    assert len(at.dataframe) == 1                                                                 # nur die Vergleichstabelle im Expander


def test_charts_are_present_with_unique_keys(default_app):
    charts = default_app.get("plotly_chart")
    keys = [c.key for c in charts]
    assert len(charts) == 17                                                                      # 4 Woche, 12 Verfahrens-Tabs (6 x 2), 1 Vergleich
    assert len(set(keys)) == 17 and all(keys)
    assert keys[:4] == ["week_load_left", "week_assignment_left", "week_load_right", "week_assignment_right"]


def test_no_dead_file_links_in_any_markdown(default_app):
    for text in all_texts(default_app):
        assert not re.search(r"\]\((?!https?://)", text), text
    math = "\n".join(m.value for m in default_app.expander[2].markdown)
    assert not re.search(r"\]\((?!https?://)", math)


def test_pdf_download_button_is_offered(default_app):
    buttons = default_app.get("download_button")
    assert len(buttons) == 1 and buttons[0].proto.label == "📄 Ergebnis als PDF herunterladen"


def test_texts_state_the_methods_the_assumptions_and_the_limits(default_app):
    text = "\n".join(m.value for m in default_app.expander[1].markdown)
    for needle in ("Bündeln", "Verteilen", "Kranrate passend", "Gierig", "Gerechnet", "abgesichert", "Wartezeit", "Anlieferung", "36 Stunden", "Beladefenster", "Flüssigkeitsmodell",
                   "Suchaufwand und Umstapeln im Block sind nicht modelliert", "Untergrenze", "Größenordnungen aus einer Simulation", "30 von 30", "0 von 30", "nur unter dieser Annahme",
                   "Schätzung", "größten Reste", "Fahrzeugflotte"):
        assert needle in text, needle
    math = "\n".join(m.value for m in default_app.expander[2].markdown)
    for needle in ("\\sum_b x_{sb} = n_s", "Konvexität", "2\\,\\mathrm{SE}", "größten Reste", "10^{-6}", "\\lambda", "blz_lp.py"):
        assert needle in math, needle


# ---------------------------------------------------------------------------------------------------
# Presets, Permalink
# ---------------------------------------------------------------------------------------------------
# Regel Kranrate passend ist die Referenz (exakt); gezeigt wird das abgesicherte Verfahren (Rechenplan: nur mit Abstand)
PRESET_EXPECTED = {"Stoßwoche": ("Der wartefreie Plan", "8 Blöcke liefern zusammen 320 Moves je Stunde", "Lagergrenze 864 Container", 292, 305),
                   "Späte Schiffe": ("Der wartefreie Plan", "Verspätung σ = 5 h", "Lagergrenze 864 Container", 305, 322),
                   "Voller Platz": ("Der wartefreie Plan", "Lagerfüllung 90 %", "Lagergrenze 672 Container", 296, 312),
                   "Starke Kräne": ("Der wartefreie Plan", "der Spitzenbedarf der 5 Schiffe liegt bei 85 %", "Lagergrenze 788 Container", 312, 330),
                   "Ruhige Woche": ("Ruhige Woche:", "480 Moves je Stunde", "Lagergrenze 687 Container", 243, 250)}


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_loads_within_widget_bounds_and_shows_its_story(name):
    at = fresh()
    click(at, name)
    p = C.PRESETS[name]
    assert at.slider(key="ships_slider").value == p["ships"] and at.slider(key="rate_slider").value == p["mu"] and at.slider(key="fill_slider").value == p["fill"]
    assert at.slider(key="crane_slider").value == p["crane"] and at.slider(key="sigma_slider").value == p["sigma"] and at.number_input(key="seed_input").value == p["seed"] == 2017
    assert at.select_slider(key="lam_slider").value == p["lam"]
    for state_key, spec in SETTING_SPECS.items():
        if spec.lo is not None:
            value = at.session_state[state_key]
            assert spec.lo <= value <= spec.hi and (spec.step in (None, 1) or (value - spec.lo) % spec.step == 0)
    needle, cap_needle, limit_needle, lo, hi = PRESET_EXPECTED[name]
    assert message(at, needle) is not None, name
    assert any(cap_needle in c.value and limit_needle in c.value for c in at.caption), name
    assert lo < num(main_metrics(at)[0][1]) < hi and at.query_params["sg"] in (str(p["sigma"]), [str(p["sigma"])])


def test_voller_platz_shows_the_storage_warning_and_the_others_do_not():
    at = click(fresh(), "Voller Platz")
    msg = message(at, "Lagergrenze verletzt")
    assert msg is not None and msg in list(at.warning) and "Bündeln um 177 Container" in msg.value and "Die Rechenpläne halten sie ein." in msg.value
    for name in ("Stoßwoche", "Ruhige Woche"):
        assert message(click(at, name), "Lagergrenze verletzt") is None


def test_the_rules_are_exact_at_the_shown_week_in_the_method_tabs():
    at = fresh()
    tab = at.metric[7:31]
    assert [m.label for m in tab] == ["Fahrweg", "Wartezeit pünktlich", "Wartezeit bei Verspätung", "Größter Beladeverzug"] * 6
    bundle, spread, kb, greedy = tab[0:4], tab[4:8], tab[8:12], tab[12:16]
    assert [m.value for m in bundle] == ["259 m", "148.1 min", "184.7 min", "630 min"] and [m.delta for m in bundle] == ["+0 m", "+127.6 min", "+129.5 min", "+493 min"]
    assert [m.value for m in kb] == ["260 m", "20.5 min", "55.2 min", "137 min"] and [m.delta for m in kb] == ["", "", "", ""]                # Referenz ohne Delta
    assert [m.value for m in spread] == ["453 m", "0.0 min", "4.8 min", "0 min"] and [m.delta for m in spread] == ["+194 m", "-20.5 min", "-50.4 min", "-137 min"]
    assert [m.value for m in greedy] == ["341 m", "3.3 min", "23.2 min", "32 min"] and [m.delta for m in greedy] == ["+82 m", "-17.2 min", "-32.0 min", "-105 min"]


def test_the_reference_tab_has_no_delta_and_uncoloured_deltas_when_rounded_to_zero():
    at = click(fresh(), "Ruhige Woche")
    m = main_metrics(at)
    assert m[1][2] == "+0.0 min" and m[3][2] == "+0 min" and at.metric[1].proto.color == MetricProto.GRAY and at.metric[3].proto.color == MetricProto.GRAY
    assert at.metric[0].proto.color == MetricProto.GREEN and m[0][2] == "-7 m"                     # 7 m kürzer als Kranrate passend: besser = grün


def test_permalink_is_clamped_snapped_and_ignores_garbage():
    at = fresh(sh="9", bl="3", mu="44", cr="80", fl="72", sg="9", lm="7", vw="junk")
    assert at.slider(key="ships_slider").value == 8 and at.slider(key="blocks_slider").value == 6 and at.slider(key="rate_slider").value == 40 and at.slider(key="crane_slider").value == 90
    assert at.slider(key="fill_slider").value == 70 and at.slider(key="sigma_slider").value == 6 and at.select_slider(key="lam_slider").value == 5
    assert at.radio(key="view_radio").value == C.VIEW_DEFAULT
    assert fresh(sh="abc", mu="x").slider(key="ships_slider").value == C.SHIPS_DEFAULT


def test_permalink_roundtrip_reflects_settings():
    at = fresh(sh="4", bl="10", mu="50", cr="120", fl="55", sg="1", lm="20", seed="11", vw="kranrate")
    values = {k: at.session_state[k] for k in SETTING_SPECS}
    assert values == {"ships_slider": 4, "blocks_slider": 10, "rate_slider": 50, "crane_slider": 120, "fill_slider": 55, "sigma_slider": 1, "lam_slider": 20, "seed_input": 11, "view_radio": "kranrate"}
    for key, spec in SETTING_SPECS.items():
        got = at.query_params[spec.url_param]
        got = got[0] if isinstance(got, list) else got
        assert got == spec.encoder(values[key]), key


def test_new_week_button_changes_only_the_seed():
    at = fresh()
    before = {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"}
    click(at, "🎲 Neue Woche")
    assert {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"} == before and 0 <= at.session_state["seed_input"] <= 9999


# ---------------------------------------------------------------------------------------------------
# Bedingte Meldung
# ---------------------------------------------------------------------------------------------------
def test_message_sigma_zero_is_an_info_that_names_both_plans():
    at = set_and_run(fresh(), sigma_slider=0)
    msg = message(at, "Keine Verspätung (σ = 0)")
    assert msg in list(at.info) and "gegen" in msg.value and "sichert er nichts ab" in msg.value
    assert num(at.metric[6].value) == pytest.approx(num(at.metric[5].value), abs=0.5)               # bei σ = 0 fallen die Wartezeiten bei Verspätung von Gerechnet und abgesichert zusammen


def test_message_calm_is_an_info():
    at = click(fresh(), "Ruhige Woche")
    msg = message(at, "Ruhige Woche:")
    assert msg in list(at.info) and "246 statt 253 m" in msg.value and "Kranrate passend wartet 0.0 min" in msg.value


def _forced(monkeypatch, kind):
    """Die Diagnose einer Art erzwingen: die Rechnung der Arten steht in test_evaluation, hier zählt nur, wie die App sie zeigt."""
    real = E.diagnose

    def fake(res):
        import dataclasses
        return dataclasses.replace(real(res), kind=kind)

    monkeypatch.setattr(E, "diagnose", fake)


@pytest.mark.parametrize("kind,element,needle", [("hedge", "success", "Der wartefreie Plan zerbricht"), ("fragile", "warning", "Der wartefreie Plan ist zerbrechlich"),
                                                 ("overload", "warning", "Die Blöcke sind für diese Woche zu knapp"), ("robust", "info", "hält die Verspätung aus"),
                                                 ("calm", "info", "Ruhige Woche:"), ("sigma0", "info", "Keine Verspätung")])
def test_every_kind_of_message_uses_its_element(monkeypatch, kind, element, needle):
    _forced(monkeypatch, kind)
    at = fresh()
    msg = message(at, needle)
    assert msg is not None and msg in list(getattr(at, element)), kind
    assert msg.icon == {"success": "✅", "warning": "⚠️", "info": "ℹ️"}[element]                    # Streamlit löst das Zeichen am Anfang in das Symbol des Kastens auf


def test_the_message_of_the_real_extreme_settings_is_one_of_the_known_kinds():
    at = fresh(sh="8", mu="30", cr="120", fl="90")
    assert any(message(at, n) is not None for n in ("Die Blöcke sind für diese Woche zu knapp", "Der wartefreie Plan", "hält die Verspätung aus", "Ruhige Woche:"))


# ---------------------------------------------------------------------------------------------------
# Regler an den Grenzen
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key,value", [("ships_slider", 3), ("ships_slider", 8), ("blocks_slider", 6), ("blocks_slider", 10), ("rate_slider", 30), ("rate_slider", 60), ("crane_slider", 60),
                                       ("crane_slider", 120), ("fill_slider", 50), ("fill_slider", 90), ("sigma_slider", 0), ("sigma_slider", 6), ("lam_slider", 2), ("lam_slider", 50),
                                       ("seed_input", 0), ("seed_input", 9999)])
def test_every_control_works_at_its_minimum_and_maximum(key, value):
    at = set_and_run(fresh(), **{key: value})
    assert at.session_state[key] == value and len(at.metric) >= 7 and len(at.get("plotly_chart")) == 17


def test_extreme_combinations_run_without_exception():
    at = fresh(sh="8", bl="6", mu="30", cr="120", fl="90", sg="6", lm="50")
    assert not at.exception and len(at.metric) >= 7
    at = fresh(sh="3", bl="10", mu="60", cr="60", fl="50", sg="0", lm="2")
    assert not at.exception and message(at, "Ruhige Woche:") is not None


def test_a_failing_solver_shows_an_error_instead_of_a_plan(monkeypatch):
    def boom(p, seed):
        raise L.LPError("Der Löser meldet kein Optimum (Status 2).")

    monkeypatch.setattr(E, "run_week", boom)
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception and len(at.error) == 1 and "Der Löser hat für diese Einstellung keinen Plan gefunden" in at.error[0].value and "Status 2" in at.error[0].value
    assert len(at.metric) == 0 and len(at.get("plotly_chart")) == 0                                # kein leerer Plan


# ---------------------------------------------------------------------------------------------------
# Kurve und Kante
# ---------------------------------------------------------------------------------------------------
def test_the_curve_button_computes_curve_and_edge_and_remembers_them_across_price_changes():
    at = click(fresh(), key="curve_button")
    keys = [c.key for c in at.get("plotly_chart")]
    assert "tradeoff_chart" in keys and "edge_chart" in keys and len(keys) == 19 and len(set(keys)) == 19
    assert message(at, "Die Kurve ist für diese Woche noch nicht gerechnet") is None
    caps = [c.value for c in at.caption]
    assert any(c.startswith("Basis: die eingestellte Woche (Seed 2017), 30 Testszenarien mit σ = 3 h") and "Von λ = 1 bis 100 wächst der Weg von" in c for c in caps)
    assert any(c.startswith("Basis: LP der eingestellten Woche, Wartezeit pünktlich höchstens ε.") and "Ein Knie dazwischen gibt es nicht" not in c and "ein Knie dazwischen gibt es nicht" in c for c in caps)
    at = set_and_run(at, lam_slider=20)                                                          # die Kurve läuft über alle Preise: sie bleibt, nur der eingekreiste Punkt wandert
    assert "tradeoff_chart" in [c.key for c in at.get("plotly_chart")] and message(at, "Die Kurve ist für diese Woche noch nicht gerechnet") is None


def test_the_curve_is_dropped_when_the_week_or_the_scenarios_change():
    at = click(fresh(), key="curve_button")
    at = set_and_run(at, sigma_slider=4)
    assert "tradeoff_chart" not in [c.key for c in at.get("plotly_chart")] and message(at, "Die Kurve ist für diese Woche noch nicht gerechnet") is not None
    at = click(fresh(), key="curve_button")
    at = set_and_run(at, seed_input=5)
    assert "tradeoff_chart" not in [c.key for c in at.get("plotly_chart")]


def test_the_curve_caption_numbers_come_from_the_curve():
    at = click(fresh(), key="curve_button")
    cap = next(c.value for c in at.caption if "Von λ = 1 bis 100 wächst der Weg von" in c.value)
    m = re.search(r"von (\d+) auf (\d+) m, die Wartezeit bei Verspätung fällt von ([\d.]+) auf ([\d.]+) min", cap)
    assert m and 262 < int(m.group(1)) < 285 and 350 < int(m.group(2)) < 400 and float(m.group(3)) > float(m.group(4)) + 5


# ---------------------------------------------------------------------------------------------------
# Stichprobe und Urteil
# ---------------------------------------------------------------------------------------------------
def small_sample(monkeypatch, n=3):
    monkeypatch.setattr(C, "SAMPLE_WEEKS", n)


def verdict_texts(at):
    return [x.value for group in (at.success, at.warning, at.info) for x in group if "Abgesichert gegen" in x.value or "Gerechnet gegen Kranrate" in x.value]


def test_the_sample_button_computes_the_verdicts_the_table_and_the_charts(monkeypatch):
    small_sample(monkeypatch)
    at = click(fresh(), key="sample_button")
    texts = verdict_texts(at)
    assert len(texts) == 3 and any("Abgesichert gegen Gerechnet, Wartezeit bei Verspätung" in t for t in texts) and any("Gerechnet gegen Kranrate passend, Wartezeit pünktlich" in t for t in texts)
    assert any("Abgesichert gegen Gierig, Zielwert Weg + 10 · Wartezeit bei Verspätung" in t for t in texts)
    df = at.dataframe[0].value
    assert list(df.columns) == ["Verfahren", "Fahrweg (m)", "Wartezeit pünktlich (min)", "Wartezeit bei Verspätung (min)"] and list(df["Verfahren"]) == [C.METHOD_LABELS[k] for k in C.METHOD_KEYS]
    assert re.fullmatch(r"\d+\.\d \[\d+\.\d; \d+\.\d\]", df["Fahrweg (m)"][0])
    keys = [c.key for c in at.get("plotly_chart")]
    for k in ("spread_distance_chart", "spread_wait_chart", "distribution_hedge_chart", "distribution_lp_chart"):
        assert k in keys
    assert len(keys) == len(set(keys)) == 21
    assert message(at, "Die Stichprobe ist für diese Einstellungen noch nicht gerechnet") is None
    cap = next(c.value for c in at.caption if c.value.startswith("Basis: 3 Wochen (Seeds 3000-3002, nicht Ihr Seed)"))
    assert "Mehrweg der Absicherung gegen den Gerechnet-Plan liegt im Median bei" in cap


def test_the_sample_does_not_depend_on_the_seed_but_on_the_other_settings(monkeypatch):
    small_sample(monkeypatch)
    at = click(fresh(), key="sample_button")
    before = verdict_texts(at)
    at = set_and_run(at, seed_input=5)
    assert verdict_texts(at) == before                                                             # dieselben Wochen (Seeds ab 3000) bei anderem eingestellten Seed
    at = set_and_run(at, sigma_slider=4)
    assert verdict_texts(at) == [] and message(at, "Die Stichprobe ist für diese Einstellungen noch nicht gerechnet") is not None


def test_the_full_sample_of_twenty_weeks_carries_the_story():
    at = click(fresh(), key="sample_button")
    texts = verdict_texts(at)
    assert len(texts) == 3
    hedge = next(t for t in texts if t.startswith("**Abgesichert gegen Gerechnet"))
    assert "weniger**" in hedge and "In **0 %** der Wochen ist es umgekehrt." in hedge                # die Absicherung senkt die Wartezeit bei Verspätung in allen 20 Wochen klar
    assert next(t for t in texts if t.startswith("**Gerechnet gegen Kranrate passend")).count("weniger") >= 1
    caps = [c.value for c in at.caption if c.value.startswith("Basis: 20 Wochen (Seeds 3000-3019, nicht Ihr Seed)")]
    assert len(caps) == 1


@pytest.mark.parametrize("kind,pct,expected", [
    ("better", -40.0, "im Mittel **40 % weniger** Wartezeit (-2.00 min je Woche, Standardfehler 0.50)."),
    ("better", None, "im Mittel **2.00 min weniger** Wartezeit (-2.00 min je Woche, Standardfehler 0.50)."),
    ("worse", 25.0, "im Mittel **25 % mehr** Wartezeit (+2.00 min je Woche, Standardfehler 0.50)."),
    ("worse", None, "im Mittel **2.00 min mehr** Wartezeit (+2.00 min je Woche, Standardfehler 0.50)."),
])
def test_verdict_sentences_in_the_four_variants(monkeypatch, kind, pct, expected):
    small_sample(monkeypatch, 2)
    monkeypatch.setattr(E, "verdict", lambda rows, key, ref, field="wait_shift": E.Verdict(kind, -2.0 if kind == "better" else 2.0, 0.5, pct, 20, field))
    at = click(fresh(), key="sample_button")
    texts = verdict_texts(at)
    assert len(texts) == 3 and all(t.count("(") == t.count(")") for t in texts)
    assert expected in texts[0] and expected in texts[1]                                           # Wartezeit in min
    assert expected.replace("Wartezeit", "Zielwert").replace(" min", " m") in texts[2]              # Zielwert in m
    element = at.success if kind == "better" else at.warning
    assert sum(1 for x in element if "Standardfehler 0.50" in x.value) == 3


def test_verdict_unclear(monkeypatch):
    small_sample(monkeypatch, 2)
    monkeypatch.setattr(E, "verdict", lambda rows, key, ref, field="wait_shift": E.Verdict("unclear", 0.1, 0.5, 1.0, 20, field))
    at = click(fresh(), key="sample_button")
    texts = verdict_texts(at)
    assert len(texts) == 3 and all(t.startswith("Kein klarer Unterschied") for t in texts) and all("Rauschens" in t and "gemittelt über die Wochen" in t for t in texts)
    assert sum(1 for x in at.info if x.value.startswith("Kein klarer Unterschied")) == 3


# ---------------------------------------------------------------------------------------------------
# Blick in die Woche
# ---------------------------------------------------------------------------------------------------
def test_view_radio_switches_the_method_shown_in_the_metrics_and_the_permalink():
    at = fresh()
    assert at.radio(key="view_radio").value == "abgesichert" and list(at.radio(key="view_radio").options) == [C.METHOD_LABELS[k] for k in C.METHOD_KEYS]
    at = at.radio(key="view_radio").set_value("gierig").run()
    assert not at.exception and main_metrics(at) == [("Fahrweg", "341 m", "+82 m"), ("Wartezeit pünktlich", "3.3 min", "-17.2 min"), ("Wartezeit bei Verspätung", "23.2 min", "-32.0 min"),
                                                     ("Größter Beladeverzug", "32 min", "-105 min")]
    assert at.query_params["vw"] in ("gierig", ["gierig"])
    at = at.radio(key="view_radio").set_value("kranrate").run()
    assert main_metrics(at) == [("Fahrweg", "260 m", ""), ("Wartezeit pünktlich", "20.5 min", ""), ("Wartezeit bei Verspätung", "55.2 min", ""), ("Größter Beladeverzug", "137 min", "")]
    assert [m.proto.color for m in at.metric[:4]] == [MetricProto.GRAY] * 4                        # die Referenz hat kein Delta


def test_the_week_charts_share_the_colour_scale():
    at = fresh()
    charts = {c.key: c for c in at.get("plotly_chart")}
    left, right = charts["week_load_left"].proto.spec, charts["week_load_right"].proto.spec
    zmax = lambda spec: re.search(r'"zmax":\s*([\d.]+)', spec).group(1)                              # noqa: E731
    assert zmax(left) == zmax(right)


def test_day_caption_explains_the_charts(default_app):
    assert any("Oben die Blocklast (Abrufe plus Anlieferungen) in Prozent der Blockrate je Stunde" in c.value and "Unten die Belegung" in c.value for c in default_app.caption)


# ---------------------------------------------------------------------------------------------------
# Verfahrensvergleich, PDF
# ---------------------------------------------------------------------------------------------------
def test_comparison_table_has_a_row_per_method_with_the_right_cells(default_app):
    df = default_app.dataframe[0].value
    assert list(df["Verfahren"]) == [C.METHOD_LABELS[k] for k in C.METHOD_KEYS]
    assert list(df["Fahrweg (m)"])[:4] == [259, 453, 260, 341] and list(df["Wartezeit pünktlich (min)"])[:4] == [148.1, 0.0, 20.5, 3.3] and list(df["Wartezeit bei Verspätung (min)"])[:4] == [184.7, 4.8, 55.2, 23.2]
    assert list(df["Container über der Lagergrenze"]) == [0] * 6 and list(df["Delta Fahrweg (m)"])[:4] == [0, 194, 0, 82] and list(df["Delta Wartezeit bei Verspätung (min)"])[2] == 0.0


def test_the_comparison_tab_chart_and_caption(default_app):
    assert "comparison_tradeoff_chart" in [c.key for c in default_app.get("plotly_chart")]
    assert any("Eine Woche, sechs Verfahren, dieselben Schiffe und dieselben Testszenarien" in c.value for c in default_app.caption)


def test_the_method_panels_show_bound_and_limit_texts():
    at = click(fresh(), "Voller Platz")
    caps = [c.value for c in at.caption]
    assert any(c.startswith("LP-Wert (Schranke): kleinstmögliche Wartezeit") and "der gerundete Plan wartet" in c for c in caps)
    assert any(c.startswith("LP-Wert (Schranke) bei λ = 10:") and "gerundete Plan kommt auf" in c for c in caps)
    assert any(c.startswith("Lagergrenze überschritten: bis zu 177 Container über der Grenze von 672 Containern je Block.") for c in caps)


def test_the_pdf_contains_curve_and_sample_only_after_they_are_computed(monkeypatch):
    import blz_pdf_export as PDF
    seen = []
    real = PDF.generate_blz_pdf

    def spy(p, seed, res, diag, curve=None, sample=None, compress=True):
        seen.append((curve is not None, sample is not None))
        return real(p, seed, res, diag, curve=curve, sample=sample, compress=compress)

    monkeypatch.setattr(PDF, "generate_blz_pdf", spy)
    small_sample(monkeypatch, 2)
    at = fresh()
    assert seen[-1] == (False, False)
    at = click(at, key="curve_button")
    assert seen[-1] == (True, False)
    click(at, key="sample_button")
    assert seen[-1] == (True, True)
