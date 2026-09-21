"""Testhilfen: kleine Wochen und unabhängige, bewusst einfache Nachrechnungen (teilen keinen Code mit blz_queue, blz_rules und blz_lp)."""

import itertools
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import blz_scenario as S  # noqa: E402


def tiny_week(seed, ships=3, blocks=3, n_range=(3, 5)):
    """Kleinstinstanz zum Durchprobieren: wenige Container, Blockrate 1 je Stunde, keine Anlieferlast, keine Lagergrenze."""
    return S.make_week(seed, ships=ships, blocks=blocks, mu=1.0, crane=3, fill=None, delivery=0, n_range=n_range, span=2)


def reference_wait_and_distance(week, x):
    """Unabhängige Nachrechnung von (Weg, Wartezeit): je Block und Stunde die Last aus den Schiffsanteilen, der Rückstand als laufende Zahl. Kein Code aus blz_queue."""
    total = 0.0
    dist = 0.0
    for b in range(week.blocks):
        backlog = 0.0
        for t in range(week.hours):
            load = 0.0
            for s in range(week.n_ships):
                load += x[s][b] * (week.f[s][t] + week.h[s][t])
            backlog = backlog + load - week.mu
            if backlog < 0:
                backlog = 0.0
            total += backlog
    for s in range(week.n_ships):
        for b in range(week.blocks):
            dist += x[s][b] * week.d[s][b]
    return dist / week.total, total * 60.0 / week.total


def reference_wait_fine(week, x, sub=12):
    """Feinschritt: jede Stunde in `sub` Schritte (5 min bei 12); Rückstand am Ende jedes Schritts, Wartezeit = Summe Rückstand / sub. Prüft, ob das Stundenmodell die Wartezeit trägt."""
    total = 0.0
    for b in range(week.blocks):
        q = 0.0
        for t in range(week.hours):
            load = sum(x[s][b] * week.lf[s][t] for s in range(week.n_ships)) / sub
            for _ in range(sub):
                q = max(0.0, q + load - week.mu / sub)
                total += q / sub
    return total / week.total * 60.0


def compositions(n, k):
    """Alle Verteilungen von n Containern auf k Blöcke."""
    if k == 1:
        yield (n,)
        return
    for i in range(n + 1):
        for rest in compositions(n - i, k - 1):
            yield (i,) + rest


def brute_force_objectives(week, lams):
    """Ganzzahliges Optimum von Weg + lam * Wartezeit je lam durch vollständiges Durchprobieren aller Pläne: {lam: (Wert, Plan)}."""
    options = [list(compositions(sh.n, week.blocks)) for sh in week.ships]
    best = {lam: None for lam in lams}
    for combo in itertools.product(*options):
        d, w = reference_wait_and_distance(week, [list(c) for c in combo])
        for lam in lams:
            v = d + lam * w
            if best[lam] is None or v < best[lam][0] - 1e-12:
                best[lam] = (v, combo)
    return best


# ---------- unabhängige Fassungen der Regeln (Bestand und Last jedes Mal aus dem bisherigen Plan berechnet) ----------
def _stock(week, x, b, t):
    return sum(x[s][b] * week.g[s][t] for s in range(week.n_ships))


def _load(week, x, b, t):
    return sum(x[s][b] * week.lf[s][t] for s in range(week.n_ships))


def _fits(week, x, s, b, take):
    if week.limit is None:
        return True
    return all(_stock(week, x, b, t) + take * week.g[s][t] <= week.limit + 1e-9 for t in range(week.hours) if week.g[s][t] > 0)


def _ships_by_start(week):
    return sorted(range(week.n_ships), key=lambda s: (week.ships[s].start, s))


def _blocks_by_distance(week, s):
    return sorted(range(week.blocks), key=lambda b: (week.d[s][b], b))


def reference_rule(week, kind, check_storage=True, cap=0.8, lot=10):
    """kind: 'bundle' | 'kblocks' | 'greedy'. `check_storage=False` ist die Erstfassung der Messreihe ohne Lagerplatzprüfung (nur für den Vergleich in Tests)."""
    x = [[0] * week.blocks for _ in range(week.n_ships)]
    for s in _ships_by_start(week):
        sh = week.ships[s]
        order = _blocks_by_distance(week, s)
        left, i = sh.n, 0
        k = min(week.blocks, max(1, math.ceil(sh.n / sh.length / week.mu)))
        while left:
            take = min(lot, left)
            fitting = [b for b in order if (not check_storage) or _fits(week, x, s, b, take)]
            if kind == "bundle":
                pick = fitting[0] if fitting else order[0]
            elif kind == "kblocks":
                ring = fitting[:k] if fitting else [order[0]]
                pick = ring[i % len(ring)]
                i += 1
            else:
                cand = fitting or list(order)
                peaks = {b: max(_load(week, x, b, t) + take * week.lf[s][t] for t in range(week.hours) if week.lf[s][t] > 0) / week.mu for b in cand}
                pick = next((b for b in cand if peaks[b] <= cap + 1e-9), None)
                if pick is None:
                    pick = min(cand, key=lambda b: (round(peaks[b], 9), order.index(b)))
            x[s][pick] += take
            left -= take
    return x


def stock_over(week, x):
    """Größter Überstand über der Lagergrenze (Container), unabhängig gerechnet."""
    if week.limit is None:
        return 0.0
    return max(0.0, max(_stock(week, x, b, t) - week.limit for b in range(week.blocks) for t in range(week.hours)))
