"""Tests der Abnahmekriterien mit KÜNSTLICHEN Werten: jedes Kriterium kippt einzeln an seiner Schwelle (die Schwellen stehen hart hier, nicht aus dem Code gelesen); Median über Wochen; Kriterien
verkraften leere Nenner (None)."""

import pytest

import blz_constants as C
import blz_evaluation as E
import blz_stories as ST

BUNDLE, SPREAD, KBLOCKS, GREEDY, LP, HEDGE = "buendeln", "verteilen", "kranrate", "gierig", "gerechnet", "abgesichert"


def make_row(base, seed=0, **over):
    """WeekRow aus einem Grundwert je (Verfahren, Feld) und Überschreibungen `Verfahren__Feld=Wert`."""
    vals = {(k, f): 0.0 for k in C.METHOD_KEYS for f in E.Scalars._fields}
    vals.update(base)
    for name, v in over.items():
        k, f = name.split("__")
        vals[(k, f)] = v
    return E.WeekRow(seed, {k: E.Scalars(*(vals[(k, f)] for f in E.Scalars._fields)) for k in C.METHOD_KEYS})


GOOD = {
    "Stoßwoche": {(KBLOCKS, "wait"): 20.0, (LP, "wait"): 0.1, (LP, "wait_shift"): 50.0, (HEDGE, "wait_shift"): 9.0, (LP, "distance"): 260.0, (HEDGE, "distance"): 300.0},
    "Späte Schiffe": {(LP, "wait_shift"): 70.0, (HEDGE, "wait_shift"): 13.0, (LP, "distance"): 260.0, (HEDGE, "distance"): 320.0},
    "Voller Platz": {(BUNDLE, "stock_over"): 180.0, (LP, "stock_over"): 0.5, (LP, "wait"): 0.0, (HEDGE, "wait_shift"): 9.0},
    "Starke Kräne": {(KBLOCKS, "wait"): 50.0, (LP, "wait_shift"): 30.0, (HEDGE, "wait_shift"): 12.0},
    "Ruhige Woche": {(KBLOCKS, "wait"): 0.0, (LP, "wait_shift"): 0.05, (KBLOCKS, "distance"): 255.0, (LP, "distance"): 247.0, (HEDGE, "distance"): 247.0},
}

# (Preset, Kriterium-Nummer, Überschreibungen die gerade noch erfüllen, Überschreibungen die gerade nicht mehr erfüllen)
EDGES = [
    ("Stoßwoche", 0, dict(kranrate__wait=10.0), dict(kranrate__wait=9.99)),
    ("Stoßwoche", 1, dict(gerechnet__wait=2.0), dict(gerechnet__wait=2.01)),
    ("Stoßwoche", 2, dict(gerechnet__wait_shift=25.0, abgesichert__wait_shift=8.0), dict(gerechnet__wait_shift=24.99, abgesichert__wait_shift=8.0)),
    ("Stoßwoche", 3, dict(abgesichert__wait_shift=15.0, gerechnet__wait_shift=60.0), dict(abgesichert__wait_shift=15.01, gerechnet__wait_shift=60.0)),
    ("Stoßwoche", 4, dict(gerechnet__wait_shift=30.0, abgesichert__wait_shift=10.0), dict(gerechnet__wait_shift=30.0, abgesichert__wait_shift=10.01)),
    ("Stoßwoche", 5, dict(abgesichert__distance=285.0), dict(abgesichert__distance=284.99)),
    ("Stoßwoche", 6, dict(abgesichert__distance=320.0), dict(abgesichert__distance=320.01)),
    ("Späte Schiffe", 0, dict(gerechnet__wait_shift=50.0), dict(gerechnet__wait_shift=49.99)),
    ("Späte Schiffe", 1, dict(abgesichert__wait_shift=25.0), dict(abgesichert__wait_shift=25.01)),
    ("Späte Schiffe", 2, dict(abgesichert__distance=305.0), dict(abgesichert__distance=304.99)),
    ("Voller Platz", 0, dict(buendeln__stock_over=50.0), dict(buendeln__stock_over=49.99)),
    ("Voller Platz", 1, dict(gerechnet__stock_over=1.0), dict(gerechnet__stock_over=1.01)),
    ("Voller Platz", 4, dict(gerechnet__wait=2.0), dict(gerechnet__wait=2.01)),
    ("Voller Platz", 5, dict(abgesichert__wait_shift=15.0), dict(abgesichert__wait_shift=15.01)),
    ("Starke Kräne", 0, dict(kranrate__wait=25.0), dict(kranrate__wait=24.99)),
    ("Starke Kräne", 1, dict(gerechnet__wait_shift=15.0, abgesichert__wait_shift=12.0), dict(gerechnet__wait_shift=14.99, abgesichert__wait_shift=12.0)),
    ("Starke Kräne", 2, dict(abgesichert__wait_shift=25.0), dict(abgesichert__wait_shift=25.01)),
    ("Ruhige Woche", 0, dict(kranrate__wait=1.0), dict(kranrate__wait=1.01)),
    ("Ruhige Woche", 1, dict(gerechnet__wait_shift=1.0), dict(gerechnet__wait_shift=1.01)),
    ("Ruhige Woche", 2, dict(gerechnet__distance=252.0, abgesichert__distance=252.0), dict(gerechnet__distance=252.01, abgesichert__distance=252.01)),
    ("Ruhige Woche", 3, dict(gerechnet__distance=240.0, abgesichert__distance=240.0), dict(gerechnet__distance=239.99, abgesichert__distance=239.99)),
    ("Ruhige Woche", 4, dict(abgesichert__distance=248.0), dict(abgesichert__distance=248.01)),
]


def flags(name, rows):
    return [ok for ok, _ in ST.criteria(name, rows)]


def test_there_is_one_story_for_every_preset_and_every_good_row_carries_it():
    assert set(GOOD) == set(C.PRESETS) and list(C.PRESETS) == ["Stoßwoche", "Späte Schiffe", "Voller Platz", "Starke Kräne", "Ruhige Woche"]
    for name, base in GOOD.items():
        row = make_row(base)
        assert all(flags(name, (row,))) and ST.holds(name, row), name


@pytest.mark.parametrize("name,index,passes,fails", EDGES)
def test_each_criterion_flips_alone_at_its_threshold(name, index, passes, fails):
    ok = flags(name, (make_row(GOOD[name], **passes),))
    bad = flags(name, (make_row(GOOD[name], **fails),))
    assert all(ok), (name, index, ok)
    assert bad[index] is False and sum(1 for v in bad if not v) == 1, (name, index, bad)
    assert ST.holds(name, make_row(GOOD[name], **passes)) and not ST.holds(name, make_row(GOOD[name], **fails))


def test_the_number_of_criteria_per_preset():
    assert {n: len(flags(n, (make_row(g),))) for n, g in GOOD.items()} == {"Stoßwoche": 7, "Späte Schiffe": 3, "Voller Platz": 6, "Starke Kräne": 3, "Ruhige Woche": 5}


def test_over_many_weeks_the_criteria_use_the_median_not_the_mean():
    rows = tuple(make_row(GOOD["Stoßwoche"], seed=i, kranrate__wait=w) for i, w in enumerate([1.0, 10.0, 500.0]))
    assert flags("Stoßwoche", rows)[0] is True                                                        # Median 10 (das Mittel wäre 170)
    rows = tuple(make_row(GOOD["Stoßwoche"], seed=i, kranrate__wait=w) for i, w in enumerate([1.0, 9.0, 500.0]))
    assert flags("Stoßwoche", rows)[0] is False


def test_the_extra_distance_criterion_uses_the_median_of_the_paired_difference():
    rows = tuple(make_row(GOOD["Stoßwoche"], seed=i, abgesichert__distance=d) for i, d in enumerate([270.0, 285.0, 400.0]))          # Mehrweg 10 / 25 / 140 gegen Gerechnet (260)
    f = flags("Stoßwoche", rows)
    assert f[5] is True and f[6] is True
    rows = tuple(make_row(GOOD["Stoßwoche"], seed=i, abgesichert__distance=d) for i, d in enumerate([270.0, 284.0, 400.0]))
    assert flags("Stoßwoche", rows)[5] is False


def test_the_ratio_criterion_survives_an_empty_denominator():
    row = make_row(GOOD["Stoßwoche"], abgesichert__wait_shift=0.0)
    f = flags("Stoßwoche", (row,))
    assert f[4] is False and f[3] is True and ST.holds("Stoßwoche", row) is False
    assert [t for _, t in ST.criteria("Stoßwoche", (row,))][4].endswith(": -")


def test_the_storage_criteria_of_voller_platz_count_weeks():
    def rows(n_bundle_ok, n_lp_bad, n=20):
        return tuple(make_row(GOOD["Voller Platz"], seed=i, buendeln__stock_over=(1.0 if i < n_bundle_ok else 180.0), gerechnet__stock_over=(1.6 if i < n_lp_bad else 0.5)) for i in range(n))
    f = flags("Voller Platz", rows(2, 1))
    assert f[2] is True and f[3] is True                                                                 # Rechenpläne verletzen in 1 von 20 Wochen (5 %): erlaubt; Bündeln in 18 von 20 (90 %): erlaubt
    assert flags("Voller Platz", rows(2, 2))[2] is False and flags("Voller Platz", rows(3, 0))[3] is False and flags("Voller Platz", rows(2, 0))[3] is True


def test_the_hedged_plan_is_included_in_the_storage_share():
    two = tuple(make_row(GOOD["Voller Platz"], seed=i, abgesichert__stock_over=(1.6 if i < 2 else 0.0)) for i in range(20))
    one = tuple(make_row(GOOD["Voller Platz"], seed=i, abgesichert__stock_over=(1.6 if i < 1 else 0.0)) for i in range(20))
    assert flags("Voller Platz", two)[2] is False and flags("Voller Platz", one)[2] is True


def test_a_storage_overshoot_of_exactly_one_and_a_half_containers_is_not_yet_a_violation():
    """Die Rundung des LP-Plans kann bis zu einem Container über die Grenze führen: erst mehr als 1,5 Container zählen als verletzt."""
    at_limit = make_row(GOOD["Voller Platz"], gerechnet__stock_over=1.5, abgesichert__stock_over=1.5)
    over = make_row(GOOD["Voller Platz"], gerechnet__stock_over=1.51)
    assert flags("Voller Platz", (at_limit,))[2] is True and flags("Voller Platz", (over,))[2] is False


def test_holds_needs_every_criterion():
    row = make_row(GOOD["Ruhige Woche"], kranrate__wait=5.0)
    assert not ST.holds("Ruhige Woche", row) and any(flags("Ruhige Woche", (row,)))


def test_an_unknown_preset_raises():
    with pytest.raises(KeyError):
        ST.criteria("Nachtwoche", (make_row({}),))


def test_key_values_are_the_medians_of_the_typical_measures():
    rows = tuple(make_row({}, seed=i, gerechnet__distance=d, kranrate__wait=w) for i, (d, w) in enumerate([(250.0, 1.0), (260.0, 30.0), (300.0, 5.0)]))
    kv = ST.key_values(rows)
    assert kv[(LP, "distance")] == 260.0 and kv[(KBLOCKS, "wait")] == 5.0 and set(kv) == set(ST.TYPICAL) and len(ST.TYPICAL) == 6


def test_criteria_texts_carry_the_measured_numbers():
    texts = [t for _, t in ST.criteria("Stoßwoche", (make_row(GOOD["Stoßwoche"]),))]
    assert texts[0] == "Kranrate passend, Wartezeit pünktlich >= 10 min: 20.0" and texts[2] == "Gerechnet, Wartezeit bei Verspätung >= 25 min: 50.0" and texts[4].endswith(": 5.6")
    assert texts[5] == "Mehrweg der Absicherung >= 25 m: 40.0"
