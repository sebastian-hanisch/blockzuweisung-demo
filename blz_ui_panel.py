"""Wiederverwendbares Panel zur Darstellung eines Verfahrens im Verfahrensvergleich (je Verfahren ein Tab)."""

import streamlit as st

import blz_constants as C
import blz_evaluation as E
import blz_visualization as V


def metric_cells(outcome, baseline):
    """Die vier Kennzahlen eines Verfahrens als (Beschriftung, Wert, Delta gegen Kranrate passend oder None, Delta-Farbe, Hilfetext); Deltas lesen sich immer als "dieses Verfahren minus Kranrate passend"
    (weniger ist besser: "inverse"); ein Delta, das auf 0 rundet, bleibt ungefärbt ("off")."""
    o, b = outcome, baseline
    ref = outcome.key == C.BASELINE
    hint = "Delta gegen Kranrate passend; weniger ist besser."
    spec = [
        ("Fahrweg", f"{o.m.distance:.0f} m", o.m.distance - b.m.distance, 0, "m", f"Mittlerer Fahrweg je Container vom Block zum Schiff (einfach). {hint}"),
        ("Wartezeit pünktlich", f"{o.m.wait:.1f} min", o.m.wait - b.m.wait, 1, "min", f"Mittlere Wartezeit je Container am Block, wenn alle Schiffe pünktlich sind. {hint}"),
        ("Wartezeit bei Verspätung", f"{o.robust.wait:.1f} min", o.robust.wait - b.robust.wait, 1, "min",
         f"Dieselbe Wartezeit, wenn sich die Beladefenster verschieben (Mittel über {C.N_TEST} Szenarien). {hint}"),
        ("Größter Beladeverzug", f"{o.m.delay_max:.0f} min", o.m.delay_max - b.m.delay_max, 0, "min",
         f"Wie lange das am schlechtesten versorgte Schiff am Ende seines Fensters noch auf seine Container wartet (pünktliche Schiffe). {hint}"),
    ]
    return [(label, value, None if ref else f"{E.signed(diff, digits)} {unit}", "inverse" if not ref and round(diff, digits) != 0 else "off", help_text)
            for label, value, diff, digits, unit, help_text in spec]


def render_metrics(outcome, baseline):
    """Die vier Kennzahlen im 2 x 2-Raster (vier Spalten schneiden die Namen bei 800 px ab)."""
    rows = st.columns(2), st.columns(2)
    cells = rows[0] + rows[1]
    for col, (label, value, delta, color, help_text) in zip(cells, metric_cells(outcome, baseline)):
        col.metric(label, value, delta=delta, delta_color=color, help=help_text)


def bound_text(outcome, lam):
    """Der LP-Wert (Schranke) und der Wert des auf ganze Container gerundeten Plans; leer bei den Regeln."""
    b = outcome.bound
    if b is None:
        return ""
    gap = "" if b.gap is None else f" (Rundung {max(b.gap, 0.0):.1f} % darüber)"
    if outcome.key == C.M_LP:
        return f"LP-Wert (Schranke): kleinstmögliche Wartezeit {b.objective:.2f} min bei {b.lp_distance:.1f} m Weg; der gerundete Plan wartet {b.rounded:.2f} min{gap}."
    return (f"LP-Wert (Schranke) bei λ = {lam:g}: {b.objective:.1f} m (Weg {b.lp_distance:.1f} m plus λ mal {b.lp_wait:.2f} min an den Planungsszenarien); der auf ganze Container gerundete Plan "
            f"kommt auf {b.rounded:.1f} m{gap}.")


def render_method_panel(prefix, outcome, outcomes, week, lam, zmax=None):
    """Beschreibung, Kennzahlen (2 x 2), Belegung Schiff x Block und Blocklast eines Verfahrens. `outcomes`: alle sechs Outcomes einer Woche (Referenz: Kranrate passend)."""
    baseline = next(o for o in outcomes if o.key == C.BASELINE)
    st.markdown(C.METHOD_DESCRIPTIONS[outcome.key])
    render_metrics(outcome, baseline)
    if outcome.bound is not None:
        st.caption(bound_text(outcome, lam))
    if outcome.m.stock_over > C.STOCK_TOLERANCE:
        st.caption(f"Lagergrenze überschritten: bis zu {outcome.m.stock_over:.0f} Container über der Grenze von {week.limit:.0f} Containern je Block.")
    st.plotly_chart(V.assignment_figure(week, outcome.x, "Belegung: Container je Schiff und Block"), width="stretch", key=f"{prefix}_assignment_chart")
    st.plotly_chart(V.load_figure(week, outcome.m.load, "Blocklast in % der Rate", zmax), width="stretch", key=f"{prefix}_load_chart")
