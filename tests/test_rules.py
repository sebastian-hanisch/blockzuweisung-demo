"""Tests der vier Regeln: jede verteilt genau n Container je Schiff, gleiche Ergebnisse wie eine unabhängige einfache Fassung, kanonische Reihenfolge bei Gleichstand, Lagerprüfung, Grenzfälle."""

import pytest

import blz_rules as R
import blz_scenario as S
from helpers import reference_rule, stock_over

RULES = {"bundle": R.rule_bundle, "spread": R.rule_spread, "kblocks": R.rule_kblocks, "greedy": R.rule_greedy}
SETTINGS = [dict(seed=s, ships=sh, blocks=b, mu=float(mu), crane=cr, fill=fl) for s, sh, b, mu, cr, fl in
            [(0, 6, 8, 40, 90, 70), (1, 3, 6, 30, 60, 50), (2, 8, 10, 60, 120, 90), (3, 5, 8, 40, 120, 70), (4, 4, 8, 60, 60, 60), (5, 6, 8, 40, 90, None), (6, 8, 6, 30, 120, 90)]]


@pytest.mark.parametrize("name", list(RULES))
@pytest.mark.parametrize("kw", SETTINGS)
def test_every_rule_distributes_exactly_n_whole_containers_per_ship(name, kw):
    w = S.make_week(**kw)
    x = RULES[name](w)
    assert len(x) == w.n_ships and all(len(row) == w.blocks for row in x)
    for s, sh in enumerate(w.ships):
        assert sum(x[s]) == sh.n and all(isinstance(v, int) and v >= 0 for v in x[s])


@pytest.mark.parametrize("name", ["bundle", "kblocks", "greedy"])
def test_the_portion_rules_agree_with_an_independent_naive_version(name):
    for kw in SETTINGS:
        w = S.make_week(**kw)
        assert RULES[name](w) == reference_rule(w, name), (name, kw)


def test_spread_differs_by_at_most_one_container_between_blocks():
    for seed in range(15):
        w = S.make_week(seed, blocks=7 + seed % 4)
        for s, row in enumerate(R.rule_spread(w)):
            assert max(row) - min(row) <= 1 and sum(row) == w.ships[s].n


def test_split_rounded_uses_largest_remainders_and_the_smaller_index_on_ties():
    assert R.split_rounded(10, [1, 1, 1]) == [4, 3, 3]
    assert R.split_rounded(11, [1, 1, 1]) == [4, 4, 3]
    assert R.split_rounded(9, [1, 1, 1]) == [3, 3, 3]
    assert R.split_rounded(10, [1, 2, 7]) == [1, 2, 7] and R.split_rounded(7, [0.5, 0.25, 0.25]) == [3, 2, 2]
    assert R.split_rounded(0, [1, 1]) == [0, 0]


def test_bundle_without_storage_limit_puts_every_ship_into_its_nearest_block():
    for seed in range(10):
        w = S.make_week(seed, fill=None)
        for s, row in enumerate(R.rule_bundle(w)):
            assert row[R.block_order(w, s)[0]] == w.ships[s].n and sum(1 for v in row if v) == 1


def test_block_order_is_by_distance_and_then_by_index():
    w = S.make_week(2017)
    for s in range(w.n_ships):
        order = R.block_order(w, s)
        assert sorted(order) == list(range(8)) and all((w.d[s][a], a) <= (w.d[s][b], b) for a, b in zip(order, order[1:]))
    s_mid = next(s for s, sh in enumerate(w.ships) if sh.berth == 1)                       # Liegeplatz in der Mitte: Block 4 und 5 (Index 3 und 4) gleich weit
    assert R.block_order(w, s_mid)[:2] == [3, 4] and w.d[s_mid][3] == w.d[s_mid][4]


def test_ships_are_processed_by_window_start_then_index():
    w = S.make_week(2017)
    assert R.ship_order(w) == sorted(range(6), key=lambda s: (w.ships[s].start, s)) and R.ship_order(w)[:2] == [0, 1]           # Schiff 1 und 2 (Beginn 42 und 46; 2 und 3 gleich: kleiner Index)


def test_kblocks_uses_as_many_blocks_as_the_crane_rate_requires_when_storage_is_no_limit():
    w = S.make_week(2017, fill=None)
    x = R.rule_kblocks(w)
    import math
    for s, sh in enumerate(w.ships):
        k = min(8, max(1, math.ceil(sh.n / sh.length / 40.0)))
        used = [b for b in range(8) if x[s][b]]
        assert len(used) == k and used == sorted(R.block_order(w, s)[:k])


def test_greedy_keeps_the_peak_below_eighty_percent_when_that_is_possible():
    w = S.make_week(0, ships=3, blocks=10, mu=60.0, crane=60, fill=None)
    from blz_queue import evaluate
    assert evaluate(w, R.rule_greedy(w)).peak <= 0.8 + 1e-9
    assert evaluate(w, R.rule_greedy(w, cap=0.5)).peak <= 0.5 + 0.2                             # bei kleiner Kappe weicht die Regel auf die kleinste Spitze aus, ohne abzustürzen


def test_greedy_falls_back_to_the_block_with_the_smallest_peak_when_none_fits_the_cap():
    w = S.make_week(2017, fill=None)
    x_all = R.rule_greedy(w, cap=0.0)                                                         # nichts bleibt unter 0 %: immer der Block mit der kleinsten Spitze
    assert all(sum(row) == sh.n for row, sh in zip(x_all, w.ships))
    from blz_queue import evaluate
    assert evaluate(w, x_all).peak < evaluate(w, R.rule_bundle(w)).peak


# ---------- Lagerplatz (Korrektur 3 der Messreihe) ----------
def test_storage_check_matters_the_blind_rules_break_the_limit_and_the_checking_ones_almost_never_do():
    """Ohne Prüfung verletzte "Kranrate passend" die Lagergrenze in 17 von 30 Wochen (Messreihe, Füllung 70 %); mit Prüfung höchstens in wenigen."""
    weeks = [S.make_week(seed) for seed in range(30)]
    blind = sum(1 for w in weeks if stock_over(w, reference_rule(w, "kblocks", check_storage=False)) > 1.5)
    checked = sum(1 for w in weeks if stock_over(w, R.rule_kblocks(w)) > 1.5)
    assert blind >= 10 and checked <= 3


def test_violation_counts_at_ninety_percent_fill_seeds_0_to_29():
    """Bei 90 % Lagerfüllung sprengen die schiffsweisen Regeln die Grenze oft (Messreihe bei 91 %: Bündeln 10 von 10, Kranrate 8 von 10, Gierig 8 von 10 Wochen), Verteilen nie."""
    weeks = [S.make_week(seed, fill=90) for seed in range(30)]
    counts = {name: sum(1 for w in weeks if stock_over(w, RULES[name](w)) > 1.5) for name in RULES}
    assert counts == {"bundle": 30, "spread": 0, "kblocks": 23, "greedy": 21}


def test_spread_never_violates_the_limit_up_to_ninety_percent():
    for seed in range(30):
        w = S.make_week(seed, fill=90)
        assert stock_over(w, R.rule_spread(w)) <= 1e-6


def test_fits_true_without_limit_and_false_when_the_block_is_full():
    w = S.make_week(2017, fill=None)
    st = R._State(w)
    assert st.fits(0, 0, 10 ** 9)
    w = S.make_week(2017, fill=90)
    st = R._State(w)
    assert st.fits(0, 0, 10) and not st.fits(0, 0, int(w.limit) + 5)
    st.add(0, 0, 10)
    assert st.stock[0][w.ships[0].start - 1] == pytest.approx(10.0, abs=1e-9) and st.load[0][w.ships[0].start] == pytest.approx(10 * (w.f[0][w.ships[0].start] + w.h[0][w.ships[0].start]), abs=1e-9)


# ---------- Grenzfälle ----------
def test_with_one_block_all_rules_are_identical():
    for seed in range(5):
        w = S.make_week(seed, blocks=1, fill=None)
        plans = [RULES[n](w) for n in RULES]
        assert all(p == plans[0] for p in plans) and plans[0] == [[sh.n] for sh in w.ships]


def test_rules_are_deterministic():
    w = S.make_week(2017)
    for f in RULES.values():
        assert f(w) == f(w)
