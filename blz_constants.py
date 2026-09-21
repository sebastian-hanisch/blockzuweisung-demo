"""Konstanten der Blockzuweisungs-Demo.

Erzeugung der Woche, Regeln, LP und Bewertung sind die der Messreihe (hafen-planung/messreihe_blockzuweisung: blz.py, common.py), damit deren Zahlen mit diesem Code reproduzierbar sind."""

# --- Fachliche Festwerte (keine Regler; im Text genannt) ---------------------------------------------
PITCH = 100.0                        # Abstand der Blöcke am Kai (m)
D0 = 200.0                           # Grundfahrweg vom Block zum Kai (m)
BERTHS = 3                           # Liegeplätze in gleichem Abstand
N_LO, N_HI = 700, 1300               # Exportcontainer je Schiff
ARRIVAL_SPAN = 30                    # Schiffe kommen innerhalb der ersten 30 Stunden der Woche an
DELIVERY_HOURS = 36                  # Anlieferzeit: die Container kommen gleichmäßig in den 36 h vor dem Beladefenster (Annahme, fest; siehe Befund "ohne Anlieferlast")
TIME_PAD = 22                        # Stunden Luft hinter dem letzten Beladefenster (12 + 10): Rückstände laufen aus
MIN_WINDOW = 3                       # kürzestes Beladefenster (h)
LOT = 10                             # Portion der Regeln (Container)
CAP_HEADROOM = 0.8                   # Regel "Gierig": höchstens 80 % Spitzenauslastung im Fenster
LP_SCALE = 100.0                     # Variablen des LP in Einheiten zu 100 Containern (in der Messreihe meldete GLOP ohne Skalierung mit Lagerzeilen fälschlich INFEASIBLE; OR-Tools 9.15 tut es nicht mehr)
WAIT_TIEBREAK = 1e-6                 # zweitrangiges Gewicht (lexikographisch): bei "Gerechnet" der Weg, bei anderen Zielen die Wartezeit
STOCK_EPS = 1e-9                     # Rechentoleranz der Lagerprüfung

# --- Szenarien ---------------------------------------------------------------------------------------
N_TRAIN, N_TEST = 10, 30             # Planungsszenarien (Szenario-LP) und Testszenarien (Bewertung), Seeds getrennt
TRAIN_BASE, TEST_BASE = 500000, 0

# --- Regler ------------------------------------------------------------------------------------------
SHIPS_RANGE, SHIPS_DEFAULT = (3, 8), 6
BLOCKS_RANGE, BLOCKS_DEFAULT = (6, 10), 8
RATE_RANGE, RATE_DEFAULT, RATE_STEP = (30, 60), 40, 10
CRANE_RANGE, CRANE_DEFAULT, CRANE_STEP = (60, 120), 90, 30
FILL_RANGE, FILL_DEFAULT, FILL_STEP = (50, 90), 70, 5
SIGMA_RANGE, SIGMA_DEFAULT = (0, 6), 3
LAM_CHOICES, LAM_DEFAULT = (2, 5, 10, 20, 50), 10
SEED_RANGE, SEED_DEFAULT = (0, 9999), 2017

# --- Verfahren ---------------------------------------------------------------------------------------
M_BUNDLE, M_SPREAD, M_KBLOCKS, M_GREEDY, M_LP, M_HEDGE = "buendeln", "verteilen", "kranrate", "gierig", "gerechnet", "abgesichert"
METHOD_KEYS = (M_BUNDLE, M_SPREAD, M_KBLOCKS, M_GREEDY, M_LP, M_HEDGE)
METHOD_LABELS = {M_BUNDLE: "🏗️ Bündeln", M_SPREAD: "⚖️ Verteilen", M_KBLOCKS: "🎚️ Kranrate passend", M_GREEDY: "🧮 Gierig", M_LP: "🎯 Gerechnet",
                 M_HEDGE: "🛡️ Gerechnet und abgesichert"}
METHOD_SHORT = {M_BUNDLE: "Bündeln", M_SPREAD: "Verteilen", M_KBLOCKS: "Kranrate passend", M_GREEDY: "Gierig", M_LP: "Gerechnet", M_HEDGE: "Abgesichert"}
BASELINE = M_KBLOCKS                 # Referenz aller Deltas: so wird von Hand geplant, wenn man die Kranrate kennt
VIEW_DEFAULT = M_HEDGE

METHOD_DESCRIPTIONS = {
    M_BUNDLE: "Alle Container eines Schiffs in den nächsten Block; ist er nach Lagerplatz voll, in den nächsten (in Portionen zu 10). Der Rand \"kürzester Weg\": ein Schiff ruft mehr ab, als ein Block "
              "liefert, der Block wird zum Nadelöhr.",
    M_SPREAD: "Gleichmäßig auf alle Blöcke. Der Rand \"keine Wartezeit\", aber der weiteste Weg: die Referenz für die Absicherung.",
    M_KBLOCKS: "Die Alltagsregel: so viele nächste Blöcke, wie die Abrufrate des Schiffs (durch die Blockrate, aufgerundet) verlangt, reihum in Portionen zu 10; volle Blöcke werden übergangen. "
               "Referenz aller Deltas.",
    M_GREEDY: "Schiff für Schiff nach Beginn des Fensters, je 10 Container in den nächsten Block, dessen Spitzenauslastung im Fenster unter 80 % bleibt (sonst der mit der kleinsten). "
              "Die schiffsweise Regel mit Reserve: sie sieht die späteren Schiffe nicht.",
    M_LP: "Lineares Programm über die ganze Woche: minimale Wartezeit für pünktliche Schiffe, bei Gleichstand der kürzeste Weg. Exakt, das Optimum ist bewiesen. Zeigt die Kante, aber der Plan ist zerbrechlich.",
    M_HEDGE: "Lineares Programm mit 10 Verspätungsszenarien: minimiere Fahrweg plus Preis λ mal mittlere Wartezeit über die Szenarien. Exakt (Optimum des Szenario-Modells). Der Preis der Absicherung in Metern.",
}

# --- Auswertung --------------------------------------------------------------------------------------
SAMPLE_WEEKS, SAMPLE_BASE = 20, 3000     # Stichprobe: 20 Wochen ab Seed 3000 (bewusst nicht der eingestellte Seed), alle Verfahren, Bewertung an 30 Szenarien
LAM_CURVE = (1, 2, 5, 10, 20, 50, 100)  # Punkte der Kurve "Preis der Absicherung"
EPS_EDGE = (400, 200, 100, 50, 20, 10, 5, 2, 1)   # erlaubte Wartezeit (min) der Kante
VERDICT_Z = 2.0                      # klar ab mehr als VERDICT_Z Standardfehlern der gepaarten Differenz
PCT_LO, PCT_HI = 0.10, 0.90          # Perzentile der Verteilung (Rang ohne Interpolation)

# --- Diagnose (Schwellen der bedingten Meldung) -------------------------------------------------------
CALM_WAIT = 2.0                      # Kranrate passend pünktlich UND Gerechnet bei Verspätung unter 2 min: nichts zu sichern
OVERLOAD_WAIT = 3.0                  # auch der beste pünktliche Plan wartet 3 min oder mehr: die Blöcke sind zu knapp (Starke Kräne, Seed 2017: 1,8 min)
FRAGILE_RATIO = 5.0                  # bei Verspätung mindestens das Fünffache der pünktlichen Wartezeit (mindestens 1 min als Grundlage)
HEDGE_FACTOR = 0.6                   # die Absicherung senkt die Wartezeit bei Verspätung auf höchstens 60 % (Starke Kräne, Seed 2017: 37,4 auf 19,8 min = 53 %)
STOCK_TOLERANCE = 1.5                # Container über der Lagergrenze, ab denen sie als verletzt gilt (Rundung des LP-Plans kann 1 Container ausmachen)

# --- Darstellung --------------------------------------------------------------------------------------
METHOD_COLORS = {M_BUNDLE: "#c77700", M_SPREAD: "#8a94a3", M_KBLOCKS: "#2a6fb0", M_GREEDY: "#7b5ea7", M_LP: "#c0392b", M_HEDGE: "#2e7d4f"}
MARKER_LINE_COLOR = "#808895"
OUTCOME_COLORS = {"better": "#2e7d4f", "equal": "#8a94a3", "worse": "#c0392b"}
CHART_HEIGHT = 380

# --- Presets (gemeinsamer Seed 2017, siehe tools/PRESET_SWEEP.md) --------------------------------------
_BASE = dict(ships=6, blocks=8, mu=40, crane=90, fill=70, sigma=3, lam=10, seed=SEED_DEFAULT)
PRESETS = {
    "Stoßwoche": dict(_BASE),
    "Späte Schiffe": dict(_BASE, sigma=5),
    "Voller Platz": dict(_BASE, fill=90),
    "Starke Kräne": dict(_BASE, ships=5, crane=120),
    "Ruhige Woche": dict(_BASE, ships=4, mu=60, crane=60, fill=60, sigma=1),
}
