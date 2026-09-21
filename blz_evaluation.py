"""Auswertung: eine Woche mit allen sechs Verfahren, Kurve "Preis der Absicherung", Kante, Stichprobe, gepaarte Differenz, Verteilung, Urteil und Diagnose.

Reine Rechnung ohne Streamlit. Kosten sind der Fahrweg (m) und die Wartezeit am Block (min); sie werden nicht zu einer Zahl vermischt (der Preis λ wählt nur den Punkt auf der Kurve). Alle Vergleiche
sind gepaart (dieselben Wochen, dieselben Testszenarien); Unterschied = Verfahren minus Referenz, negativ = besser (weniger Wartezeit, kürzerer Weg)."""

import math
import statistics
from dataclasses import dataclass
from typing import NamedTuple

import blz_constants as C
import blz_lp as L
import blz_queue as Q
import blz_rules as R
import blz_scenario as S

BUNDLE, SPREAD, KBLOCKS, GREEDY, LP, HEDGE = C.METHOD_KEYS


class Params(NamedTuple):
    """Alle Einstellungen, die eine Woche und ihre Bewertung bestimmen (ohne Seed)."""
    ships: int
    blocks: int
    mu: int
    crane: int
    fill: int
    sigma: int
    lam: int


def signed(value, digits=0):
    """Zahl mit Vorzeichen; ein Wert, der auf 0 rundet, erscheint als +0 statt als -0 (sonst zeigt eine Änderung um -0,4 m "-0 m")."""
    v = round(value, digits)
    if v == 0:
        v = 0.0
    return f"{v:+.{digits}f}"


def make_week(p, seed):
    return S.make_week(seed, p.ships, p.blocks, float(p.mu), p.crane, p.fill)


def training_loads(week, sigma):
    """Lastanteile der Planungsszenarien (Verschiebungen mit anderen Seeds als die Testszenarien)."""
    return [S.shifted(week, dl).lf for dl in S.train_scenarios(week, sigma)]


# ---------------------------------------------------------------------------------------------------
# Eine Woche, alle Verfahren
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True, eq=False)
class Bound:
    """Der LP-Wert eines Rechenverfahrens (Schranke) und derselbe Wert für den auf ganze Container gerundeten Plan."""
    lp_distance: float       # Weg des LP-Plans (m)
    lp_wait: float           # mittlere Wartezeit des LP-Plans über die Szenarien (min)
    objective: float         # Zielwert des LP (Gerechnet: Wartezeit in min; Abgesichert: Weg + Preis mal Wartezeit in m)
    rounded: float           # derselbe Zielwert für den gerundeten Plan (an denselben Szenarien)

    @property
    def gap(self):
        """Aufschlag der Rundung gegen den LP-Wert in Prozent; None, wenn der LP-Wert 0 ist."""
        return 100.0 * (self.rounded / self.objective - 1.0) if self.objective > 1e-9 else None


@dataclass(frozen=True, eq=False)
class Outcome:
    key: str
    label: str
    x: tuple                 # Plan: Container je Schiff und Block
    m: Q.Metrics             # pünktliche Woche
    robust: Q.Robust         # bei Verspätung (Testszenarien)
    bound: object            # Bound oder None (nur die Rechenverfahren)


@dataclass(frozen=True, eq=False)
class WeekResult:
    params: Params
    seed: int
    week: object
    outcomes: tuple          # in der Reihenfolge C.METHOD_KEYS

    def __getitem__(self, key):
        return next(o for o in self.outcomes if o.key == key)


def _freeze(x):
    return tuple(tuple(int(v) for v in row) for row in x)


def _outcome(key, week, x, test, bound=None):
    x = _freeze(x)
    return Outcome(key, C.METHOD_LABELS[key], x, Q.evaluate(week, x), Q.robust_eval(week, x, test), bound)


def hedged_plan(p, week, lam, train_loads=None):
    """(Plan, Bound) des abgesicherten Rechenplans mit Preis lam (m je min); Bound für den gerundeten Plan an denselben Planungsszenarien."""
    loads = train_loads if train_loads is not None else training_loads(week, p.sigma)
    x, res = L.plan_hedged(week, lam, loads)
    train = S.train_scenarios(week, p.sigma)
    wait_r = Q.robust_eval(week, x, train).wait
    m = Q.evaluate(week, x)
    return x, Bound(res.distance, res.wait, res.distance + lam * res.wait, m.distance + lam * wait_r)


def run_week(p, seed):
    """Die Woche des Seeds mit allen sechs Verfahren (Reihenfolge C.METHOD_KEYS), bewertet pünktlich und an den 30 Testszenarien."""
    week = make_week(p, seed)
    test = S.evaluation_scenarios(week, p.sigma)
    loads = training_loads(week, p.sigma)
    x_lp, res_lp = L.plan_exact(week)
    m_lp = Q.evaluate(week, x_lp)
    b_lp = Bound(res_lp.distance, res_lp.wait, res_lp.wait, m_lp.wait)
    x_h, b_h = hedged_plan(p, week, p.lam, loads)
    plans = ((BUNDLE, R.rule_bundle(week), None), (SPREAD, R.rule_spread(week), None), (KBLOCKS, R.rule_kblocks(week), None), (GREEDY, R.rule_greedy(week), None), (LP, x_lp, b_lp), (HEDGE, x_h, b_h))
    return WeekResult(p, seed, week, tuple(_outcome(key, week, x, test, bound) for key, x, bound in plans))


# ---------------------------------------------------------------------------------------------------
# Kurve "Preis der Absicherung" und Kante
# ---------------------------------------------------------------------------------------------------
class CurvePoint(NamedTuple):
    lam: float
    distance: float          # Weg des gerundeten Plans (m)
    wait: float              # Wartezeit pünktlich (min)
    wait_shift: float        # Wartezeit bei Verspätung (min, Testszenarien)


@dataclass(frozen=True, eq=False)
class Curve:
    points: tuple            # CurvePoint je Preis lam aus C.LAM_CURVE
    edge: tuple              # (erlaubte Wartezeit eps in min, kürzester Weg in m) für pünktliche Schiffe
    min_wait: float          # kleinstmögliche Wartezeit (min) pünktlich
    bundle_distance: float
    spread_distance: float


def price_curve(p, seed, result=None):
    """Sieben Szenario-LP (Preis lam = 1 ... 100) für die Woche und neun LP der Kante (kürzester Weg unter erlaubter Wartezeit, pünktlich). `result`: schon gerechnete Woche (Referenzpunkte)."""
    res = result if result is not None else run_week(p, seed)
    week = res.week
    test = S.evaluation_scenarios(week, p.sigma)
    loads = training_loads(week, p.sigma)
    points = []
    for lam in C.LAM_CURVE:
        x, _ = hedged_plan(p, week, lam, loads)
        m = Q.evaluate(week, x)
        points.append(CurvePoint(lam, m.distance, m.wait, Q.robust_eval(week, x, test).wait))
    min_wait = L.solve(week, min_wait=True).wait
    edge = tuple((eps, L.edge_distance(week, eps, min_wait)) for eps in C.EPS_EDGE)
    return Curve(tuple(points), edge, min_wait, res[BUNDLE].m.distance, res[SPREAD].m.distance)


# ---------------------------------------------------------------------------------------------------
# Stichprobe
# ---------------------------------------------------------------------------------------------------
class Scalars(NamedTuple):
    """Die Kennzahlen eines Verfahrens in einer Woche (ohne Plan und Verlauf: klein genug für viele Wochen)."""
    distance: float          # Fahrweg (m)
    wait: float              # Wartezeit pünktlich (min)
    wait_shift: float        # Wartezeit bei Verspätung (min)
    delay_max: float         # größter Beladeverzug pünktlich (min)
    stock_over: float        # Container über der Lagergrenze
    cost: float              # Weg + Preis mal Wartezeit bei Verspätung (m): Preis und Nutzen in einer Zahl, am eingestellten Preis


@dataclass(frozen=True)
class WeekRow:
    seed: int
    m: dict                  # Verfahren -> Scalars


def row_of(res):
    return WeekRow(res.seed, {o.key: Scalars(o.m.distance, o.m.wait, o.robust.wait, o.m.delay_max, o.m.stock_over, o.m.distance + res.params.lam * o.robust.wait) for o in res.outcomes})


def week_row(p, seed):
    return row_of(run_week(p, seed))


def sample(p, n=C.SAMPLE_WEEKS, base=C.SAMPLE_BASE):
    """n Wochen (Seeds base ... base+n-1, unabhängig vom eingestellten Seed) mit allen Verfahren."""
    return tuple(week_row(p, seed) for seed in range(base, base + n))


def values(rows, key, field="distance"):
    return [getattr(r.m[key], field) for r in rows]


def mean_of(rows, key, field="distance"):
    return statistics.fmean(values(rows, key, field))


def median_of(rows, key, field="distance"):
    return statistics.median(values(rows, key, field))


def percentile(vals, share):
    """Rang ohne Interpolation (wie die Messreihe): sortierte Werte, Stelle int(share * n), höchstens die letzte."""
    v = sorted(vals)
    return v[min(len(v) - 1, int(share * len(v)))]


def spread_of(rows, key, field="distance"):
    """(Median, 10. Perzentil, 90. Perzentil) des Feldes über die Wochen."""
    v = values(rows, key, field)
    return statistics.median(v), percentile(v, C.PCT_LO), percentile(v, C.PCT_HI)


def paired(rows, key, reference, field="distance"):
    """Gepaarte Differenz key minus reference je Woche (negativ = besser)."""
    return [getattr(r.m[key], field) - getattr(r.m[reference], field) for r in rows]


def median_diff(rows, key, reference, field="distance"):
    return statistics.median(paired(rows, key, reference, field))


def _se(d):
    return statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0


@dataclass(frozen=True)
class Distribution:
    key: str
    field: str
    n: int
    better: float
    equal: float
    worse: float
    mean_gain: float         # Gewinn je Woche (positiv = besser als die Referenz)
    median_gain: float


def distribution(rows, key, reference, field="wait_shift", tol=1e-9):
    """Anteil der Wochen, in denen das Verfahren weniger / gleich viel / mehr als die Referenz hat (Unterschiede unter `tol` gelten als gleich)."""
    d = paired(rows, key, reference, field)
    n = len(d)
    better, worse = sum(1 for x in d if x < -tol), sum(1 for x in d if x > tol)
    return Distribution(key, field, n, better / n, (n - better - worse) / n, worse / n, -statistics.fmean(d), -statistics.median(d))


@dataclass(frozen=True)
class Verdict:
    kind: str                # "better" (weniger) | "worse" | "unclear"
    diff: float              # Verfahren minus Referenz je Woche (negativ = besser)
    se: float
    pct: object              # Unterschied in % der Referenz; None, wenn die Referenz im Mittel 0 ist
    n: int
    field: str


def verdict(rows, key, reference, field="wait_shift"):
    """Bewertung gegen die Referenz. "Klar" heißt: Unterschied > VERDICT_Z Standardfehler der gepaarten Differenz (gemittelt über die Wochen); sonst "unclear"."""
    d = paired(rows, key, reference, field)
    diff, se = statistics.fmean(d), _se(d)
    ref = mean_of(rows, reference, field)
    if se == 0:
        kind = "unclear" if diff == 0 else ("better" if diff < 0 else "worse")
    else:
        kind = "unclear" if abs(diff) <= C.VERDICT_Z * se else ("better" if diff < 0 else "worse")
    return Verdict(kind, diff, se, 100.0 * diff / ref if ref else None, len(d), field)


# ---------------------------------------------------------------------------------------------------
# Diagnose (bedingte Meldung)
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Diagnosis:
    kind: str                # "calm" | "sigma0" | "overload" | "fragile" | "hedge" | "robust"
    kb_wait: float           # Kranrate passend, pünktlich (min)
    kb_distance: float       # Kranrate passend, Weg (m)
    lp_wait: float           # Gerechnet, pünktlich (min)
    lp_wait_shift: float     # Gerechnet, bei Verspätung (min)
    hedge_wait_shift: float  # Abgesichert, bei Verspätung (min)
    extra: float             # Mehrweg der Absicherung gegen Gerechnet (m)
    extra_pct: float         # dasselbe in Prozent des Gerechnet-Wegs
    hedge_distance: float
    lp_distance: float
    hedge_wait: float
    stock: tuple             # ((Verfahren, Container über der Grenze), ...) der Verfahren mit verletzter Lagergrenze


def stock_violations(outcomes):
    return tuple((o.key, o.m.stock_over) for o in outcomes if o.m.stock_over > C.STOCK_TOLERANCE)


def diagnose(res):
    """Was zeigt diese Woche: nichts zu sichern (calm), σ = 0 (sigma0), auch der Rechenplan wartet (overload), der wartefreie Plan zerbricht und die Absicherung hilft (hedge) oder nicht genug (fragile),
    oder der pünktliche Plan hält Verspätung aus (robust). Dazu die Verfahren mit verletzter Lagergrenze (unabhängig von der Art)."""
    p = res.params
    kb, lp, hd = res[KBLOCKS], res[LP], res[HEDGE]
    if kb.m.wait < C.CALM_WAIT and lp.robust.wait < C.CALM_WAIT:
        kind = "calm"
    elif p.sigma == 0:
        kind = "sigma0"
    elif lp.m.wait >= C.OVERLOAD_WAIT:
        kind = "overload"
    elif lp.robust.wait >= C.FRAGILE_RATIO * max(lp.m.wait, 1.0):
        kind = "hedge" if hd.robust.wait <= C.HEDGE_FACTOR * lp.robust.wait else "fragile"
    else:
        kind = "robust"
    extra = hd.m.distance - lp.m.distance
    return Diagnosis(kind, kb.m.wait, kb.m.distance, lp.m.wait, lp.robust.wait, hd.robust.wait, extra, 100.0 * extra / lp.m.distance, hd.m.distance, lp.m.distance, hd.m.wait, stock_violations(res.outcomes))


def diagnosis_text(d, p):
    """Die bedingte Meldung als Satz ohne Emoji (die App setzt je nach Art ein Zeichen davor, das PDF nicht)."""
    if d.kind == "calm":
        return (f"Ruhige Woche: die Blöcke kommen mit den Schiffen mit (Kranrate passend wartet {d.kb_wait:.1f} min, der Rechenplan bei Verspätung {d.lp_wait_shift:.1f} min). Alle Regeln außer Verteilen "
                f"sind gleich gut, Rechnen spart nur wenige Meter ({d.lp_distance:.0f} statt {d.kb_distance:.0f} m), Absichern kostet {d.extra:.1f} m. Mehr Schiffe oder eine niedrigere Blockrate machen daraus ein Problem.")
    if d.kind == "sigma0":
        return (f"Keine Verspätung (σ = 0): die zehn Planungsszenarien sind alle die pünktliche Woche. Der abgesicherte Plan wägt dann nur Weg gegen Wartezeit dieser einen Woche ab: "
                f"{d.hedge_distance:.1f} gegen {d.lp_distance:.1f} m Fahrweg und {d.hedge_wait:.2f} gegen {d.lp_wait:.2f} min Wartezeit beim Gerechnet-Plan. Gegen Verspätung sichert er nichts ab.")
    if d.kind == "overload":
        return (f"Die Blöcke sind für diese Woche zu knapp: auch der Rechenplan wartet pünktlich {d.lp_wait:.1f} min (bei Verspätung {d.lp_wait_shift:.1f} min). Absichern hilft dann wenig "
                f"(abgesichert bei Verspätung {d.hedge_wait_shift:.1f} min, {signed(d.extra)} m Fahrweg); mehr Blockrate, mehr Blöcke oder weniger Schiffe schaffen Luft.")
    if d.kind == "fragile":
        return (f"Der wartefreie Plan ist zerbrechlich: pünktlich {d.lp_wait:.1f} min Wartezeit, bei Verspätung {d.lp_wait_shift:.1f} min. Der abgesicherte Plan mit Preis λ = {p.lam} m je min bringt sie "
                f"nur auf {d.hedge_wait_shift:.1f} min ({signed(d.extra)} m Fahrweg): ein höherer Preis sichert stärker.")
    if d.kind == "hedge":
        return (f"Der wartefreie Plan zerbricht: pünktlich {d.lp_wait:.1f} min Wartezeit, bei Verspätung {d.lp_wait_shift:.1f} min. Die Absicherung (Preis λ = {p.lam} m je min) kostet {d.extra:.0f} m Fahrweg "
                f"({signed(d.extra_pct)} %) und senkt die Wartezeit bei Verspätung auf {d.hedge_wait_shift:.1f} min.")
    return (f"Der pünktliche Rechenplan hält die Verspätung aus: {d.lp_wait:.1f} min pünktlich, {d.lp_wait_shift:.1f} min bei Verspätung. Die Absicherung kostet {d.extra:.0f} m Fahrweg und bringt "
            f"nur {d.hedge_wait_shift:.1f} min bei Verspätung.")


def stock_text(d):
    """Meldung zur Lagergrenze; leer, wenn kein Verfahren sie verletzt."""
    if not d.stock:
        return ""
    names = ", ".join(f"{C.METHOD_SHORT[k]} um {v:.0f} Container" for k, v in d.stock)
    kept = "Die Rechenpläne halten sie ein." if not any(k in (LP, HEDGE) for k, _ in d.stock) else "Auch ein Rechenplan überschreitet sie (Rundung auf ganze Container)."
    return f"Lagergrenze verletzt: {names}. {kept}"


def verdict_text(rows, label, key, reference, field, noun, unit):
    """(Art, Satz) des Urteils über die Stichprobe, mit **fett** für die App (das PDF entfernt die Zeichen). `noun`: was verglichen wird (Wartezeit, Zielwert), `unit`: min oder m."""
    v = verdict(rows, key, reference, field)
    d = distribution(rows, key, reference, field)
    if v.kind == "better":
        amount = f"**{abs(v.pct):.0f} % weniger**" if v.pct is not None else f"**{abs(v.diff):.2f} {unit} weniger**"
        return v.kind, f"**{label}**: im Mittel {amount} {noun} ({signed(v.diff, 2)} {unit} je Woche, Standardfehler {v.se:.2f}). In **{d.worse * 100:.0f} %** der Wochen ist es umgekehrt."
    if v.kind == "worse":
        amount = f"**{v.pct:.0f} % mehr**" if v.pct is not None else f"**{v.diff:.2f} {unit} mehr**"
        return v.kind, f"**{label}**: im Mittel {amount} {noun} ({signed(v.diff, 2)} {unit} je Woche, Standardfehler {v.se:.2f}). In **{d.better * 100:.0f} %** der Wochen ist es besser."
    return v.kind, (f"Kein klarer Unterschied bei **{label}**: die Differenz ({signed(v.diff, 2)} {unit} {noun}, gemittelt über die Wochen) liegt innerhalb des Rauschens (Standardfehler {v.se:.2f}). "
                    f"Besser in {d.better * 100:.0f} %, schlechter in {d.worse * 100:.0f} % der Wochen.")


def verdict_specs(lam):
    """Die drei Vergleiche des Kernabschnitts: (Beschriftung, Verfahren, Referenz, Feld, Substantiv, Einheit)."""
    return (("Abgesichert gegen Gerechnet, Wartezeit bei Verspätung", HEDGE, LP, "wait_shift", "Wartezeit", "min"),
            ("Gerechnet gegen Kranrate passend, Wartezeit pünktlich", LP, KBLOCKS, "wait", "Wartezeit", "min"),
            (f"Abgesichert gegen Gierig, Zielwert Weg + {lam} · Wartezeit bei Verspätung", HEDGE, GREEDY, "cost", "Zielwert", "m"))
