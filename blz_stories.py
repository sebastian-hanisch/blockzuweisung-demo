"""Abnahmekriterien der Presets: Welche Geschichte erzählt jedes Beispielszenario, und woran erkennt man, dass sie trägt?

Einzige Quelle für `tools/tune_presets.py` (Abstimmung) und `tests/test_preset_stories.py` (Abnahme). Jedes Kriterium ist eine Aussage über ein Tupel von `WeekRow`s (blz_evaluation): über viele Wochen die
Aussage im MEDIAN (`criteria`), über die EINE Woche des Presets dieselbe Aussage an dieser Woche (`holds`, der Median einer Woche ist sie selbst). So wird dieselbe Geschichte an der Grundgesamtheit UND an
der gezeigten Woche geprüft: das Preset soll typisch sein, nicht der schönste Einzelfall. Die Kennzahlen sind schief (Wartezeit: Median 21 min, Mittel 31 min bei Kranrate passend), deshalb der Median.
Schwellen ganzzahlig und mit Abstand zum gemessenen Wert (tools/PRESET_SWEEP.md). Deterministisch, kein Zeitlimit: die Kriterien prüfen Kennzahlen, nie die Aufteilung des LP (bei mehreren gleichwertigen
Plänen lösungsabhängig). Ein Kriterium ist "nicht erfüllt", wenn es sich nicht auswerten lässt."""

import statistics

import blz_constants as C
import blz_evaluation as E

BUNDLE, SPREAD, KBLOCKS, GREEDY, LP, HEDGE = C.METHOD_KEYS

# Kennzahlen, an denen "typisch" gemessen wird: (Verfahren, Feld); gemeinsam für alle Presets
TYPICAL = ((LP, "distance"), (HEDGE, "distance"), (KBLOCKS, "wait"), (LP, "wait_shift"), (HEDGE, "wait_shift"), (GREEDY, "distance"))


def _share(rows, key, field="stock_over"):
    """Anteil der Wochen, in denen das Verfahren die Lagergrenze verletzt."""
    return sum(1 for r in rows if getattr(r.m[key], field) > C.STOCK_TOLERANCE) / len(rows)


def _ratio(rows, num, den, field):
    """Median des Zählers durch Median des Nenners; None, wenn der Nenner 0 ist."""
    d = E.median_of(rows, den, field)
    return E.median_of(rows, num, field) / d if d > 0 else None


def criteria(name, rows):
    """Kriterien über ein Tupel von Wochen (Median). Rückgabe: Liste (erfüllt, Text)."""
    med = E.median_of
    kb_w, lp_w, lp_r, hd_r = med(rows, KBLOCKS, "wait"), med(rows, LP, "wait"), med(rows, LP, "wait_shift"), med(rows, HEDGE, "wait_shift")
    extra = E.median_diff(rows, HEDGE, LP, "distance")
    saving = -E.median_diff(rows, LP, KBLOCKS, "distance")
    if name == "Stoßwoche":
        ratio = _ratio(rows, LP, HEDGE, "wait_shift")
        return [(kb_w >= 10.0, f"Kranrate passend, Wartezeit pünktlich >= 10 min: {kb_w:.1f}"),
                (lp_w <= 2.0, f"Gerechnet, Wartezeit pünktlich <= 2 min: {lp_w:.2f}"),
                (lp_r >= 25.0, f"Gerechnet, Wartezeit bei Verspätung >= 25 min: {lp_r:.1f}"),
                (hd_r <= 15.0, f"abgesichert, Wartezeit bei Verspätung <= 15 min: {hd_r:.1f}"),
                (ratio is not None and ratio >= 3.0, f"Gerechnet / abgesichert bei Verspätung >= 3: {'-' if ratio is None else format(ratio, '.1f')}"),
                (extra >= 25.0, f"Mehrweg der Absicherung >= 25 m: {extra:.1f}"),
                (extra <= 60.0, f"Mehrweg der Absicherung <= 60 m: {extra:.1f}")]
    if name == "Späte Schiffe":
        return [(lp_r >= 50.0, f"Gerechnet, Wartezeit bei Verspätung >= 50 min: {lp_r:.1f}"),
                (hd_r <= 25.0, f"abgesichert, Wartezeit bei Verspätung <= 25 min: {hd_r:.1f}"),
                (extra >= 45.0, f"Mehrweg der Absicherung >= 45 m: {extra:.1f}")]
    if name == "Voller Platz":
        over_b, over_lp = med(rows, BUNDLE, "stock_over"), med(rows, LP, "stock_over")
        return [(over_b >= 50.0, f"Bündeln, Container über der Grenze >= 50: {over_b:.1f}"),
                (over_lp <= 1.0, f"Gerechnet, Container über der Grenze <= 1 (Rundung): {over_lp:.1f}"),
                (_share(rows, LP) <= 0.05 and _share(rows, HEDGE) <= 0.05, "Rechenpläne verletzen die Lagergrenze in höchstens 5 % der Wochen"),
                (_share(rows, BUNDLE) >= 0.9, f"Bündeln verletzt die Lagergrenze in mindestens 90 % der Wochen: {_share(rows, BUNDLE) * 100:.0f} %"),
                (lp_w <= 2.0, f"Gerechnet, Wartezeit pünktlich <= 2 min: {lp_w:.2f}"),
                (hd_r <= 15.0, f"abgesichert, Wartezeit bei Verspätung <= 15 min: {hd_r:.1f}")]
    if name == "Starke Kräne":
        return [(kb_w >= 25.0, f"Kranrate passend, Wartezeit pünktlich >= 25 min: {kb_w:.1f}"),
                (lp_r >= 15.0, f"Gerechnet, Wartezeit bei Verspätung >= 15 min: {lp_r:.1f}"),
                (hd_r <= 25.0, f"abgesichert, Wartezeit bei Verspätung <= 25 min: {hd_r:.1f}")]
    if name == "Ruhige Woche":
        return [(kb_w <= 1.0, f"Kranrate passend, Wartezeit pünktlich <= 1 min: {kb_w:.2f}"),
                (lp_r <= 1.0, f"Gerechnet, Wartezeit bei Verspätung <= 1 min: {lp_r:.2f}"),
                (saving >= 3.0, f"Weg-Ersparnis des Rechenplans gegen Kranrate passend >= 3 m: {saving:.1f}"),
                (saving <= 15.0, f"Weg-Ersparnis des Rechenplans gegen Kranrate passend <= 15 m: {saving:.1f}"),
                (extra <= 1.0, f"Mehrweg der Absicherung <= 1 m: {extra:.2f}")]
    raise KeyError(name)


def holds(name, row):
    """Gilt die Geschichte an der EINEN Woche (`WeekRow`), die das Preset zeigt?"""
    return all(ok for ok, _ in criteria(name, (row,)))


def key_values(rows):
    """Die Kennzahlen aus TYPICAL als {(Verfahren, Feld): Median}."""
    return {(k, f): statistics.median(E.values(rows, k, f)) for k, f in TYPICAL}
