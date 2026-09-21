"""
Blockzuweisung im Export – interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Zusatz zur Hafen-Linie (Kai, Block, Kran): Welche Exportcontainer eines Schiffs kommen in welchen Block des Containerlagers? Gezeigt wird, wie viel Fahrweg es kostet, die Blockkräne beim Beladen
nicht zum Nadelöhr werden zu lassen, wie viel ein gerechneter Plan gegenüber den Alltagsregeln spart und was eine Absicherung gegen verspätete Schiffe kostet.

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import blz_constants as C
import blz_evaluation as E
import blz_lp as L
import blz_scenario as S
import blz_ui_panel as UI
import blz_visualization as V
from blz_pdf_export import generate_blz_pdf
from blz_presets import apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, SETTING_SPECS, sync_query_params

st.set_page_config(page_title="Blockzuweisung im Export – Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = list(SETTING_SPECS)
BUNDLE, SPREAD, KBLOCKS, GREEDY, LP, HEDGE = C.METHOD_KEYS
LABEL = C.METHOD_LABELS


@st.cache_data(show_spinner=False, max_entries=32)
def _compute_week(key):
    """Eine Woche (Seed) mit allen sechs Verfahren, bewertet pünktlich und an 30 Szenarien (etwa 0,7 s)."""
    return E.run_week(E.Params(*key[:-1]), key[-1])


@st.cache_data(show_spinner=False, max_entries=8)
def _compute_curve(key):
    """Kurve "Preis der Absicherung" und Kante: sieben Szenario-LP und neun LP (etwa 4 s). Der eingestellte Preis geht nicht ein (die Kurve läuft über alle Preise)."""
    return E.price_curve(E.Params(*key[:-1]), key[-1])


@st.cache_data(show_spinner=False, max_entries=200)
def _compute_row(key):
    """Eine Woche der Stichprobe (nur Kennzahlen, ohne Plan)."""
    return E.week_row(E.Params(*key[:-1]), key[-1])


st.title("🏗️ Blockzuweisung: In welchen Block kommen die Exportcontainer?")
st.markdown(
    """
Nach dem Kai fahren die Exportcontainer eines Schiffs aus dem Lager. Kommen sie aus einem **Block**, sind die **Fahrwege** kurz, aber dessen Blockkräne kommen nicht nach; verteilt man sie, entlastet das die
Kräne und verlängert die Wege. Die Demo zeigt, wie viel Fahrweg eine gute Verteilung kostet, wie viel besser ein **gerechneter Plan** ist als die Alltagsregeln und was passiert, wenn die Schiffe zu anderen
Zeiten kommen als geplant (**Absicherung**). Wie das Modell funktioniert, steht im Expander "Wie funktioniert diese Demo?" weiter unten, die formale Beschreibung im Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Stoßwoche": "Die Kernaussage: der wartefreie Plan zerbricht bei Verspätung, die Absicherung kostet etwa 40 m Fahrweg.",
    "Späte Schiffe": "Wie Stoßwoche, aber die Beladefenster streuen mit σ = 5 h: der pünktliche Plan ist noch schlechter, die Absicherung kostet mehr, bleibt aber lohnend.",
    "Voller Platz": "Das Lager ist zu 90 % gefüllt: Bündeln und schiffsweise Regeln sprengen die Lagergrenze, nur der Rechenplan hält sie und bleibt kurz.",
    "Starke Kräne": "Fünf Schiffe mit Kränen bis 120 Moves/h: jedes Schiff braucht zwei bis drei Blöcke, die Alltagsregel kommt kaum hinterher.",
    "Ruhige Woche": "Vier Schiffe, Blockrate 60, kleine Verspätung: alle Regeln außer Verteilen sind gleich gut, Rechnen spart nur wenige Meter, Absichern kostet nichts.",
}
# Je Zeile drei Schaltflächen: bei fünf in einer Zeile werden die Namen in schmalen Fenstern abgeschnitten.
preset_names = list(C.PRESETS.keys())
for row in (preset_names[:3], preset_names[3:]):
    cols = st.columns(3)
    for col, name in zip(cols, row):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

ss = st.session_state
week_now = S.make_week(ss["seed_input"], ss["ships_slider"], ss["blocks_slider"], float(ss["rate_slider"]), ss["crane_slider"], ss["fill_slider"])
peak_now = S.peak_ratio(week_now)

with st.sidebar:
    st.header("⚙️ Einstellungen")
    ships = st.slider("Schiffe", *bounds("ships_slider"), key="ships_slider", help="Zahl der Schiffe der Woche (700 bis 1300 Exportcontainer je Schiff). Mehr Schiffe: mehr Überlappungen der Beladefenster.")
    blocks = st.slider("Blöcke", *bounds("blocks_slider"), key="blocks_slider", help="Zahl der Blöcke im Abstand von 100 m am Kai. Mehr Blöcke: mehr Auswahl, die Rechenzeit wächst leicht.")
    mu = st.slider("Abrufrate je Block (Moves/h)", *bounds("rate_slider"), step=C.RATE_STEP, key="rate_slider",
                   help=f"Was alle Blockkräne eines Blocks zusammen je Stunde liefern. Der Spitzenbedarf der Schiffe gleichzeitig liegt bei {peak_now * 100:.0f} % der Gesamtrate aller Blöcke: "
                        "Gemessen (Median über 100 Wochen): Stoßwoche 72 %, Starke Kräne 91 %, Ruhige Woche 29 %; bei so wenig Last kommt jedes Schiff mit einem Block aus und die Regeln gleichen sich.")
    crane = st.slider("Abrufrate der Schiffe bis (Moves/h)", *bounds("crane_slider"), step=C.CRANE_STEP, key="crane_slider",
                      help="Obere Abrufrate der Schiffskräne r; jedes Schiff ruft mit r oder mit zwei Dritteln von r ab. Sie bestimmt, wie viele Blöcke ein Schiff braucht (Abrufrate durch Blockrate, aufgerundet).")
    fill = st.slider("Lagerfüllung im Spitzenbestand (%)", *bounds("fill_slider"), step=C.FILL_STEP, format="%d%%", key="fill_slider",
                     help=f"Wie voll das Lager im Spitzenbestand ist. Daraus folgt die Lagergrenze: jetzt {week_now.limit:.0f} Container je Block. Über 90 % wird das Lager im Modell zu eng (gemessen bis 91 %).")
    sigma = st.slider("Verspätung σ (h)", *bounds("sigma_slider"), key="sigma_slider",
                      help="Streuung der Verschiebung jedes Beladefensters in ganzen Stunden (die Anlieferung bleibt). Bei 0 gibt es keine Verspätung: der abgesicherte Plan sichert dann nichts ab.")
    lam = st.select_slider("Preis der Wartezeit λ (m je min)", options=C.LAM_CHOICES, key="lam_slider",
                           help="Wie viele Meter Fahrweg eine Minute Wartezeit dem Betreiber wert ist. Bestimmt den Punkt auf der Kurve des abgesicherten Plans: kleiner = kürzerer Weg, größer = weniger Wartezeit.")
    seed = st.number_input("Seed", *bounds("seed_input"), key="seed_input", step=1, help="Bestimmt Schiffe, Liegeplätze, Beladefenster und die Verspätungsszenarien der Woche.")
    st.button("🎲 Neue Woche", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Seed für die Woche.")

sync_query_params({key: st.session_state[key] for key in SCENARIO_KEYS})

p = E.Params(int(ships), int(blocks), int(mu), int(crane), int(fill), int(sigma), int(lam))
try:
    with st.spinner("Rechne die Woche mit allen sechs Verfahren..."):
        res = _compute_week(tuple(p) + (int(seed),))
except L.LPError as err:
    st.error(f"Der Löser hat für diese Einstellung keinen Plan gefunden: {err} Bitte einen anderen Seed oder andere Einstellungen wählen.")
    st.stop()
by_key = {o.key: o for o in res.outcomes}
week = res.week
base = by_key[C.BASELINE]
diag = E.diagnose(res)

# ---------------------------------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------------------------------
st.markdown("## 🎯 Wie viel Fahrweg, wie viel Wartezeit am Block?")
st.caption(f"{p.blocks} Blöcke liefern zusammen {p.blocks * p.mu} Moves je Stunde; der Spitzenbedarf der {p.ships} Schiffe liegt bei {peak_now * 100:.0f} % davon; Lagergrenze {week.limit:.0f} Container je Block "
           f"(Lagerfüllung {p.fill} %); Verspätung σ = {p.sigma} h. Angezeigt wird das gewählte Verfahren (siehe Blick in die Woche); Delta = Verfahren minus Kranrate passend.")

right_key = ss.get("view_radio", C.VIEW_DEFAULT)
chosen = by_key[right_key]
UI.render_metrics(chosen, base)

text = E.diagnosis_text(diag, p)
if diag.kind == "hedge":
    st.success(f"✅ {text}")
elif diag.kind in ("calm", "robust", "sigma0"):
    st.info(f"ℹ️ {text}")
else:
    st.warning(f"⚠️ {text}")
if diag.stock:
    st.warning(f"⚠️ {E.stock_text(diag)}")

st.markdown("#### 🔍 Blick in die Woche")
right_key = st.radio("Rechts vergleichen mit", list(C.METHOD_KEYS), format_func=LABEL.get, key="view_radio", horizontal=True, help="Links steht immer Kranrate passend.")
right = by_key[right_key]
zmax = V.shared_load_max([base.m.load, right.m.load], week.mu)                       # beide Diagramme mit derselben Farbskala: sie sollen sich vergleichen lassen
left_col, right_col = st.columns(2)
for col, outcome, side in ((left_col, base, "left"), (right_col, right, "right")):
    with col:
        st.plotly_chart(V.load_figure(week, outcome.m.load, f"{C.METHOD_SHORT[outcome.key]}: Blocklast in % der Rate", zmax), width="stretch", key=f"week_load_{side}")
        st.plotly_chart(V.assignment_figure(week, outcome.x, f"{C.METHOD_SHORT[outcome.key]}: Container je Schiff und Block"), width="stretch", key=f"week_assignment_{side}")
st.caption("Oben die Blocklast (Abrufe plus Anlieferungen) in Prozent der Blockrate je Stunde: über 100 % (orange bis rot) wächst der Rückstand, das Schiff wartet auf seine Container. Unten die Belegung: "
           "wie viele Container von welchem Schiff in welchen Block gehen (Zahl in Klammern: Container des Schiffs).")

pdf_slot = st.container()

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
st.subheader("📐 Was kostet die Absicherung gegen verspätete Schiffe?")
st.markdown(
    """
Kernfrage dieser Demo: Wie viel **Fahrweg** kostet es, die Container so auf die Blöcke zu verteilen, dass die Blockkräne auch bei **verspäteten Schiffen** nicht zum Nadelöhr werden? Der Rechenplan für
pünktliche Schiffe ist wartefrei, aber **zerbrechlich**: er füllt die Blöcke in den Überlappungen bis an die Grenze. Der **abgesicherte Plan** plant mit zehn Verspätungsszenarien und kauft Sicherheit mit
Fahrweg; der **Preis λ** (Meter je Minute Wartezeit) wählt den Punkt auf der Kurve. Hier für Ihre Woche gerechnet:
"""
)
lp_o, hd_o = by_key[LP], by_key[HEDGE]
g1, g2, g3 = st.columns(3)
g1.metric("Mehrweg der Absicherung", f"{E.signed(diag.extra)} m", delta=f"{E.signed(diag.extra_pct)} %", delta_color="off", help="Fahrweg des abgesicherten Plans minus Fahrweg des Gerechnet-Plans (Prozent: davon).")
g2.metric("Verspätung, Gerechnet", f"{lp_o.robust.wait:.1f} min", help=f"Wartezeit des wartefreien Plans, wenn sich die Beladefenster verschieben (Mittel über {C.N_TEST} Szenarien); pünktlich {lp_o.m.wait:.1f} min.")
g3.metric("Verspätung, abgesichert", f"{hd_o.robust.wait:.1f} min", delta=f"{E.signed(hd_o.robust.wait - lp_o.robust.wait, 1)} min", delta_color="inverse" if abs(hd_o.robust.wait - lp_o.robust.wait) >= 0.05 else "off",
          help=f"Dieselbe Wartezeit beim abgesicherten Plan mit Preis λ = {p.lam} m je min; Delta gegen Gerechnet.")

curve_key = tuple(p._replace(lam=C.LAM_DEFAULT)) + (int(seed),)
sample_key = tuple(p)
bcol1, bcol2 = st.columns(2)
with bcol1:
    if st.button("📈 Kurve und Kante rechnen (etwa 4 s)", width="stretch", key="curve_button",
                 help="Sieben Szenario-LP mit Preisen von 1 bis 100 m je min und neun LP für die Kante (kürzester Weg unter erlaubter Wartezeit), für die eingestellte Woche."):
        with st.spinner("Rechne sieben Szenario-LP und die Kante..."):
            st.session_state["curve_result"] = (curve_key, _compute_curve(curve_key))
with bcol2:
    if st.button(f"📊 Stichprobe rechnen ({C.SAMPLE_WEEKS} Wochen, etwa 15 s)", width="stretch", key="sample_button",
                 help=f"{C.SAMPLE_WEEKS} andere Wochen (Seeds ab {C.SAMPLE_BASE}, nicht Ihr Seed) mit Ihren Einstellungen und allen sechs Verfahren: Verteilung statt Einzelwoche."):
        bar = st.progress(0.0, text="Rechne die Stichprobe...")
        rows_done = []
        for i in range(C.SAMPLE_WEEKS):
            rows_done.append(_compute_row(sample_key + (C.SAMPLE_BASE + i,)))
            bar.progress((i + 1) / C.SAMPLE_WEEKS, text=f"Woche {i + 1} von {C.SAMPLE_WEEKS}")
        bar.empty()
        st.session_state["sample_result"] = (sample_key, tuple(rows_done))

stored_curve = st.session_state.get("curve_result")
curve = stored_curve[1] if stored_curve and stored_curve[0] == curve_key else None
stored_sample = st.session_state.get("sample_result")
sample = stored_sample[1] if stored_sample and stored_sample[0] == sample_key else None

st.markdown("**Preis der Absicherung: Fahrweg gegen Wartezeit bei Verspätung**")
if curve is None:
    st.info("ℹ️ Die Kurve ist für diese Woche noch nicht gerechnet: Knopf „Kurve und Kante rechnen“ (die Regler wirken nicht auf eine früher gerechnete Kurve).")
else:
    st.plotly_chart(V.tradeoff_figure(res.outcomes, curve, p.lam), width="stretch", key="tradeoff_chart")
    knee = {pt.lam: pt for pt in curve.points}
    st.caption(f"Basis: die eingestellte Woche (Seed {int(seed)}), {C.N_TEST} Testszenarien mit σ = {p.sigma} h (andere Zufallszahlen als die {C.N_TRAIN} Planungsszenarien der Kurve). Quadrate: Regeln und der Rechenplan für "
               "pünktliche Schiffe; grüne Linie: der abgesicherte Plan mit Preis λ (kleiner Preis links, großer Preis rechts), der eingestellte Preis ist eingekreist. Links unten ist gut: die Kurve liegt "
               f"unter den Regeln. Von λ = 1 bis 100 wächst der Weg von {knee[1].distance:.0f} auf {knee[100].distance:.0f} m, die Wartezeit bei Verspätung fällt von {knee[1].wait_shift:.1f} auf {knee[100].wait_shift:.1f} min.")
    st.markdown("**Die Kante: kürzester Weg bei erlaubter Wartezeit (pünktliche Schiffe)**")
    st.plotly_chart(V.edge_figure(curve), width="stretch", key="edge_chart")
    edge = dict(curve.edge)
    st.caption(f"Basis: LP der eingestellten Woche, Wartezeit pünktlich höchstens ε. Die kleinstmögliche Wartezeit beträgt {curve.min_wait:.2f} min; sie zu erreichen kostet {edge[1]:.0f} m gegen {curve.bundle_distance:.0f} m beim "
               f"Bündeln und {curve.spread_distance:.0f} m beim Verteilen: ab wenigen Minuten erlaubter Wartezeit ist fast nichts mehr zu gewinnen. Die Kante ist die Aussage, ein Knie dazwischen gibt es nicht.")


def _show_verdict(spec):
    kind, sentence = E.verdict_text(sample, *spec)
    if kind == "better":
        st.success(f"✅ {sentence}")
    elif kind == "worse":
        st.warning(f"⚠️ {sentence}")
    else:
        st.info(f"ℹ️ {sentence}")


st.markdown("**Urteil über die Stichprobe** (gepaarte Differenz je Woche, klar ab mehr als zwei Standardfehlern)")
if sample is None:
    st.info("ℹ️ Die Stichprobe ist für diese Einstellungen noch nicht gerechnet: Knopf „Stichprobe rechnen“. Sie hängt nicht vom Seed ab.")
else:
    specs = E.verdict_specs(p.lam)
    for spec in specs:
        _show_verdict(spec)
    rows_t = []
    for k in C.METHOD_KEYS:
        cells = {"Verfahren": LABEL[k]}
        for name, field in (("Fahrweg (m)", "distance"), ("Wartezeit pünktlich (min)", "wait"), ("Wartezeit bei Verspätung (min)", "wait_shift")):
            med, lo, hi = E.spread_of(sample, k, field)
            cells[name] = f"{med:.1f} [{lo:.1f}; {hi:.1f}]"
        rows_t.append(cells)
    st.markdown("**Verteilung über die Wochen: Median [10. bis 90. Perzentil]** (die Wartezeit ist schief, das Mittel allein täuscht)")
    st.dataframe(pd.DataFrame(rows_t), width="stretch", hide_index=True)
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown("**Fahrweg je Verfahren** (Median und 10. bis 90. Perzentil)")
        st.plotly_chart(V.spread_figure(sample, "distance", "Fahrweg je Container (m)"), width="stretch", key="spread_distance_chart")
    with dcol2:
        st.markdown("**Wartezeit bei Verspätung je Verfahren**")
        st.plotly_chart(V.spread_figure(sample, "wait_shift", "Wartezeit bei Verspätung (min)"), width="stretch", key="spread_wait_chart")
    ecol1, ecol2 = st.columns(2)
    with ecol1:
        st.markdown("**Abgesichert gegen Gerechnet** (Anteil der Wochen, Wartezeit bei Verspätung)")
        st.plotly_chart(V.distribution_figure([E.distribution(sample, HEDGE, LP, "wait_shift")], ["abgesichert"], "Gerechnet", "Wartezeit"), width="stretch", key="distribution_hedge_chart")
    with ecol2:
        st.markdown("**Gerechnet gegen Kranrate passend** (Anteil der Wochen, Wartezeit pünktlich)")
        st.plotly_chart(V.distribution_figure([E.distribution(sample, LP, KBLOCKS, "wait")], ["Gerechnet"], "Kranrate passend", "Wartezeit"), width="stretch", key="distribution_lp_chart")
    extra_med = E.median_diff(sample, HEDGE, LP, "distance")
    st.caption(f"Basis: {len(sample)} Wochen (Seeds {sample[0].seed}-{sample[-1].seed}, nicht Ihr Seed) mit Ihren Einstellungen. Der Mehrweg der Absicherung gegen den Gerechnet-Plan liegt im Median bei {extra_med:.0f} m "
               f"(10. bis 90. Perzentil {E.percentile(E.paired(sample, HEDGE, LP, 'distance'), C.PCT_LO):.0f} bis {E.percentile(E.paired(sample, HEDGE, LP, 'distance'), C.PCT_HI):.0f} m). "
               "Der Zielwert ist Weg plus λ mal Wartezeit bei Verspätung.")

kb_cost = base.m.distance + p.lam * base.robust.wait
gr_cost = by_key[GREEDY].m.distance + p.lam * by_key[GREEDY].robust.wait
hd_cost = hd_o.m.distance + p.lam * hd_o.robust.wait
st.markdown(
    f"""
**Zweiter Befund: schiffsweise Regeln sind kurzsichtig.** Eine Regel entscheidet Schiff für Schiff und sieht die späteren Schiffe nicht; der Rechenplan sieht alle zugleich. In dieser Woche kommt bei Ihrem
Preis λ = {p.lam} m je min die Regel Gierig auf einen Zielwert (Weg plus λ mal Wartezeit bei Verspätung) von **{gr_cost:.0f} m**, Kranrate passend auf **{kb_cost:.0f} m**, der abgesicherte Plan auf **{hd_cost:.0f} m**.
Der dritte Satz des Urteils über die Stichprobe (nach dem Knopf) sagt, ob das über viele Wochen gilt. Dieser Vergleich trennt allerdings zwei Dinge nicht: der abgesicherte Plan sieht alle Schiffe **und**
die Verspätungsszenarien, die Regel Gierig keins von beiden. Getrennt hat es die Messreihe (eine gierige Regel, die jeden Posten von 20 Containern nach dem Zuwachs von Weg plus λ mal Wartezeit über dieselben
Szenarien verteilt): sie liegt im Zielwert 27 % bis 130 % über dem LP (10 Wochen, λ = 5 bis 50); in dieser Demo ist diese Regel nicht enthalten, die Zahl ist nicht nachgerechnet.
"""
)

with pdf_slot:
    st.download_button(
        "📄 Ergebnis als PDF herunterladen",
        data=generate_blz_pdf(p, int(seed), res, diag, curve=curve, sample=sample),
        file_name="blockzuweisung_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download",
        help="Szenario, Zusammenfassung, Verfahrensvergleich und, falls schon gerechnet, Kurve, Kante und Stichprobe mit Urteil.")

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Verfahrensvergleich
# ---------------------------------------------------------------------------------------------------
with st.expander("🔧 Wie wir das erreichen – Verfahren im Vergleich"):
    tabs = st.tabs([o.label for o in res.outcomes] + ["📊 Vergleich"])
    for tab, outcome in zip(tabs, res.outcomes):
        with tab:
            UI.render_method_panel(f"method_{outcome.key}", outcome, res.outcomes, week, p.lam)
    with tabs[len(res.outcomes)]:
        table = []
        for o in res.outcomes:
            table.append({"Verfahren": o.label, "Fahrweg (m)": round(o.m.distance), "Wartezeit pünktlich (min)": round(o.m.wait, 1), "Wartezeit bei Verspätung (min)": round(o.robust.wait, 1),
                          "Größter Beladeverzug (min)": round(o.m.delay_max), "Container über der Lagergrenze": round(o.m.stock_over), "Delta Fahrweg (m)": round(o.m.distance - base.m.distance),
                          "Delta Wartezeit bei Verspätung (min)": round(o.robust.wait - base.robust.wait, 1)})
        st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)
        st.markdown("**Fahrweg gegen Wartezeit bei Verspätung** (diese Woche)")
        st.plotly_chart(V.tradeoff_figure(res.outcomes), width="stretch", key="comparison_tradeoff_chart")
        st.caption("Eine Woche, sechs Verfahren, dieselben Schiffe und dieselben Testszenarien. Links unten ist gut. Was weit über den übrigen liegt (Bündeln), wird am oberen Rand gezeichnet und beschriftet.")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Die Woche.** Ein Terminal hat **Blöcke** im Abstand von 100 m am Kai und drei Liegeplätze. Jedes Schiff hat 700 bis 1300 **Exportcontainer** und ein **Beladefenster** von ganzen Stunden; es ruft seine
Container gleichmäßig über das Fenster ab, mit einer Rate von r oder zwei Dritteln davon (Regler). Jeder Block liefert höchstens so viele Moves je Stunde, wie die **Abrufrate je Block** sagt. Der **Fahrweg**
eines Containers vom Block zum Schiff ist 200 m plus der Abstand zwischen Block und Liegeplatz. Die Container eines Schiffs kommen gleichmäßig in den **36 Stunden vor dem Fenster** im Lager an und belasten
den Block ebenfalls (ein Move je Container). Was der Block in einer Stunde nicht schafft, wartet als **Rückstand**; die **Wartezeit** ist die mittlere Wartezeit je Container am Block.

**Der Plan** ist die Aufteilung der Container jedes Schiffs auf die Blöcke, für die ganze Woche, vor der Anlieferung. Ein **Lagerplatz** je Block begrenzt den Bestand (aus der Lagerfüllung im Spitzenbestand).
Bei einer **Verspätung** verschiebt sich das Beladefenster jedes Schiffs um gerundet N(0, σ²) Stunden, die Anlieferung bleibt; "Wartezeit bei Verspätung" ist das Mittel über 30 solche Szenarien (für alle Verfahren
dieselben).

**Sechs Verfahren**, alle auf derselben Woche:

- **🏗️ Bündeln:** alle Container eines Schiffs in den nächsten Block (bei vollem Lager in den nächsten). Der kürzeste Weg, aber ein Schiff ruft mehr ab, als ein Block liefert: die Wartezeit steigt auf hundert Minuten und mehr.
- **⚖️ Verteilen:** gleichmäßig auf alle Blöcke. Keine Wartezeit, aber der weiteste Weg.
- **🎚️ Kranrate passend:** die Alltagsregel und Referenz aller Deltas: so viele nächste Blöcke, wie die Abrufrate des Schiffs durch die Blockrate verlangt, reihum, volle Blöcke übergangen.
- **🧮 Gierig:** Schiff für Schiff nach Fensterbeginn, je 10 Container in den nächsten Block, dessen Spitzenauslastung unter 80 % bleibt.
- **🎯 Gerechnet:** ein lineares Programm über die ganze Woche: minimale Wartezeit für pünktliche Schiffe, bei Gleichstand der kürzeste Weg. Es sieht alle Schiffe zugleich; das Optimum ist bewiesen.
- **🛡️ Gerechnet und abgesichert:** dasselbe mit zehn Verspätungsszenarien; minimiert Fahrweg plus Preis λ mal mittlere Wartezeit über die Szenarien. Der Preis λ (Meter je Minute) ist Sache des Betreibers.

**Warum Bündeln nicht geht.** Die Rate des Schiffs übersteigt die des Blocks: ein Schiff mit 90 Moves/h braucht mehr als zwei Blöcke à 40 Moves/h. **Warum Verteilen zu viel kostet:** es nutzt alle Blöcke, auch
die fernen. **Warum der Rechenplan beides trifft:** er sieht alle Schiffe zugleich und nimmt den kürzesten Weg, der noch keine Wartezeit erzeugt. **Warum er zerbrechlich ist:** in den Überlappungen der
Beladefenster füllt er die Blöcke bis an die Grenze; verschieben sich die Fenster, staut es sich. **Was die Absicherung tut:** sie plant gegen Szenarien der Verspätung und lässt Luft in den Überlappungen,
das kostet Fahrweg (der Preis in Metern).

**Was passiert ohne Anlieferlast?** Ohne die Anlieferung in den Tagen vor der Beladung (die Container erscheinen erst mit dem Fenster) trifft die einfache Regel "nächster Block mit Luft" den Rechenplan in
30 von 30 Wochen bitgleich: dann gäbe es nichts zu rechnen. Mit der Anlieferlast (Annahme, fest 36 Stunden) trifft sie ihn in 0 von 30 Wochen (Weg im Mittel 23 % länger, Wartezeit 35 gegen 0,3 min): die Anlieferung
belegt die Blockkräne schon vor der Beladung, und die schiffsweise Regel sieht die späteren Schiffe nicht. **Die Aussage "die Regel liegt weit über dem Rechenplan" gilt nur unter dieser Annahme.**

**Stichprobe, Verteilung und Urteil.** Die Stichprobe rechnet 20 andere Wochen (Seeds ab 3000, nicht Ihr Seed) mit Ihren Einstellungen und zeigt Median und 10. bis 90. Perzentil je Verfahren, weil die Kennzahlen
schief sind. Ein Unterschied gilt als klar, wenn er mehr als zwei Standardfehler der gepaarten Differenz beträgt.

**Grenzen dieses Modells** (bewusst so gewählt, damit die Aussage ehrlich bleibt):

- **Flüssigkeitsmodell:** gleichmäßiger Abruf, Blöcke arbeiten unabhängig; ein Rückstand bremst den Schiffskran nicht zurück (das ist eine **Untergrenze** der echten Kopplung von Kran und Block).
- **Suchaufwand und Umstapeln im Block sind nicht modelliert:** der Bündelungsvorteil ist hier allein der Fahrweg (im Modell höchstens etwa 13 % zwischen den Rändern).
- Fahrweg einfach, ohne Stau (der Fahrzeugbedarf folgt daraus, ist aber nicht gerechnet: siehe die Fahrzeugflotte-Demo); alle Blöcke gleich; Container austauschbar (keine Typen, Gewichte, Kühl- oder Gefahrgutcontainer).
- Die Anlieferung (36 Stunden, gleichmäßig) ist eine **Annahme**, kein Echtdatum; die Kaiplatzplanung ist gegeben; Verspätung ist nur eine Verschiebung des Fensters, keine Dehnung; der Plan wird vor der Anlieferung fest gewählt.
- Der abgesicherte Plan ist eine **Schätzung** aus zehn Planungsszenarien: ist σ falsch geschätzt, sinkt der Nutzen (Plan für σ = 3 h, getestet bei σ = 5 h: 15 statt 7,5 min Wartezeit, Messreihe).
- Der LP-Plan wird auf ganze Container gerundet (Verfahren der größten Reste); der LP-Wert bleibt als Schranke sichtbar, der Rundungsverlust liegt im Zielwert im Mittel bei 0,8 %, höchstens bei 3 % (Messreihe).
- Alle Zahlen sind **Größenordnungen aus einer Simulation, keine Messung an einem echten Terminal**; die Rechnung selbst ist gegen eine unabhängige Nachrechnung und gegen vollständiges Durchprobieren geprüft.
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Mengen und Größen.** Schiffe $s$, Blöcke $b$, Stunden $t$. Schiff $s$ hat $n_s$ Container, Fahrweg $d_{sb} = 200 + |\text{Liegeplatz}_s - y_b|$ (m), Abruf-Anteil $a_{s,t} = 1/L_s$ im Fenster
$[e_s, e_s + L_s)$, Anlieferanteil $c_{s,t} = 1/36$ in den 36 Stunden davor und Lastanteil $f_{s,t} = a_{s,t} + c_{s,t}$. Blockrate $\mu$, Lagergrenze $K$, Bestandsanteil $g_{s,t}$ (angeliefert minus abgerufen).

**Entscheidung.** $x_{sb} \ge 0$ mit $\sum_b x_{sb} = n_s$: Container von Schiff $s$ in Block $b$.

**Rückstand.** Für jedes Szenario $k$ (Verschiebung der Fenster, $f^k$) und jeden Block: $q^k_{b,t} = \max\bigl(0,\ q^k_{b,t-1} + \sum_s f^k_{s,t}\, x_{sb} - \mu\bigr)$. Wartezeit
$W^k = \frac{60}{N} \sum_{b,t} q^k_{b,t}$ Minuten je Container ($N = \sum_s n_s$), Fahrweg $D = \frac{1}{N} \sum_{s,b} d_{sb}\, x_{sb}$. Lagergrenze: $\sum_s g_{s,t}\, x_{sb} \le K$ für alle $b, t$.

**Lineares Programm.** Ersetzt man die Rekursion durch $q^k_{b,t} \ge q^k_{b,t-1} + \sum_s f^k_{s,t}\, x_{sb} - \mu$, $q \ge 0$, und minimiert eine Zielfunktion, die $q$ bestraft, so nimmt $q$ am Optimum das Maximum
der Rekursion an (Konvexität): der Zielwert des LP ist die Wartezeit der Simulation (Test: Abweichung unter $10^{-9}$).

- **Gerechnet:** ein Szenario (pünktlich), Ziel $\min\ W + 10^{-6} D$ (die Wartezeit zuerst, bei Gleichstand der Weg: der Zielwert ist eindeutig).
- **Gerechnet und abgesichert:** zehn Planungsszenarien, Ziel $\min\ D + \lambda \cdot \frac{1}{10} \sum_k W^k$ mit dem Preis $\lambda$ in m je min.
- **Kante:** $\min\ D$ unter $W \le \varepsilon$ (pünktlich).

**Rundung.** Je Schiff auf ganze Container nach dem Verfahren der größten Reste (Gleichstand: kleinerer Index); die Summe bleibt $n_s$. Der LP-Wert ist eine Untergrenze des ganzzahligen Optimums.

**Regeln.** Bündeln, Kranrate passend ($k_s = \lceil (n_s / L_s) / \mu \rceil$ nächste Blöcke reihum) und Gierig arbeiten Schiff für Schiff in Portionen zu 10 Containern; sie prüfen den Lagerplatz.

**Vergleich über Wochen.** Für Verfahren $A$ gegen Referenz $B$ auf denselben Wochen $w = 1, \dots, 20$ ist $\Delta_w = X_A^{(w)} - X_B^{(w)}$ die Differenz einer Kennzahl $X$ (negativ = besser); berichtet werden Mittel,
Median und Anteile der Wochen mit $\Delta_w < 0$, $= 0$, $> 0$. Ein Unterschied gilt als klar, wenn $|\bar\Delta| > 2\,\mathrm{SE}(\Delta)$.

Implementiert in `blz_scenario.py` (Woche, Szenarien), `blz_rules.py` (Regeln), `blz_queue.py` (Rückstand, Kennzahlen), `blz_lp.py` (LP mit OR-Tools GLOP, Rundung) und `blz_evaluation.py` (Verfahren, Kurve, Kante, Stichprobe, Urteil).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
