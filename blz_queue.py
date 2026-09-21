"""Rückstands-Rekursion und Kennzahlen eines Plans (unabhängig vom Löser).

Der Plan x[s][b] ist die Zahl der Container von Schiff s in Block b. Block b hat in Stunde t die Last load[b][t] = Summe_s x[s][b] * lf[s][t] (Abrufe plus Anlieferungen, ein Move je Container) und
bedient höchstens mu Moves je Stunde; der Rest wartet als Rückstand q (Flüssigkeit, FIFO): q[b][t] = max(0, q[b][t-1] + load[b][t] - mu). Wartezeit W = Summe q * 1 h / N in Minuten (mittlere
Wartezeit je Container am Block). Wie evaluate() der Messreihe (blz.py)."""

import math
import statistics
from dataclasses import dataclass

import blz_scenario as S


def backlog(week, x):
    """(Last, Rückstand) je Block und Stunde: zwei Listen [b][t]."""
    load = [[sum(x[s][b] * week.lf[s][t] for s in range(week.n_ships)) for t in range(week.hours)] for b in range(week.blocks)]
    q = []
    for b in range(week.blocks):
        prev, row = 0.0, []
        for t in range(week.hours):
            prev = max(0.0, prev + load[b][t] - week.mu)
            row.append(prev)
        q.append(row)
    return load, q


@dataclass(frozen=True, eq=False)
class Metrics:
    distance: float          # mittlerer Fahrweg je Container (m)
    wait: float              # mittlere Wartezeit je Container am Block (min)
    peak: float              # größte Blocklast in Anteilen der Rate (1 = Block voll ausgelastet)
    stock_over: float        # größter Überstand über der Lagergrenze (Container; 0 ohne Grenze)
    fill: float              # größter Bestand in Anteilen der Lagergrenze (0 ohne Grenze)
    delay_max: float         # größter Beladeverzug eines Schiffs (min): Rückstand am Ende des Fensters durch die Blockrate
    delays: tuple            # Beladeverzug je Schiff (min)
    load: tuple              # Last je Block und Stunde (Moves)


def evaluate(week, x):
    S_, B, T, mu = week.n_ships, week.blocks, week.hours, week.mu
    N = week.total
    distance = sum(x[s][b] * week.d[s][b] for s in range(S_) for b in range(B)) / N
    load, q = backlog(week, x)
    peak = max(max(row) for row in load) / mu
    wait = sum(q[b][t] for b in range(B) for t in range(T)) / N * 60.0
    delays = []
    for s, sh in enumerate(week.ships):
        te = min(T - 1, sh.start + sh.length - 1)
        used = [b for b in range(B) if x[s][b] > 0]
        delays.append(max(q[b][te] for b in used) / mu * 60.0 if used else 0.0)
    stock_over, fill = 0.0, 0.0
    if week.limit is not None:
        for b in range(B):
            for t in range(T):
                stock = sum(x[s][b] * week.g[s][t] for s in range(S_))
                fill = max(fill, stock / week.limit)
                stock_over = max(stock_over, stock - week.limit)
    return Metrics(distance, wait, peak, max(0.0, stock_over), fill, max(delays), tuple(delays), tuple(tuple(r) for r in load))


@dataclass(frozen=True)
class Robust:
    wait: float              # mittlere Wartezeit über die Testszenarien (min)
    wait95: float            # 95. Perzentil der mittleren Wartezeit über die Szenarien
    delay_max: float         # mittlerer größter Beladeverzug (min)
    waits: tuple             # Wartezeit je Szenario


def robust_eval(week, x, scenarios):
    """Der Plan x bei verschobenen Beladefenstern: mittlere Wartezeit über die Szenarien (Wartezeit "bei Verspätung"), ihr 95. Perzentil und der mittlere größte Beladeverzug."""
    waits, delays = [], []
    for dl in scenarios:
        m = evaluate(S.shifted(week, dl), x)
        waits.append(m.wait)
        delays.append(m.delay_max)
    ordered = sorted(waits)
    return Robust(statistics.mean(waits), ordered[min(len(ordered) - 1, int(math.ceil(0.95 * len(ordered))) - 1)], statistics.mean(delays), tuple(waits))
