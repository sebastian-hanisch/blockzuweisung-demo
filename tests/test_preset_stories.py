"""Abnahme der Presets an ECHTEN Daten: jede Geschichte trägt im Median über 40 Wochen (Seeds 1000-1039; die Abstimmung in tools/PRESET_SWEEP.md nutzt 100) UND an der einen Woche, die das Preset zeigt
(Seed 2017); die gezeigte Woche ist typisch, nicht der schönste Einzelfall. Ohne Zeitlimit; geprüft werden Kennzahlen mit Abstand zur Schwelle, nie die Aufteilung des LP."""

import concurrent.futures
import os

import pytest

import blz_constants as C
import blz_evaluation as E
import blz_stories as ST

POPULATION = range(1000, 1040)
NAMES = list(C.PRESETS)


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["ships"], p["blocks"], p["mu"], p["crane"], p["fill"], p["sigma"], p["lam"])


@pytest.fixture(scope="module")
def populations():
    """{Preset: Tupel von WeekRow}: 5 Presets x 40 Wochen, parallel gerechnet (E.week_row ist eine Funktion der Modulebene und lässt sich in Prozessen aufrufen)."""
    jobs = [(name, seed) for name in NAMES for seed in POPULATION]
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        rows = list(pool.map(E.week_row, [params(n) for n, _ in jobs], [s for _, s in jobs], chunksize=4))
    out = {n: [] for n in NAMES}
    for (n, _), r in zip(jobs, rows):
        out[n].append(r)
    return {n: tuple(v) for n, v in out.items()}


@pytest.fixture(scope="module")
def shown():
    return {n: E.week_row(params(n), C.PRESETS[n]["seed"]) for n in NAMES}


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_in_the_median_over_the_population(name, populations):
    for ok, text in ST.criteria(name, populations[name]):
        assert ok, f"{name}: {text}"


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_at_the_week_the_preset_shows(name, shown):
    assert ST.holds(name, shown[name]), [t for ok, t in ST.criteria(name, (shown[name],)) if not ok]


def test_all_presets_share_seed_2017_which_lies_outside_the_populations():
    assert {p["seed"] for p in C.PRESETS.values()} == {2017} and 2017 not in range(1000, 1100) and 2017 not in range(3000, 3020)


@pytest.mark.parametrize("name", NAMES)
def test_the_shown_week_is_typical_for_every_key_measure(name, populations, shown):
    """Jede Kennzahl aus ST.TYPICAL der gezeigten Woche liegt zwischen dem 5. und 95. Perzentil der Grundgesamtheit (40 Wochen; die Abstimmung mit 100 Wochen nennt den 10. bis 90.)."""
    for key, field in ST.TYPICAL:
        vals = sorted(E.values(populations[name], key, field))
        lo, hi = vals[int(0.05 * len(vals))], vals[int(0.95 * len(vals)) - 1]
        assert lo <= getattr(shown[name].m[key], field) <= hi, (name, key, field, getattr(shown[name].m[key], field), (lo, hi))


def test_the_population_reproduces_the_measured_medians_of_the_tuning(populations):
    """Stoßwoche: Kranrate passend pünktlich im Median etwa 21 min, Gerechnet bei Verspätung etwa 42 min, abgesichert etwa 8 min, Mehrweg etwa 42 m (PRESET_SWEEP.md, 100 Wochen); hier 40 Wochen mit Abstand."""
    rows = populations["Stoßwoche"]
    assert 14 < E.median_of(rows, C.M_KBLOCKS, "wait") < 32 and 32 < E.median_of(rows, C.M_LP, "wait_shift") < 55 and 5 < E.median_of(rows, C.M_HEDGE, "wait_shift") < 12
    assert 34 < E.median_diff(rows, C.M_HEDGE, C.M_LP, "distance") < 52
    late = populations["Späte Schiffe"]
    assert E.median_diff(late, C.M_HEDGE, C.M_LP, "distance") > E.median_diff(rows, C.M_HEDGE, C.M_LP, "distance") + 10                # größere Verspätung: die Absicherung kostet mehr


def test_the_storage_story_of_voller_platz_counts(populations):
    """Bündeln überschreitet die Lagergrenze in (fast) allen Wochen, Verteilen und die Rechenpläne nie (PRESET_SWEEP.md: 100 von 100 / 0 / 0)."""
    rows = populations["Voller Platz"]

    def share(key):
        return sum(1 for r in rows if r.m[key].stock_over > 1.5) / len(rows)

    assert share(C.M_BUNDLE) >= 0.95 and share(C.M_KBLOCKS) > 0.3 and share(C.M_GREEDY) > 0.2 and share(C.M_SPREAD) == 0 and share(C.M_LP) == 0 and share(C.M_HEDGE) == 0


def test_in_the_calm_week_the_rules_agree_and_hedging_is_free(populations):
    rows = populations["Ruhige Woche"]
    assert abs(E.median_diff(rows, C.M_GREEDY, C.M_KBLOCKS, "distance")) < 1e-9 and abs(E.median_diff(rows, C.M_BUNDLE, C.M_KBLOCKS, "distance")) < 1e-9
    assert abs(E.median_diff(rows, C.M_HEDGE, C.M_LP, "distance")) < 0.5 and E.median_of(rows, C.M_SPREAD, "distance") > 400
