"""Tests der Auswertung: eine Woche mit allen sechs Verfahren, Reproduktion der Messreihe (Mittel über Seeds 0-19 aus sweep1.json / plan_daten.json), Kurve gegen Direktrechnungen, Kante, Stichprobe,
gepaarte Differenz, Verteilung, Urteil an seiner Schwelle, Diagnose in allen Zuständen. Schwellen stehen hart im Test, nicht aus dem Code gelesen."""

import statistics
from types import SimpleNamespace

import pytest

import blz_constants as C
import blz_evaluation as E
import blz_lp as L
import blz_queue as Q
import blz_rules as R
import blz_scenario as S

BUNDLE, SPREAD, KBLOCKS, GREEDY, LP, HEDGE = "buendeln", "verteilen", "kranrate", "gierig", "gerechnet", "abgesichert"
P = E.Params(6, 8, 40, 90, 70, 3, 10)


# ---------- Hilfen: künstliche Wochen und Zeilen ----------
def fake_res(kb_wait=0.0, kb_dist=250.0, lp_wait=0.0, lp_rw=0.0, lp_dist=250.0, hd_rw=0.0, hd_dist=250.0, hd_wait=0.0, sigma=3, lam=10, stock=None):
    stock = stock or {}
    values = {KBLOCKS: (kb_wait, 0.0, kb_dist), LP: (lp_wait, lp_rw, lp_dist), HEDGE: (hd_wait, hd_rw, hd_dist)}
    outs = []
    for key in C.METHOD_KEYS:
        wait, rw, dist = values.get(key, (0.0, 0.0, 300.0))
        outs.append(SimpleNamespace(key=key, m=SimpleNamespace(wait=wait, distance=dist, stock_over=stock.get(key, 0.0)), robust=SimpleNamespace(wait=rw)))
    return E.WeekResult(P._replace(sigma=sigma, lam=lam), 0, None, tuple(outs))


def row(seed=0, **fields):
    """WeekRow: je Verfahren ein Scalars mit Werten aus `fields` (Verfahren -> dict) über einer neutralen Grundlage."""
    m = {k: E.Scalars(300.0, 1.0, 5.0, 10.0, 0.0, 350.0) for k in C.METHOD_KEYS}
    for key, kw in fields.items():
        m[key] = m[key]._replace(**kw)
    return E.WeekRow(seed, m)


# ---------- Eine Woche, sechs Verfahren ----------
def test_run_week_returns_the_six_methods_in_order_with_whole_plans_and_consistent_metrics():
    res = E.run_week(P, 2017)
    assert [o.key for o in res.outcomes] == list(C.METHOD_KEYS) and [o.label for o in res.outcomes] == [C.METHOD_LABELS[k] for k in C.METHOD_KEYS]
    for o in res.outcomes:
        assert all(sum(row_) == sh.n and all(isinstance(v, int) for v in row_) for row_, sh in zip(o.x, res.week.ships))
        m = Q.evaluate(res.week, o.x)
        assert o.m.distance == m.distance and o.m.wait == m.wait and o.robust.wait == Q.robust_eval(res.week, o.x, S.evaluation_scenarios(res.week, 3)).wait
    assert res[LP] is res.outcomes[4] and res[HEDGE].bound is not None and res[LP].bound is not None and all(res[k].bound is None for k in (BUNDLE, SPREAD, KBLOCKS, GREEDY))


def test_run_week_reproduces_the_messreihe_for_the_shown_week_seed_2017():
    """Stoßwoche, Seed 2017: die Regeln bitgleich zur Messreihe; die Rechenpläne (gerundet) auf ihre Zielwerte, nicht auf die Aufteilung."""
    res = E.run_week(P, 2017)
    exact = {BUNDLE: (259.1261620185923, 148.09199565374857, 184.70102683062836), SPREAD: (453.18725099601596, 0.0, 4.806723466882828),
             KBLOCKS: (259.6148738379814, 20.526548352046362, 55.24732521573157), GREEDY: (341.2084993359894, 3.289905313809688, 23.218202859557426)}
    for key, (d, w, rw) in exact.items():
        assert (res[key].m.distance, res[key].m.wait, res[key].robust.wait) == pytest.approx((d, w, rw), abs=1e-9), key
    assert res[LP].m.distance == pytest.approx(259.6, abs=0.3) and res[LP].m.wait < 0.5 and 35 < res[LP].robust.wait < 65                   # Messreihe: 259,6 m, 0,0 min, bei Verspätung 50,1 min
    assert res[HEDGE].m.distance == pytest.approx(298.4, abs=1.0) and res[HEDGE].m.wait < 0.5 and 5 < res[HEDGE].robust.wait < 14          # Messreihe: 298,4 m, bei Verspätung 9,4 min


def test_run_week_is_deterministic():
    a, b = E.run_week(P, 5), E.run_week(P, 5)
    assert [o.x for o in a.outcomes[:4]] == [o.x for o in b.outcomes[:4]]
    assert [(o.m.distance, o.robust.wait) for o in a.outcomes] == [(o.m.distance, o.robust.wait) for o in b.outcomes]


def test_the_bound_of_the_exact_method_is_the_minimal_wait_and_the_rounded_plan_is_not_below_it():
    res = E.run_week(P, 2017)
    b = res[LP].bound
    assert b.objective == pytest.approx(b.lp_wait, abs=1e-12) and b.rounded == res[LP].m.wait and b.rounded >= b.objective - 1e-9
    assert b.lp_distance == pytest.approx(259.62402242880273, abs=1e-3)


def test_the_bound_of_the_hedged_method_is_weight_distance_plus_price_times_training_wait_and_the_rounding_gap_is_small():
    res = E.run_week(P, 2017)
    b = res[HEDGE].bound
    assert b.objective == pytest.approx(b.lp_distance + 10 * b.lp_wait, abs=1e-9) and b.objective == pytest.approx(298.37127284040724 + 10 * 5.419885438595533, abs=1e-3)
    train_wait = Q.robust_eval(res.week, res[HEDGE].x, S.train_scenarios(res.week, 3)).wait
    assert b.rounded == pytest.approx(res[HEDGE].m.distance + 10 * train_wait, abs=1e-9)
    assert -1e-6 <= b.gap <= 4.0                                                                       # Prozent; Messreihe: höchstens 3 %
    assert b.rounded >= b.objective - 1e-6


def test_the_bound_gap_is_none_when_the_lp_value_is_zero():
    assert E.Bound(250.0, 0.0, 0.0, 0.1).gap is None and E.Bound(250.0, 1.0, 100.0, 103.0).gap == pytest.approx(3.0, abs=1e-12)
    assert E.Bound(250.0, 0.4, 0.5, 0.51).gap == pytest.approx(2.0, abs=1e-9) and E.Bound(250.0, 0.0, 1e-8, 2e-8).gap == pytest.approx(100.0, abs=1e-6)          # ein kleiner LP-Wert (Minuten) hat einen Aufschlag


def test_price_changes_only_the_hedged_plan():
    a, b = E.run_week(P._replace(lam=2), 2017), E.run_week(P._replace(lam=50), 2017)
    for k in (BUNDLE, SPREAD, KBLOCKS, GREEDY):
        assert a[k].x == b[k].x
    assert a[LP].m.distance == pytest.approx(b[LP].m.distance, abs=1e-9)
    assert a[HEDGE].m.distance < b[HEDGE].m.distance and a[HEDGE].robust.wait > b[HEDGE].robust.wait


def test_sigma_zero_run_has_identical_shifted_and_nominal_waits():
    res = E.run_week(P._replace(sigma=0), 2017)
    for o in res.outcomes:
        assert o.robust.wait == pytest.approx(o.m.wait, abs=1e-9)


# ---------- Reproduktion der Messreihe (Seeds 0-19, keine Lagergrenze, σ = 3) ----------
@pytest.fixture(scope="module")
def messreihe_means():
    """Die Mittel der Messreihe (sweep1.json) mit dem Code der Demo nachgerechnet: Regeln und LP-Pläne UNGERUNDET wie in der Messreihe."""
    acc = {k: [] for k in ("bundle", "spread", "kblocks", "greedy", "lp", "hedge10")}
    edge = {e: [] for e in (400, 100, 20, 5, 1)}
    wmin = []
    for seed in range(20):
        w = S.make_week(seed, fill=None)
        test = S.evaluation_scenarios(w, 3)
        loads = E.training_loads(w, 3)
        lp = L.solve(w, min_wait=True)
        wmin.append(lp.wait)
        for e in edge:
            edge[e].append(L.edge_distance(w, e, lp.wait))
        plans = {"bundle": R.rule_bundle(w), "spread": R.rule_spread(w), "kblocks": R.rule_kblocks(w), "greedy": R.rule_greedy(w), "lp": lp.x, "hedge10": L.solve(w, lam=10, scenarios=loads).x}
        for k, x in plans.items():
            m = Q.evaluate(w, x)
            acc[k].append((m.distance, m.wait, Q.robust_eval(w, x, test).wait))
    means = {k: tuple(statistics.fmean(v[i] for v in vals) for i in range(3)) for k, vals in acc.items()}
    return means, {e: statistics.fmean(v) for e, v in edge.items()}, statistics.fmean(wmin)


def test_the_edge_numbers_of_the_messreihe_are_reproduced(messreihe_means):
    """plan_daten.json: kürzester Weg unter erlaubter Wartezeit (20 Wochen): 239,5 / 250,6 / 257,3 / 261,4 / 263,8 m bei 400 / 100 / 20 / 5 / 1 min; kleinstmögliche Wartezeit 0,50 min."""
    _, edge, wmin = messreihe_means
    assert edge[400] == pytest.approx(239.548, abs=0.05) and edge[100] == pytest.approx(250.624, abs=0.05) and edge[20] == pytest.approx(257.283, abs=0.05)
    assert edge[5] == pytest.approx(261.430, abs=0.05) and edge[1] == pytest.approx(263.799, abs=0.05) and wmin == pytest.approx(0.5026, abs=0.01)
    assert list(edge.values()) == sorted(edge.values())                                                # weniger erlaubte Wartezeit: längerer Weg


def test_the_rule_means_of_the_messreihe_are_reproduced_exactly(messreihe_means):
    """ERGEBNIS.md, Befund 1 und 3 (Mittel über 20 Wochen): Bündeln 228,2 m und 1907 min; Verteilen 457,3 m und 0,50 min; Kranrate passend 263,4 m, 43,9 min, bei Verspätung 72,8 min."""
    means, _, _ = messreihe_means
    assert means["bundle"] == pytest.approx((228.153, 1906.92, 1912.425), abs=1e-2)
    assert means["spread"] == pytest.approx((457.343, 0.503, 4.03), abs=1e-2)
    assert means["kblocks"] == pytest.approx((263.439, 43.935, 72.845), abs=1e-2)
    assert means["greedy"] == pytest.approx((347.093, 9.089, 27.831), abs=1e-2)


def test_the_price_of_hedging_of_the_messreihe_is_reproduced(messreihe_means):
    """Der wartefreie Plan: 264,2 m, 0,50 min, bei Verspätung 46,0 min; abgesichert (λ = 10): 308,0 m, bei Verspätung 9,5 min. Zielwerte eng, die von der Aufteilung abhängige Wartezeit bei Verspätung mit Abstand."""
    means, _, _ = messreihe_means
    lp, hd = means["lp"], means["hedge10"]
    assert lp[0] == pytest.approx(264.185, abs=0.05) and lp[1] == pytest.approx(0.503, abs=0.02) and 40 < lp[2] < 52
    assert hd[0] == pytest.approx(307.959, abs=1.0) and hd[1] < 1.0 and 6 < hd[2] < 13
    assert 35 < hd[0] - lp[0] < 55 and hd[2] < 0.35 * lp[2]                                             # +44 m (+17 %) bringen die Wartezeit bei Verspätung auf etwa ein Fünftel
    assert lp[0] <= means["kblocks"][0] + 2 and lp[1] < means["kblocks"][1] / 20


def test_without_delivery_load_the_simple_rule_hits_the_lp_in_30_of_30_weeks_and_with_it_in_none():
    """Befund 2: ohne Anlieferlast trifft "nächster Block mit Luft" (Gierig, 100 %) den Rechenplan (Weg und Wartezeit) in 30 von 30 Wochen; mit ihr (36 h) in 0 von 30 (Weg im Mittel +23 %, Wartezeit 35 gegen 0,3 min)."""
    def hits(delivery):
        n_hit, gaps, w_rule, w_lp = 0, [], [], []
        for seed in range(30):
            w = S.make_week(seed, fill=None, delivery=delivery)
            lp = L.solve(w, min_wait=True)
            m = Q.evaluate(w, R.rule_greedy(w, cap=1.0))
            n_hit += m.wait <= lp.wait + 1e-6 and m.distance <= lp.distance * 1.005
            gaps.append(m.distance / lp.distance - 1)
            w_rule.append(m.wait)
            w_lp.append(lp.wait)
        return n_hit, statistics.fmean(gaps), statistics.fmean(w_rule), statistics.fmean(w_lp)
    n0, gap0, _, _ = hits(0)
    n36, gap36, wr36, wl36 = hits(C.DELIVERY_HOURS)
    assert n0 == 30 and gap0 < 1e-9
    assert n36 == 0 and 0.20 < gap36 < 0.26 and 30 < wr36 < 40 and wl36 == pytest.approx(0.335, abs=0.05)


# ---------- Kurve und Kante gegen Direktrechnungen ----------
@pytest.fixture(scope="module")
def curve_2017():
    res = E.run_week(P, 2017)
    return res, E.price_curve(P, 2017, res)


def test_every_curve_point_is_a_direct_lp_call(curve_2017):
    res, curve = curve_2017
    w = res.week
    test = S.evaluation_scenarios(w, 3)
    loads = E.training_loads(w, 3)
    assert [pt.lam for pt in curve.points] == [1, 2, 5, 10, 20, 50, 100]
    for lam in (2, 20, 100):
        pt = next(pt for pt in curve.points if pt.lam == lam)
        x = L.round_plan(w, L.solve(w, lam=lam, scenarios=loads).x)
        m = Q.evaluate(w, x)
        assert (pt.distance, pt.wait, pt.wait_shift) == pytest.approx((m.distance, m.wait, Q.robust_eval(w, x, test).wait), abs=1e-9)


def test_the_curve_point_at_the_set_price_is_the_hedged_outcome_of_the_week(curve_2017):
    res, curve = curve_2017
    pt = next(pt for pt in curve.points if pt.lam == 10)
    assert pt.distance == pytest.approx(res[HEDGE].m.distance, abs=1e-9) and pt.wait_shift == pytest.approx(res[HEDGE].robust.wait, abs=1e-9)


def test_the_curve_trades_distance_for_wait_and_the_price_of_hedging_is_visible(curve_2017):
    res, curve = curve_2017
    d = [pt.distance for pt in curve.points]
    assert all(a <= b + 0.5 for a, b in zip(d, d[1:]))                                                 # höherer Preis: nie deutlich kürzerer Weg (Rundung 0,5 m)
    assert curve.points[-1].wait_shift < curve.points[0].wait_shift and curve.points[-1].distance > curve.points[0].distance + 40
    assert curve.points[3].wait_shift < 0.4 * res[LP].robust.wait                                       # λ = 10: gut ein Fünftel bis ein Drittel des wartefreien Plans


def test_the_curve_minimum_wait_is_the_lp_value_also_when_it_is_above_the_smallest_allowed_wait():
    """Starke Kräne, Woche 2017: der Rechenplan wartet pünktlich mindestens 1,7 min: die Kante darf nicht unter dieser Grenze rechnen (das LP wäre unzulässig)."""
    p = E.Params(5, 8, 40, 120, 70, 3, 10)
    res = E.run_week(p, 2017)
    curve = E.price_curve(p, 2017, res)
    assert curve.min_wait == pytest.approx(res[LP].bound.lp_wait, abs=1e-9) and curve.min_wait > 1.5
    assert [d for _, d in curve.edge] == sorted(d for _, d in curve.edge) and curve.edge[-1][1] == pytest.approx(L.edge_distance(res.week, 1, curve.min_wait), abs=1e-9)


def test_the_edge_of_the_week_is_monotone_and_starts_near_the_nearest_block_plan(curve_2017):
    res, curve = curve_2017
    eps = [e for e, _ in curve.edge]
    dist = [dd for _, dd in curve.edge]
    assert eps == [400, 200, 100, 50, 20, 10, 5, 2, 1] and dist == sorted(dist)
    assert curve.min_wait == pytest.approx(res[LP].bound.lp_wait, abs=1e-9)
    assert curve.bundle_distance == res[BUNDLE].m.distance and curve.spread_distance == res[SPREAD].m.distance
    assert dist[-1] < curve.spread_distance - 100 and dist[0] > 225                                     # ein Minutchen Wartezeit kostet weit weniger als Verteilen
    assert L.edge_distance(res.week, 100, curve.min_wait) == pytest.approx(dist[2], abs=1e-9)


# ---------- Stichprobe ----------
def test_week_row_and_sample_use_the_seeds_from_base_and_reduce_to_scalars():
    r = E.week_row(P, 2017)
    res = E.run_week(P, 2017)
    assert r.seed == 2017 and set(r.m) == set(C.METHOD_KEYS)
    for o in res.outcomes:
        s = r.m[o.key]
        assert (s.distance, s.wait, s.wait_shift, s.delay_max, s.stock_over) == (o.m.distance, o.m.wait, o.robust.wait, o.m.delay_max, o.m.stock_over) and s.cost == s.distance + 10 * s.wait_shift
    rows = E.sample(P, 2, 3000)
    assert [x.seed for x in rows] == [3000, 3001] and rows[0].m[KBLOCKS].distance == E.week_row(P, 3000).m[KBLOCKS].distance


def test_the_sample_defaults_are_twenty_weeks_from_seed_3000_and_not_the_shown_week():
    assert C.SAMPLE_WEEKS == 20 and C.SAMPLE_BASE == 3000 and not (3000 <= C.SEED_DEFAULT < 3020)


def test_percentile_is_the_rank_without_interpolation_and_spread_of_is_median_and_p10_p90():
    v = [float(i) for i in range(1, 21)]
    assert E.percentile(v, 0.10) == 3.0 and E.percentile(v, 0.90) == 19.0 and E.percentile(v, 1.0) == 20.0 and E.percentile(list(reversed(v)), 0.5) == 11.0
    rows = tuple(row(i, **{KBLOCKS: dict(wait=float(i + 1))}) for i in range(20))
    assert E.spread_of(rows, KBLOCKS, "wait") == (10.5, 3.0, 19.0) and E.median_of(rows, KBLOCKS, "wait") == 10.5 and E.mean_of(rows, KBLOCKS, "wait") == 10.5


def test_paired_is_method_minus_reference_and_median_diff_is_its_median():
    rows = (row(0, **{HEDGE: dict(distance=310.0), LP: dict(distance=270.0)}), row(1, **{HEDGE: dict(distance=290.0), LP: dict(distance=270.0)}), row(2, **{HEDGE: dict(distance=305.0), LP: dict(distance=280.0)}))
    assert E.paired(rows, HEDGE, LP, "distance") == [40.0, 20.0, 25.0] and E.median_diff(rows, HEDGE, LP, "distance") == 25.0


# ---------- Verteilung und Urteil ----------
def test_distribution_counts_better_equal_and_worse_weeks_and_the_gain():
    rows = tuple(row(i, **{HEDGE: dict(wait_shift=w), LP: dict(wait_shift=10.0)}) for i, w in enumerate([5.0, 5.0, 10.0, 15.0]))
    d = E.distribution(rows, HEDGE, LP, "wait_shift")
    assert (d.better, d.equal, d.worse, d.n) == (0.5, 0.25, 0.25, 4) and d.mean_gain == pytest.approx(1.25) and d.median_gain == pytest.approx(2.5) and d.key == HEDGE and d.field == "wait_shift"


def test_distribution_treats_differences_below_the_tolerance_as_equal():
    rows = tuple(row(i, **{HEDGE: dict(wait_shift=10.0 + 1e-12), LP: dict(wait_shift=10.0)}) for i in range(4))
    assert E.distribution(rows, HEDGE, LP, "wait_shift").equal == 1.0
    assert E.distribution(rows, HEDGE, LP, "wait_shift", tol=1e-15).worse == 1.0


def alternating(mean_diff, half_width, n=10):
    """Wochen, in denen die Differenz Verfahren minus Referenz abwechselnd mean_diff +- half_width beträgt (Standardfehler = half_width / 3 bei n = 10)."""
    return tuple(row(i, **{HEDGE: dict(wait_shift=100.0 + mean_diff + (half_width if i % 2 else -half_width)), LP: dict(wait_shift=100.0)}) for i in range(n))


def test_verdict_is_better_worse_or_unclear_and_flips_at_two_standard_errors():
    """Differenz -2 min je Woche, Standardfehler 1,01 (Verhältnis 1,98: unklar) gegen 0,99 (2,02: klar besser); dasselbe mit umgekehrtem Vorzeichen."""
    clear = E.verdict(alternating(-2.0, 2.97), HEDGE, LP, "wait_shift")
    assert clear.kind == "better" and clear.diff == pytest.approx(-2.0) and clear.se == pytest.approx(0.99, abs=0.01) and clear.n == 10 and clear.pct == pytest.approx(-2.0)
    assert E.verdict(alternating(-2.0, 3.03), HEDGE, LP, "wait_shift").kind == "unclear"
    assert E.verdict(alternating(2.0, 2.97), HEDGE, LP, "wait_shift").kind == "worse" and E.verdict(alternating(2.0, 3.03), HEDGE, LP, "wait_shift").kind == "unclear"


def test_verdict_without_spread_is_decided_by_the_sign_and_zero_is_unclear():
    same = tuple(row(i, **{HEDGE: dict(wait_shift=5.0), LP: dict(wait_shift=5.0)}) for i in range(5))
    assert E.verdict(same, HEDGE, LP, "wait_shift").kind == "unclear"
    lower = tuple(row(i, **{HEDGE: dict(wait_shift=4.0), LP: dict(wait_shift=5.0)}) for i in range(5))
    higher = tuple(row(i, **{HEDGE: dict(wait_shift=6.0), LP: dict(wait_shift=5.0)}) for i in range(5))
    assert E.verdict(lower, HEDGE, LP, "wait_shift").kind == "better" and E.verdict(higher, HEDGE, LP, "wait_shift").kind == "worse"


def test_verdict_percentage_is_none_when_the_reference_is_zero():
    rows = tuple(row(i, **{HEDGE: dict(wait_shift=2.0), LP: dict(wait_shift=0.0)}) for i in range(4))
    assert E.verdict(rows, HEDGE, LP, "wait_shift").pct is None


def test_verdict_text_has_three_states_with_the_shares_and_signs():
    better = tuple(row(i, **{HEDGE: dict(wait_shift=2.0), LP: dict(wait_shift=10.0)}) for i in range(6))
    kind, text = E.verdict_text(better, "Abgesichert gegen Gerechnet", HEDGE, LP, "wait_shift", "Wartezeit", "min")
    assert kind == "better" and "**80 % weniger**" in text and "-8.00 min je Woche" in text and "In **0 %** der Wochen ist es umgekehrt." in text and text.count("(") == text.count(")")
    kind, text = E.verdict_text(better, "Umgekehrt", LP, HEDGE, "wait_shift", "Wartezeit", "min")
    assert kind == "worse" and "**400 % mehr**" in text and "+8.00 min je Woche" in text and "In **0 %** der Wochen ist es besser." in text
    zero_ref = tuple(row(i, **{HEDGE: dict(wait_shift=2.0), LP: dict(wait_shift=0.0)}) for i in range(4))
    below_zero = tuple(row(i, **{HEDGE: dict(wait_shift=-2.0), LP: dict(wait_shift=0.0)}) for i in range(4))
    assert "**2.00 min mehr**" in E.verdict_text(zero_ref, "X", HEDGE, LP, "wait_shift", "Wartezeit", "min")[1] and "**2.00 min weniger**" in E.verdict_text(below_zero, "X", HEDGE, LP, "wait_shift", "Wartezeit", "min")[1]
    kind, text = E.verdict_text(alternating(-2.0, 3.03), "Y", HEDGE, LP, "wait_shift", "Wartezeit", "min")
    assert kind == "unclear" and text.startswith("Kein klarer Unterschied bei **Y**") and "Rauschens" in text and "gemittelt über die Wochen" in text and "(-2.00 min Wartezeit" in text


def test_verdict_specs_name_the_three_comparisons_and_the_price():
    specs = E.verdict_specs(20)
    assert [s[1:] for s in specs] == [(HEDGE, LP, "wait_shift", "Wartezeit", "min"), (LP, KBLOCKS, "wait", "Wartezeit", "min"), (HEDGE, GREEDY, "cost", "Zielwert", "m")]
    assert "λ" not in specs[2][0] and "20 · Wartezeit bei Verspätung" in specs[2][0] and specs[0][0].startswith("Abgesichert gegen Gerechnet")


def test_signed_never_shows_minus_zero():
    assert E.signed(-0.4) == "+0" and E.signed(0.4) == "+0" and E.signed(-0.6) == "-1" and E.signed(2.5) == "+2" and E.signed(-0.04, 1) == "+0.0" and E.signed(-1.26, 1) == "-1.3" and E.signed(0.0, 2) == "+0.00"


# ---------- Diagnose ----------
def test_diagnose_calm_needs_both_the_rule_and_the_calculated_plan_under_two_minutes():
    assert E.diagnose(fake_res(kb_wait=0.0, lp_rw=0.5)).kind == "calm" and E.diagnose(fake_res(kb_wait=1.99, lp_rw=1.99)).kind == "calm"
    assert E.diagnose(fake_res(kb_wait=2.0, lp_rw=0.5)).kind != "calm" and E.diagnose(fake_res(kb_wait=0.5, lp_rw=2.0)).kind != "calm"


def test_diagnose_sigma_zero_comes_after_calm_and_before_the_rest():
    assert E.diagnose(fake_res(kb_wait=30.0, lp_rw=0.4, sigma=0)).kind == "sigma0"
    assert E.diagnose(fake_res(kb_wait=0.0, lp_rw=0.0, sigma=0)).kind == "calm"
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=0.1, lp_rw=0.1, hd_rw=0.05, sigma=1)).kind == "robust"                    # σ = 1 h ist noch eine Verspätung: nicht die σ = 0-Meldung
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=5.0, lp_rw=9.0, sigma=0)).kind == "sigma0"


def test_diagnose_overload_when_even_the_calculated_plan_waits_three_minutes():
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=3.0, lp_rw=40.0)).kind == "overload"
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=2.99, lp_rw=40.0, hd_rw=5.0)).kind == "hedge"


def test_diagnose_fragile_and_robust_flip_at_five_times_the_punctual_wait():
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=0.5, lp_rw=5.0, hd_rw=1.0)).kind == "hedge"          # 5,0 = fünffache Basis (mindestens 1 min: hier 1,0 * 5)
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=0.5, lp_rw=4.99, hd_rw=1.0)).kind == "robust"
    assert E.diagnose(fake_res(kb_wait=30.0, lp_wait=1.5, lp_rw=7.5, hd_rw=1.0)).kind == "hedge" and E.diagnose(fake_res(kb_wait=30.0, lp_wait=1.5, lp_rw=7.4, hd_rw=1.0)).kind == "robust"


def test_diagnose_hedge_versus_fragile_flips_at_sixty_percent():
    assert E.diagnose(fake_res(kb_wait=30.0, lp_rw=10.0, hd_rw=6.0)).kind == "hedge"
    assert E.diagnose(fake_res(kb_wait=30.0, lp_rw=10.0, hd_rw=6.01)).kind == "fragile"


def test_diagnose_reports_the_extra_distance_and_the_storage_violations():
    d = E.diagnose(fake_res(kb_wait=30.0, lp_rw=10.0, hd_rw=3.0, lp_dist=260.0, hd_dist=299.0, stock={BUNDLE: 177.2, KBLOCKS: 1.5, GREEDY: 1.6, HEDGE: 1.0}))
    assert d.extra == pytest.approx(39.0) and d.extra_pct == pytest.approx(15.0) and d.hedge_distance == 299.0 and d.lp_distance == 260.0
    assert d.stock == ((BUNDLE, 177.2), (GREEDY, 1.6))                                                   # 1,5 gilt noch nicht als verletzt (Rundung), 1,6 schon
    assert E.diagnose(fake_res()).stock == ()


def test_diagnosis_text_states_the_numbers_of_each_kind():
    p = P
    hedge = E.diagnose(fake_res(kb_wait=30.0, lp_wait=0.1, lp_rw=50.1, hd_rw=9.4, lp_dist=259.6, hd_dist=298.4))
    t = E.diagnosis_text(hedge, p)
    assert hedge.kind == "hedge" and "zerbricht" in t and "pünktlich 0.1 min" in t and "bei Verspätung 50.1 min" in t and "λ = 10 m je min" in t and "kostet 39 m Fahrweg (+15 %)" in t and "auf 9.4 min" in t
    fragile = E.diagnose(fake_res(kb_wait=30.0, lp_wait=1.8, lp_rw=37.4, hd_rw=30.0, lp_dist=268.0, hd_dist=321.0))
    t = E.diagnosis_text(fragile, p)
    assert fragile.kind == "fragile" and "zerbrechlich" in t and "nur auf 30.0 min (+53 m Fahrweg)" in t and "ein höherer Preis sichert stärker" in t
    calm = E.diagnose(fake_res(kb_wait=0.0, lp_rw=0.1, kb_dist=252.6, lp_dist=246.0, hd_dist=246.0))
    t = E.diagnosis_text(calm, p)
    assert "Ruhige Woche" in t and "246 statt 253 m" in t and "Absichern kostet 0.0 m" in t and "Kranrate passend wartet 0.0 min" in t
    overload = E.diagnose(fake_res(kb_wait=80.0, lp_wait=15.0, lp_rw=40.0, hd_rw=30.0, lp_dist=270.0, hd_dist=330.0))
    t = E.diagnosis_text(overload, p)
    assert overload.kind == "overload" and "zu knapp" in t and "wartet pünktlich 15.0 min" in t and "(bei Verspätung 40.0 min)" in t and "+60 m Fahrweg" in t
    sigma0 = E.diagnose(fake_res(kb_wait=30.0, lp_wait=0.1, lp_rw=0.1, hd_wait=0.02, sigma=0, lp_dist=259.6, hd_dist=261.0))
    t = E.diagnosis_text(sigma0, P._replace(sigma=0))
    assert sigma0.kind == "sigma0" and "σ = 0" in t and "261.0 gegen 259.6 m Fahrweg" in t and "0.02 gegen 0.10 min Wartezeit" in t and "sichert er nichts ab" in t
    robust = E.diagnose(fake_res(kb_wait=30.0, lp_wait=1.0, lp_rw=3.0, hd_rw=2.5, lp_dist=260.0, hd_dist=270.0))
    t = E.diagnosis_text(robust, p)
    assert robust.kind == "robust" and "hält die Verspätung aus" in t and "1.0 min pünktlich, 3.0 min bei Verspätung" in t and "kostet 10 m Fahrweg" in t and "nur 2.5 min" in t


def test_stock_text_names_the_violators_and_whether_a_calculated_plan_is_among_them():
    assert E.stock_text(E.diagnose(fake_res())) == ""
    d = E.diagnose(fake_res(stock={BUNDLE: 177.2, KBLOCKS: 20.4}))
    t = E.stock_text(d)
    assert t == "Lagergrenze verletzt: Bündeln um 177 Container, Kranrate passend um 20 Container. Die Rechenpläne halten sie ein."
    assert "Auch ein Rechenplan überschreitet sie" in E.stock_text(E.diagnose(fake_res(stock={LP: 2.0})))


def test_diagnosis_of_real_weeks_matches_the_stories_of_the_presets():
    kinds = {}
    for name, pr in C.PRESETS.items():
        p = E.Params(pr["ships"], pr["blocks"], pr["mu"], pr["crane"], pr["fill"], pr["sigma"], pr["lam"])
        kinds[name] = E.diagnose(E.run_week(p, pr["seed"]))
    assert kinds["Stoßwoche"].kind == kinds["Späte Schiffe"].kind == kinds["Voller Platz"].kind == kinds["Starke Kräne"].kind == "hedge" and kinds["Ruhige Woche"].kind == "calm"
    assert [k for k, _ in kinds["Voller Platz"].stock] == [BUNDLE] and all(d.stock == () for n, d in kinds.items() if n != "Voller Platz")
