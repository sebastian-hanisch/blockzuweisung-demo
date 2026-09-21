"""Tests des LP: Zielwert gegen unabhängige Nachrechnung, Kleinstinstanzen gegen vollständiges Durchprobieren, Grenzfälle (ein Block, unbegrenzte Rate, σ = 0), LP nie schlechter als jede Regel, Skalierung,
Rundung, Löserstatus. Geprüft werden Zielwerte und Kennzahlen, nie die Aufteilung: bei mehreren gleichwertigen Plänen ist sie lösungsabhängig (CI installiert die neueste OR-Tools-Version)."""

import pytest
from ortools.linear_solver import pywraplp

import blz_lp as L
import blz_queue as Q
import blz_rules as R
import blz_scenario as S
from helpers import brute_force_objectives, reference_wait_and_distance, stock_over, tiny_week


def scen_loads(w, sigma=3):
    return [S.shifted(w, dl).lf for dl in S.train_scenarios(w, sigma)]


# ---------- Zielwert gegen unabhängige Nachrechnung ----------
@pytest.mark.parametrize("mode", ["min_wait", "lam5", "lam50", "eps5"])
def test_lp_value_equals_the_independent_recomputation_of_the_plan(mode):
    """Der LP-Zielwert (Weg, Wartezeit) ist die Wartezeit der Simulation für denselben Bruchteilsplan (Konvexität): Abweichung höchstens 1e-9."""
    worst = 0.0
    for seed in range(20):
        w = S.make_week(seed)
        eps = max(5.0, L.solve(w, min_wait=True).wait + 1e-6)                                        # unter der kleinstmöglichen Wartezeit wäre das LP unzulässig
        kw = {"min_wait": dict(min_wait=True), "lam5": dict(lam=5), "lam50": dict(lam=50), "eps5": dict(eps_wait=eps)}[mode]
        res = L.solve(w, **kw)
        d_ref, w_ref = reference_wait_and_distance(w, res.x)
        worst = max(worst, abs(d_ref - res.distance), abs(w_ref - res.wait))
        assert all(sum(row) == pytest.approx(w.ships[s].n, abs=1e-6) and min(row) >= -1e-9 for s, row in enumerate(res.x))
    assert worst < 1e-9


def test_lp_value_equals_the_recomputation_on_tiny_weeks_with_load_in_the_first_hours():
    """Kleinstwochen beginnen in Stunde 0 bis 2 mit einer Last über der Rate: der Rückstand muss von Stunde zu Stunde weitergegeben werden (sonst meldet das LP zu wenig Wartezeit)."""
    for seed in range(10):
        w = tiny_week(seed)
        for kw in (dict(lam=3.0), dict(min_wait=True)):
            res = L.solve(w, **kw)
            d_ref, w_ref = reference_wait_and_distance(w, res.x)
            assert res.distance == pytest.approx(d_ref, abs=1e-9) and res.wait == pytest.approx(w_ref, abs=1e-9), (seed, kw)


def test_scenario_lp_value_is_the_mean_wait_over_the_scenarios_of_the_simulation():
    for seed in range(8):
        w = S.make_week(seed)
        loads = scen_loads(w)
        res = L.solve(w, lam=10, scenarios=loads)
        waits = [Q.evaluate(S.shifted(w, dl), res.x).wait for dl in S.train_scenarios(w, 3)]
        assert res.wait == pytest.approx(sum(waits) / 10, abs=1e-9)
        assert res.distance == pytest.approx(Q.evaluate(w, res.x).distance, abs=1e-9)


def test_minimal_wait_lp_is_lexicographic_the_distance_is_the_shortest_among_the_wait_optimal_plans():
    """Ziel "Wartezeit + 1e-6 Weg": derselbe Weg wie beim kürzesten Weg unter der Wartezeit-Grenze des Optimums (Zielwert eindeutig, Aufteilung nicht)."""
    for seed in range(8):
        w = S.make_week(seed)
        a = L.solve(w, min_wait=True)
        b = L.solve(w, eps_wait=a.wait + 1e-6)
        assert a.distance == pytest.approx(b.distance, abs=1e-3) and b.wait <= a.wait + 1e-6 + 1e-9


def test_the_minimal_wait_of_the_exact_method_is_the_true_minimum_not_a_weighted_compromise():
    """Das zweite Ziel (Weg, Gewicht 1e-6) darf die Wartezeit nicht anheben: gegen ein LP, das Wartezeit mit dem Preis 1e5 m je min über alles stellt, gleiche Wartezeit."""
    for seed in range(8):
        w = S.make_week(seed)
        a = L.solve(w, min_wait=True)
        b = L.solve(w, lam=1e5)
        assert a.wait == pytest.approx(b.wait, abs=5e-3), seed
        assert a.distance == pytest.approx(b.distance, abs=1.0), seed


# ---------- LP gegen Regeln und gegen Durchprobieren ----------
def test_lp_is_never_worse_than_any_rule_in_wait_and_in_the_weighted_objective():
    for seed in range(12):
        w = S.make_week(seed)
        best_w = L.solve(w, min_wait=True).wait
        for lam in (2, 10, 50):
            lp = L.solve(w, lam=lam)                                                               # ein Szenario: die pünktliche Woche
            lp_value = lp.distance + lam * lp.wait
            for rule in (R.rule_bundle, R.rule_spread, R.rule_kblocks, R.rule_greedy):
                m = Q.evaluate(w, rule(w))
                assert lp_value <= m.distance + lam * m.wait + 1e-9, (seed, lam, rule.__name__)
                assert best_w <= m.wait + 1e-9


def test_lp_bound_never_exceeds_the_integer_optimum_found_by_exhaustive_search_on_tiny_instances():
    """3 Schiffe x 3 Blöcke, 3 bis 5 Container: LP-Schranke <= ganzzahliges Optimum (Durchprobieren aller Pläne); der gerundete LP-Plan ist ein zulässiger Plan, also nie besser als das Optimum."""
    lams = (1.0, 3.0, 30.0)
    for seed in range(10):
        w = tiny_week(seed)
        best = brute_force_objectives(w, lams)
        for lam in lams:
            res = L.solve(w, lam=lam)
            bound = res.distance + lam * res.wait
            assert bound <= best[lam][0] + 1e-9, (seed, lam)
            d_r, w_r = reference_wait_and_distance(w, L.round_plan(w, res.x))
            assert d_r + lam * w_r >= best[lam][0] - 1e-9


# ---------- Grenzfälle ----------
def test_one_block_lp_equals_the_rules():
    for seed in range(4):
        w = S.make_week(seed, blocks=1, fill=None)
        res = L.solve(w, min_wait=True)
        assert [row[0] for row in res.x] == pytest.approx([sh.n for sh in w.ships], abs=1e-6)
        assert L.round_plan(w, res.x) == R.rule_bundle(w)


def test_unlimited_block_rate_lp_distance_equals_bundling():
    for seed in range(5):
        w = S.make_week(seed, fill=None)
        fast = S.Week(**{**w.__dict__, "mu": 1e6})
        assert L.solve(fast, min_wait=True).distance == pytest.approx(Q.evaluate(fast, R.rule_bundle(fast)).distance, abs=1e-6)


def test_sigma_zero_the_scenario_lp_value_equals_the_single_scenario_lp_value():
    for seed in range(5):
        w = S.make_week(seed)
        same = scen_loads(w, sigma=0)
        assert all(lf == w.lf for lf in same)
        a = L.solve(w, lam=20, scenarios=same)
        b = L.solve(w, lam=20)
        assert a.distance + 20 * a.wait == pytest.approx(b.distance + 20 * b.wait, abs=1e-9)


def test_scenario_lp_with_a_higher_price_never_gets_shorter_and_never_waits_more_in_the_planning_scenarios():
    w = S.make_week(2017)
    loads = scen_loads(w)
    results = [L.solve(w, lam=lam, scenarios=loads) for lam in (1, 5, 20, 100)]
    assert all(a.distance <= b.distance + 1e-6 for a, b in zip(results, results[1:])) and all(a.wait >= b.wait - 1e-6 for a, b in zip(results, results[1:]))


def test_the_edge_is_monotone_and_bounded_by_the_nearest_block_plan():
    w = S.make_week(2017)
    wmin = L.solve(w, min_wait=True).wait
    edge = [L.edge_distance(w, eps, wmin) for eps in (400, 100, 20, 5, 1)]
    assert all(a <= b + 1e-9 for a, b in zip(edge, edge[1:]))                                    # weniger erlaubte Wartezeit: nie ein kürzerer Weg
    nearest = sum(sh.n * min(w.d[s]) for s, sh in enumerate(w.ships)) / w.total
    assert edge[0] >= nearest - 1e-9 and edge[-1] <= Q.evaluate(w, R.rule_spread(w)).distance + 1e-9


def test_the_edge_at_an_allowed_wait_below_the_optimum_is_clamped_to_the_feasible_minimum():
    w = S.make_week(2017)
    wmin = L.solve(w, min_wait=True).wait
    assert L.edge_distance(w, 0.0, wmin) == pytest.approx(L.edge_distance(w, wmin + 1e-6, wmin), abs=1e-9)


# ---------- Lagerplatz und Skalierung (Korrektur 2 der Messreihe) ----------
def test_lp_finds_an_optimum_in_every_week_at_high_fill_and_keeps_the_storage_limit():
    """Ohne Skalierung der Variablen meldete GLOP mit Lagerzeilen in 3 bis 4 von 12 Wochen INFEASIBLE oder ABNORMAL."""
    for seed in range(15):
        w = S.make_week(seed, fill=90)
        for kw in (dict(min_wait=True), dict(lam=10, scenarios=scen_loads(w))):
            res = L.solve(w, **kw)
            assert stock_over(w, res.x) <= 1e-5


def test_the_storage_limit_costs_the_nominal_plan_some_distance():
    """Messreihe: die Lagergrenze kostet den nominalen Plan bis zu 10,5 m gegen den Plan ohne Grenze."""
    for seed in range(8):
        limited = L.solve(S.make_week(seed, fill=90), min_wait=True).distance
        free = L.solve(S.make_week(seed, fill=None), min_wait=True).distance
        assert limited >= free - 1e-6 and limited - free < 30


# ---------- Rundung ----------
def test_round_plan_keeps_the_sums_and_is_deterministic():
    w = S.make_week(2017)
    res = L.solve(w, lam=20, scenarios=scen_loads(w))
    r1, r2 = L.round_plan(w, res.x), L.round_plan(w, res.x)
    assert r1 == r2 and all(sum(row) == sh.n and all(isinstance(v, int) and v >= 0 for v in row) for row, sh in zip(r1, w.ships))


def test_round_plan_takes_the_largest_remainders_first_and_the_smaller_index_on_ties():
    w = tiny_week(0, ships=1, blocks=4)
    w = S.Week(**{**w.__dict__, "ships": (S.Ship(10, 0, 3, 0.0, 0),), "total": 10})
    assert L.round_plan(w, [[0.6, 1.4, 1.5, 6.5]]) == [[1, 1, 2, 6]]                             # Reste 0,6 / 0,4 / 0,5 / 0,5: zwei Zusatzcontainer für 0,6 und (Gleichstand mit 0,5) den kleineren Index
    assert L.round_plan(w, [[2.5, 2.5, 2.5, 2.5]]) == [[3, 3, 2, 2]]


def test_round_plan_tolerates_solver_noise_just_below_an_integer():
    w = tiny_week(0, ships=1, blocks=3)
    n = w.ships[0].n
    assert L.round_plan(w, [[n - 1e-12, 1e-12 - 1e-13, 0.0]]) == [[n, 0, 0]]


def test_rounded_plan_costs_at_most_four_percent_over_the_lp_value():
    """Messreihe: Zielwert des gerundeten Plans im Mittel +0,8 %, höchstens +3,04 % (30 Wochen, λ = 20)."""
    gaps = []
    for seed in range(30):
        w = S.make_week(seed, fill=None)
        loads = scen_loads(w)
        res = L.solve(w, lam=20, scenarios=loads)
        x = L.round_plan(w, res.x)
        wait = sum(Q.evaluate(S.shifted(w, dl), x).wait for dl in S.train_scenarios(w, 3)) / 10
        gaps.append((Q.evaluate(w, x).distance + 20 * wait) / (res.distance + 20 * res.wait) - 1)
    assert min(gaps) >= -1e-9 and max(gaps) <= 0.04 and sum(gaps) / len(gaps) <= 0.02


# ---------- Löserstatus ----------
@pytest.mark.parametrize("status", [pywraplp.Solver.INFEASIBLE, pywraplp.Solver.UNBOUNDED, pywraplp.Solver.ABNORMAL, pywraplp.Solver.NOT_SOLVED, pywraplp.Solver.FEASIBLE])
def test_a_solver_without_a_proven_optimum_raises_instead_of_returning_a_plan(monkeypatch, status):
    monkeypatch.setattr(pywraplp.Solver, "Solve", lambda self, *a, **k: status)
    with pytest.raises(L.LPError, match="kein Optimum"):
        L.solve(S.make_week(1), min_wait=True)


def test_a_missing_solver_raises(monkeypatch):
    monkeypatch.setattr(pywraplp.Solver, "CreateSolver", staticmethod(lambda name: None))
    with pytest.raises(L.LPError, match="GLOP"):
        L.solve(S.make_week(1), min_wait=True)


def test_plan_exact_and_plan_hedged_return_rounded_plans_and_the_lp_result():
    w = S.make_week(2017)
    x, res = L.plan_exact(w)
    assert all(sum(row) == sh.n for row, sh in zip(x, w.ships)) and res.wait == pytest.approx(0.0, abs=1e-6)
    xh, resh = L.plan_hedged(w, 10, scen_loads(w))
    assert all(sum(row) == sh.n for row, sh in zip(xh, w.ships)) and resh.distance == pytest.approx(298.37127284040724, abs=1e-3) and resh.wait == pytest.approx(5.419885438595533, abs=1e-3)
    assert res.distance == pytest.approx(259.62402242880273, abs=1e-3)                            # Messreihe, Woche 2017 (LP nominal und Szenario-LP, λ = 10)
