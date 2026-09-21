"""Tests der Woche: Reproduktion der Messreihe (feste Referenzwerte aus hafen-planung/messreihe_blockzuweisung/blz.py), Massenbilanz, Verschiebungen, Lagergrenze, Grenzen der Regler."""

import math
import random

import pytest

import blz_constants as C
import blz_scenario as S

# Woche des Presets Stoßwoche, Seed 2017, aus der Messreihe (make_instance(2017, S=6, B=8, mu=40, crane_rates=(60, 90), dpre=36, cap_factor=100/70)): (n, Beginn, Länge, Liegeplatz, Liegeplatz-Nr.)
SHIPS_2017 = [(914, 42, 16, 133.33333333333334, 0), (1225, 46, 14, 400.0, 1), (1247, 46, 21, 666.6666666666666, 2), (944, 58, 11, 133.33333333333334, 0),
              (1239, 60, 21, 400.0, 1), (706, 67, 12, 666.6666666666666, 2)]


def week_2017(fill=70):
    return S.make_week(2017, 6, 8, 40.0, 90, fill)


def test_the_week_reproduces_the_messreihe_seed_2017():
    w = week_2017()
    assert [(sh.n, sh.start, sh.length, sh.pos, sh.berth) for sh in w.ships] == SHIPS_2017
    assert w.hours == 103 and w.total == 6275 and w.blocks == 8 and w.mu == 40.0
    assert w.limit == pytest.approx(863.9583333333336, abs=1e-9)
    assert week_2017(90).limit == pytest.approx(671.9675925925928, abs=1e-9)


def test_fahrweg_matrix_is_200_m_plus_the_distance_along_the_quay():
    w = week_2017()
    assert w.y == tuple(100.0 * (b + 0.5) for b in range(8))
    for s, sh in enumerate(w.ships):
        for b in range(8):
            assert w.d[s][b] == pytest.approx(200.0 + abs(sh.pos - w.y[b]), abs=1e-9)
    assert w.d[0][0] == pytest.approx(200.0 + abs(133.33333333333334 - 50.0), abs=1e-9)


def test_berths_are_three_equidistant_positions_and_windows_do_not_overlap_on_a_berth():
    w = week_2017()
    assert sorted({sh.pos for sh in w.ships}) == pytest.approx([800 * (k + 0.5) / 3 for k in range(3)])
    for berth in range(3):
        on = sorted((sh.start, sh.start + sh.length) for sh in w.ships if sh.berth == berth)
        assert all(a[1] <= b[0] for a, b in zip(on, on[1:]))


def test_deliveries_start_36_hours_before_the_window_and_the_crane_calls_over_the_window():
    w = week_2017()
    for s, sh in enumerate(w.ships):
        called = [t for t in range(w.hours) if w.f[s][t] > 0]
        delivered = [t for t in range(w.hours) if w.h[s][t] > 0]
        assert called == list(range(sh.start, sh.start + sh.length)) and delivered == list(range(sh.start - 36, sh.start))


@pytest.mark.parametrize("seed", [0, 5, 2017, 9999])
def test_mass_balance_each_ship_calls_and_receives_exactly_all_its_containers(seed):
    w = S.make_week(seed)
    for s in range(w.n_ships):
        assert sum(w.f[s]) == pytest.approx(1.0, abs=1e-12) and sum(w.h[s]) == pytest.approx(1.0, abs=1e-12) and sum(w.lf[s]) == pytest.approx(2.0, abs=1e-12)
        assert all(abs(w.lf[s][t] - (w.f[s][t] + w.h[s][t])) < 1e-15 for t in range(w.hours))


def test_stock_share_rises_during_delivery_and_falls_during_loading_and_ends_empty():
    w = week_2017()
    g = w.g[0]
    sh = w.ships[0]
    assert g[sh.start - 37] == 0.0 and g[sh.start - 1] == pytest.approx(1.0, abs=1e-12) and g[sh.start - 1 + sh.length] == 0.0
    assert g[sh.start - 19] == pytest.approx(18 / 36, abs=1e-12)                    # nach 18 von 36 Stunden Anlieferung die Hälfte
    assert g[sh.start + sh.length // 2 - 1] == pytest.approx(1.0 - (sh.length // 2) / sh.length, abs=1e-12)


def test_storage_limit_is_the_peak_stock_divided_by_blocks_and_fill():
    """K = Spitzenbestand aller Schiffe gleichzeitig / Blöcke / Lagerfüllung, unabhängig nachgerechnet."""
    w = week_2017(70)
    peak = max(sum(w.ships[s].n * w.g[s][t] for s in range(w.n_ships)) for t in range(w.hours))
    assert w.limit == pytest.approx(peak / 8 / 0.70, rel=1e-12)
    assert week_2017(50).limit == pytest.approx(peak / 8 / 0.50, rel=1e-12) and week_2017(None).limit is None


def test_without_delivery_load_all_containers_are_in_the_block_from_the_start_of_the_window():
    w = S.make_week(3, delivery=0, fill=70)
    assert all(sum(w.h[s]) == 0 for s in range(w.n_ships))
    sh = w.ships[0]
    assert w.g[0][sh.start - 1] == 0.0 and w.g[0][sh.start] == pytest.approx(1.0 - 1.0 / sh.length, abs=1e-12)


def test_crane_rates_are_the_upper_rate_and_two_thirds_of_it():
    assert S.crane_rates(60) == (40.0, 60.0) and S.crane_rates(90) == (60.0, 90.0) and S.crane_rates(120) == (80.0, 120.0)
    lengths = {(sh.n / sh.length) for sh in S.make_week(11, crane=120).ships}
    assert all(60 <= v <= 120 + 1e-9 for v in lengths)                                # Abrufrate des Schiffs: n / Länge liegt beim Aufrunden knapp unter r


def test_window_length_is_at_least_three_hours_and_matches_one_of_the_two_rates():
    for seed in range(20):
        for sh in S.make_week(seed, crane=90).ships:
            assert sh.length >= 3 and any(sh.length == max(3, math.ceil(sh.n / rho)) for rho in (60, 90))


def test_a_slow_small_ship_still_gets_a_window_of_three_hours():
    """Kleinstinstanzen (3 bis 5 Container, Rate 2 oder 3 je Stunde): die Länge n / Rate ist oft kleiner als 3, das Fenster hat mindestens 3 Stunden."""
    lengths = [(sh.n, sh.length) for seed in range(10) for sh in S.make_week(seed, ships=3, blocks=3, mu=1.0, crane=3, fill=None, delivery=0, n_range=(3, 5), span=2).ships]
    assert all(length == max(3, math.ceil(n / 2)) or length == max(3, math.ceil(n / 3)) for n, length in lengths) and all(length >= 3 for _, length in lengths)
    assert any(math.ceil(n / 3) < 3 and length == 3 for n, length in lengths) and any(length == 3 and math.ceil(n / 2) == 3 for n, length in lengths)


def test_generation_is_deterministic_and_every_setting_changes_the_week():
    assert S.make_week(7).ships == S.make_week(7).ships and S.make_week(7).ships != S.make_week(8).ships
    assert S.make_week(7, ships=4).n_ships == 4 and S.make_week(7, blocks=10).blocks == 10 and S.make_week(7, mu=60.0).mu == 60.0
    assert S.make_week(7, crane=60).ships != S.make_week(7, crane=120).ships


@pytest.mark.parametrize("ships,blocks", [(3, 6), (8, 10), (3, 10), (8, 6)])
def test_regler_extremes_build_valid_weeks(ships, blocks):
    w = S.make_week(1, ships, blocks, 30.0, 120, 50)
    assert w.n_ships == ships and w.blocks == blocks and len(w.d) == ships and all(len(r) == blocks for r in w.d) and w.limit > 0
    assert w.hours == max(sh.start + sh.length for sh in w.ships) + 22


def test_peak_ratio_is_peak_demand_over_total_block_rate():
    w = week_2017()
    demand = max(sum(sh.n / sh.length for sh in w.ships if sh.start <= t < sh.start + sh.length) for t in range(w.hours))
    assert S.peak_ratio(w) == pytest.approx(demand / (8 * 40.0), rel=1e-12)
    assert S.peak_ratio(w) == pytest.approx(0.7271847943722943, abs=1e-12)                # Stoßwoche, Seed 2017: 73 % der Gesamtrate (Median der Grundgesamtheit 72 %)


# ---------- Verschiebungen ----------
def test_shifted_by_zero_is_the_base_week_bit_identically():
    w = week_2017()
    z = S.shifted(w, [0] * 6)
    assert z.f == w.f and z.lf == w.lf and z.ships == w.ships and z.g == w.g and z.h == w.h


def test_shifted_moves_the_call_window_but_not_the_delivery_or_the_stock():
    w = week_2017()
    z = S.shifted(w, [2, -3, 0, 0, 5, 0])
    assert [sh.start for sh in z.ships] == [44, 43, 46, 58, 65, 67]
    assert z.h == w.h and z.g == w.g
    for s in range(6):
        assert sum(z.f[s]) == pytest.approx(1.0, abs=1e-12)
        assert [t for t in range(z.hours) if z.f[s][t] > 0] == list(range(z.ships[s].start, z.ships[s].start + z.ships[s].length))


def test_shifted_never_starts_before_hour_zero_or_ends_beyond_the_week():
    w = week_2017()
    z = S.shifted(w, [-500, 500, 0, 0, 0, 0])
    assert z.ships[0].start == 0 and z.ships[1].start + z.ships[1].length == w.hours
    assert all(sum(z.f[s]) == pytest.approx(1.0, abs=1e-12) for s in range(6))


def test_deltas_are_rounded_gaussians_and_zero_without_sigma():
    rng = random.Random(3)
    ref = random.Random(3)
    assert S.deltas(rng, 6, 3) == [int(round(ref.gauss(0.0, 3))) for _ in range(6)]
    assert S.deltas(random.Random(1), 6, 0) == [0] * 6
    spread = [d for seed in range(400) for d in S.deltas(random.Random(seed), 6, 3)]
    assert 2.5 < (sum(d * d for d in spread) / len(spread)) ** 0.5 < 3.5 and min(spread) < -5 and max(spread) > 5


def test_scenario_sets_are_reproducible_and_training_and_test_seeds_are_disjoint():
    assert S.scenario_set(2017, 6, 3, 30, 0) == S.scenario_set(2017, 6, 3, 30, 0)
    w = week_2017()
    train, test = S.train_scenarios(w, 3), S.evaluation_scenarios(w, 3)
    assert len(train) == 10 and len(test) == 30 and train != test[:10]
    assert train == S.scenario_set(2017, 6, 3, 10, 500000) and test == S.scenario_set(2017, 6, 3, 30, 0)
    assert S.scenario_set(2017, 6, 3, 5, 0) != S.scenario_set(2018, 6, 3, 5, 0)
    assert all(d == [0] * 6 for d in S.train_scenarios(w, 0))


def test_first_test_scenario_of_seed_2017_matches_the_messreihe():
    """common.scen_set(2017, 6, 3.0, 30, 0)[0] der Messreihe (random.Random(2017000).gauss)."""
    ref = random.Random(0 + 1000 * 2017 + 0)
    assert S.scenario_set(2017, 6, 3, 30, 0)[0] == [int(round(ref.gauss(0.0, 3))) for _ in range(6)]
