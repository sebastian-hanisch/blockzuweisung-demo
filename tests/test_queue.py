"""Tests der Rückstands-Rekursion und der Kennzahlen: von Hand gerechnetes Beispiel, unabhängige Nachrechnung auf vielen Plänen, Massenbilanz, Lagergrenze, Beladeverzug, Verspätungsbewertung."""

import random

import pytest

import blz_queue as Q
import blz_rules as R
import blz_scenario as S
from helpers import reference_wait_and_distance, reference_wait_fine, stock_over


def hand_week():
    """Ein Schiff (6 Container), ein Block mit 2 Moves je Stunde, Fenster Stunden 0 und 1, keine Anlieferung, 5 Stunden."""
    return S.Week(ships=(S.Ship(6, 0, 2, 0.0, 0),), blocks=1, y=(0.0,), mu=2.0, hours=5, d=((200.0,),), total=6, seed=0, f=((0.5, 0.5, 0.0, 0.0, 0.0),), h=((0.0,) * 5,),
                  g=((1.0, 0.5, 0.0, 0.0, 0.0),), lf=((0.5, 0.5, 0.0, 0.0, 0.0),), limit=5.0)


def test_hand_computed_week_backlog_wait_delay_peak_and_stock():
    w = hand_week()
    load, q = Q.backlog(w, [[6]])
    assert load == [[3.0, 3.0, 0.0, 0.0, 0.0]] and q == [[1.0, 2.0, 0.0, 0.0, 0.0]]               # Last 3, 3 gegen Rate 2: Rückstand 1, dann 2, dann abgebaut
    m = Q.evaluate(w, [[6]])
    assert m.distance == 200.0 and m.wait == pytest.approx((1 + 2) / 6 * 60, abs=1e-12) == pytest.approx(30.0)
    assert m.delay_max == pytest.approx(2.0 / 2.0 * 60, abs=1e-12) and m.delays == pytest.approx((60.0,))        # Rückstand am Ende des Fensters 2 durch Rate 2 = 1 h
    assert m.peak == pytest.approx(1.5, abs=1e-12) and m.load == ((3.0, 3.0, 0.0, 0.0, 0.0),)
    assert m.stock_over == pytest.approx(1.0, abs=1e-12) and m.fill == pytest.approx(1.2, abs=1e-12)              # Bestand 6 gegen Grenze 5


def test_a_block_that_keeps_up_has_no_backlog_and_no_wait():
    w = hand_week()
    m = Q.evaluate(S.Week(**{**w.__dict__, "mu": 3.0}), [[6]])
    assert m.wait == 0.0 and m.delay_max == 0.0 and m.peak == pytest.approx(1.0, abs=1e-12)


def test_the_backlog_is_carried_over_and_drains_after_the_window():
    w = hand_week()
    _, q = Q.backlog(w, [[6]])
    assert q[0][1] == 2.0 and q[0][2] == 0.0                                                      # 2 + 0 - 2 = 0 in der Stunde danach
    w2 = S.Week(**{**w.__dict__, "mu": 1.0, "hours": 8, "f": ((0.5, 0.5) + (0.0,) * 6,), "lf": ((0.5, 0.5) + (0.0,) * 6,), "h": ((0.0,) * 8,), "g": ((0.0,) * 8,)})
    _, q2 = Q.backlog(w2, [[6]])
    assert q2[0] == [2.0, 4.0, 3.0, 2.0, 1.0, 0.0, 0.0, 0.0]


def test_evaluate_matches_an_independent_recomputation_on_many_plans_and_weeks():
    rng = random.Random(4)
    for seed in range(60):
        w = S.make_week(seed, ships=rng.randint(3, 8), blocks=rng.randint(6, 10), mu=float(rng.choice([30, 40, 50, 60])), crane=rng.choice([60, 90, 120]), fill=rng.choice([None, 60, 90]))
        x = [[rng.randint(0, 40) for _ in range(w.blocks)] for _ in range(w.n_ships)]
        w = S.Week(**{**w.__dict__, "ships": tuple(S.Ship(sum(row), sh.start, sh.length, sh.pos, sh.berth) for sh, row in zip(w.ships, x)), "total": sum(map(sum, x))})
        d_ref, w_ref = reference_wait_and_distance(w, x)
        m = Q.evaluate(w, x)
        assert m.distance == pytest.approx(d_ref, abs=1e-9) and m.wait == pytest.approx(w_ref, abs=1e-9)
        assert m.stock_over == pytest.approx(stock_over(w, x), abs=1e-9)


def test_backlog_is_never_negative_and_the_load_adds_up_to_two_moves_per_container():
    for seed in range(20):
        w = S.make_week(seed)
        x = R.rule_kblocks(w)
        load, q = Q.backlog(w, x)
        assert all(v >= 0 for row in q for v in row)
        assert sum(sum(row) for row in load) == pytest.approx(2 * w.total, rel=1e-12)             # ein Move bei der Anlieferung, einer beim Abruf


def test_more_block_rate_never_increases_the_wait():
    w = S.make_week(3)
    x = R.rule_kblocks(w)
    waits = [Q.evaluate(S.Week(**{**w.__dict__, "mu": float(mu)}), x).wait for mu in (30, 40, 50, 60, 200)]
    assert waits == sorted(waits, reverse=True) and waits[-1] == 0.0


def test_peak_is_the_largest_block_load_in_shares_of_the_rate():
    w = S.make_week(2017)
    x = R.rule_bundle(w)
    m = Q.evaluate(w, x)
    assert m.peak == pytest.approx(max(v for row in m.load for v in row) / 40.0, abs=1e-12) and m.peak > 1.0
    assert Q.evaluate(w, R.rule_spread(w)).peak < 1.0


def test_stock_over_and_fill_are_zero_without_a_limit_and_positive_when_exceeded():
    w = S.make_week(2017, fill=None)
    assert w.limit is None and Q.evaluate(w, R.rule_bundle(w)).stock_over == 0.0 and Q.evaluate(w, R.rule_bundle(w)).fill == 0.0
    w90 = S.make_week(2017, fill=90)
    m = Q.evaluate(w90, R.rule_bundle(w90))
    assert m.stock_over == pytest.approx(177.19907407407402, abs=1e-9) and m.fill > 1.0                # aus der Messreihe (Voller Platz, Bündeln)
    assert Q.evaluate(w90, R.rule_spread(w90)).stock_over == 0.0 and Q.evaluate(w90, R.rule_spread(w90)).fill < 0.95


def test_delay_uses_the_backlog_at_the_end_of_each_window_of_the_blocks_used():
    w = S.make_week(2017)
    x = R.rule_bundle(w)
    m = Q.evaluate(w, x)
    load, q = Q.backlog(w, x)
    for s, sh in enumerate(w.ships):
        te = sh.start + sh.length - 1
        used = [b for b in range(8) if x[s][b] > 0]
        assert m.delays[s] == pytest.approx(max(q[b][te] for b in used) / 40.0 * 60.0, abs=1e-9)
    assert m.delay_max == max(m.delays)
    assert Q.evaluate(w, R.rule_spread(w)).delay_max == 0.0


def test_a_ship_without_containers_in_any_block_has_no_delay():
    w = hand_week()
    assert Q.evaluate(w, [[0]]).delays == (0.0,)


# ---------- Bewertung bei Verspätung ----------
def test_the_hourly_model_agrees_with_a_five_minute_model_within_five_percent():
    """Feinschritt (5 min) gegen das Stundenmodell: Messreihe 36,6 gegen 36,6 (Kranrate passend), 8,53 gegen 8,38 (Gierig), höchstens 3,3 % Abweichung; hier Toleranz 5 % für Wartezeiten über 1 min."""
    checked = 0
    for seed in range(8):
        w = S.make_week(seed, fill=None)
        for rule in (R.rule_kblocks, R.rule_greedy):
            x = rule(w)
            hourly, fine = Q.evaluate(w, x).wait, reference_wait_fine(w, x)
            if hourly > 1.0:
                assert abs(fine - hourly) / hourly <= 0.05, (seed, rule.__name__, hourly, fine)
                checked += 1
    assert checked >= 8


def test_robust_eval_is_the_mean_over_the_scenarios_of_the_shifted_weeks():
    w = S.make_week(2017)
    x = R.rule_kblocks(w)
    scen = S.evaluation_scenarios(w, 3)
    r = Q.robust_eval(w, x, scen)
    waits = [reference_wait_and_distance(S.shifted(w, dl), x)[1] for dl in scen]
    assert r.waits == pytest.approx(tuple(waits), abs=1e-9) and r.wait == pytest.approx(sum(waits) / 30, abs=1e-9)
    assert r.wait95 == pytest.approx(sorted(waits)[28], abs=1e-9)          # 95. Perzentil: ceil(0,95 * 30) - 1 = Stelle 28
    assert r.delay_max == pytest.approx(sum(Q.evaluate(S.shifted(w, dl), x).delay_max for dl in scen) / 30, abs=1e-9)


def test_robust_eval_with_no_shift_equals_the_nominal_evaluation():
    w = S.make_week(9)
    x = R.rule_greedy(w)
    r = Q.robust_eval(w, x, [[0] * w.n_ships] * 3)
    m = Q.evaluate(w, x)
    assert r.wait == pytest.approx(m.wait, abs=1e-12) and r.wait95 == pytest.approx(m.wait, abs=1e-12) and r.delay_max == pytest.approx(m.delay_max, abs=1e-12)


def test_reference_values_of_the_messreihe_seed_2017_are_reproduced_bit_identically():
    """blz.py der Messreihe, Woche 2017 (Stoßwoche): Weg, Wartezeit, größter Beladeverzug und Wartezeit bei Verspätung (30 Testszenarien) der vier Regeln."""
    w = S.make_week(2017)
    test = S.evaluation_scenarios(w, 3)
    expected = {"bundle": (259.1261620185923, 148.09199565374857, 630.0000000000001, 184.70102683062836), "spread": (453.18725099601596, 0.0, 0.0, 4.806723466882828),
                "kblocks": (259.6148738379814, 20.526548352046362, 136.66666666666663, 55.24732521573157), "greedy": (341.2084993359894, 3.289905313809688, 31.66666666666663, 23.218202859557426)}
    rules = {"bundle": R.rule_bundle, "spread": R.rule_spread, "kblocks": R.rule_kblocks, "greedy": R.rule_greedy}
    for name, (d, wait, dmax, rw) in expected.items():
        x = rules[name](w)
        m, r = Q.evaluate(w, x), Q.robust_eval(w, x, test)
        assert (m.distance, m.wait, m.delay_max, r.wait) == pytest.approx((d, wait, dmax, rw), abs=1e-9), name
    assert R.rule_bundle(w)[0] == [54, 860, 0, 0, 0, 0, 0, 0]
