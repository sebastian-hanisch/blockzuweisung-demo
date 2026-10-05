"""Orakel auf anderem Rechenweg: Das LP gegen scipy.optimize.linprog (HiGHS) in anderer Formulierung, der Rückstand gegen die geschlossene Form der Lindley-Rekursion.

* LP: statt q[t] >= q[t-1] + Last - mu steht für jedes Fenster [u, t] die Zeile q[t] >= Summe (Last - mu) über das Fenster (Schlange = größte Fenstersumme); anderer Löser, andere Zeilen.
* Rückstand: q[t] = Summe bis t minus kleinste Teilsumme bis t (Präfixsummen), statt der laufenden Rekursion."""
import random

import numpy as np
import pytest

import blz_lp as L
import blz_queue as Q
import blz_scenario as S

linprog = pytest.importorskip("scipy.optimize").linprog
sparse = pytest.importorskip("scipy.sparse")


def _tiny(seed):
    rng = random.Random(seed)
    return S.make_week(seed, ships=rng.randint(2, 3), blocks=rng.randint(2, 3), mu=float(rng.choice([1, 2])), crane=rng.choice([3, 6]), fill=rng.choice([None, 80]),
                       delivery=rng.choice([0, 2]), n_range=(3, 7), span=3)


def _window_lp(week, lfs, lam, min_wait):
    """Variablen x[s][b], dann q[k][b][t]; Zeile je Fenster; Ziel Wartezeit (min_wait) oder Weg + lam * Wartezeit. Rückgabe: Optimalwert."""
    Sn, B, T, K = week.n_ships, week.blocks, week.hours, len(lfs)
    nx = Sn * B
    xi = lambda s, b: s * B + b
    qi = lambda k, b, t: nx + (k * B + b) * T + t
    rows, cols, vals, rhs = [], [], [], []
    r = 0
    for k, lf in enumerate(lfs):
        for b in range(B):
            for t in range(T):
                for u in range(t + 1):
                    for v in range(u, t + 1):
                        for s in range(Sn):
                            if lf[s][v]:
                                rows.append(r), cols.append(xi(s, b)), vals.append(lf[s][v])
                    rows.append(r), cols.append(qi(k, b, t)), vals.append(-1.0)
                    rhs.append(week.mu * (t - u + 1))
                    r += 1
    if week.limit is not None:
        for b in range(B):
            for t in range(T):
                if any(week.g[s][t] > 0 for s in range(Sn)):
                    for s in range(Sn):
                        if week.g[s][t] > 0:
                            rows.append(r), cols.append(xi(s, b)), vals.append(week.g[s][t])
                    rhs.append(week.limit)
                    r += 1
    n_var = nx + K * B * T
    A = sparse.csr_matrix((vals, (rows, cols)), shape=(r, n_var))
    Aeq = sparse.lil_matrix((Sn, n_var))
    for s in range(Sn):
        for b in range(B):
            Aeq[s, xi(s, b)] = 1
    c = np.zeros(n_var)
    wait = 60.0 / week.total / K
    for k in range(K):
        for b in range(B):
            for t in range(T):
                c[qi(k, b, t)] = wait * (1.0 if min_wait else lam)
    if not min_wait:
        for s in range(Sn):
            for b in range(B):
                c[xi(s, b)] = week.d[s][b] / week.total
    res = linprog(c, A_ub=A, b_ub=np.array(rhs), A_eq=Aeq.tocsr(), b_eq=[sh.n for sh in week.ships], bounds=(0, None), method="highs")
    assert res.status == 0
    return res.fun


@pytest.mark.parametrize("seed", range(24))
def test_lp_optimum_equals_highs_with_window_rows(seed):
    week = _tiny(seed)
    sigma = random.Random(seed).choice([0, 1, 2])
    lfs = [S.shifted(week, d).lf for d in S.scenario_set(week.seed, week.n_ships, sigma, 3, 500000)]
    lam = random.Random(seed + 1).choice([2, 5, 10, 50])
    got = L.solve(week, min_wait=True, scenarios=lfs)
    assert got.wait == pytest.approx(_window_lp(week, lfs, 1, True), abs=2e-4)          # Gewicht 1e-6 des Wegs verschiebt die Wartezeit um höchstens 1e-4 min
    hedged = L.solve(week, lam=lam, scenarios=lfs)
    assert hedged.distance + lam * hedged.wait == pytest.approx(_window_lp(week, lfs, lam, False), rel=1e-6)


@pytest.mark.parametrize("seed", range(25))
def test_backlog_and_wait_equal_the_prefix_sum_closed_form(seed):
    rng = random.Random(seed)
    week = S.make_week(seed, ships=rng.randint(3, 8), blocks=rng.randint(6, 10), mu=float(rng.choice([30, 40, 60])), crane=rng.choice([60, 90, 120]), fill=rng.choice([None, 70, 90]))
    x = []
    for s in range(week.n_ships):
        w = np.array([rng.random() ** 3 for _ in range(week.blocks)])
        x.append(list(week.ships[s].n * w / w.sum()))
    load = np.array(x).T @ np.array(week.lf)
    pref = np.concatenate([np.zeros((week.blocks, 1)), np.cumsum(load - week.mu, axis=1)], axis=1)
    q = np.array([np.maximum(0.0, pref[:, t + 1] - pref[:, :t + 1].min(axis=1)) for t in range(week.hours)]).T
    m = Q.evaluate(week, x)
    assert m.wait == pytest.approx(q.sum() / week.total * 60.0, rel=1e-9)
    assert m.peak == pytest.approx(load.max() / week.mu, rel=1e-9)
    assert m.distance == pytest.approx((np.array(x) * np.array(week.d)).sum() / week.total, rel=1e-9)
