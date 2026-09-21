"""Die beiden Rechenverfahren: lineares Programm (OR-Tools GLOP) über die ganze Woche.

Variablen x[s][b] >= 0 (Container von Schiff s in Block b, Summe je Schiff = n_s) und q[k][b][t] >= 0 (Rückstand im Szenario k) mit q[k][b][t] >= q[k][b][t-1] + Summe_s lf_k[s][t] x[s][b] - mu.
Minimieren zwingt q auf das Maximum der Rückstands-Rekursion (Konvexität): der Zielwert des LP ist exakt die Wartezeit der Simulation (blz_queue). Lagergrenze je Block und Stunde hart.

- "Gerechnet": ein Szenario (pünktlich), Ziel Wartezeit, zweitrangig (Gewicht 1e-6) der Weg: lexikographisch, damit der Zielwert eindeutig ist.
- "Gerechnet und abgesichert": Szenario-LP mit den Planungsszenarien, Ziel Weg + lam mal mittlere Wartezeit über die Szenarien (lam in m je min).
- Kante: kürzester Weg unter erlaubter Wartezeit eps (pünktlich).
Variablen in Einheiten zu 100 Containern (Korrektur 2 der Messreihe: ohne Skalierung meldete GLOP mit Lagerzeilen fälschlich INFEASIBLE oder ABNORMAL). Kein Zeitlimit: das Optimum ist bewiesen, der
Zielwert hängt nicht vom Rechner ab (bei mehreren gleichwertigen Plänen kann die Aufteilung zwischen Löserversionen abweichen)."""

import math
from dataclasses import dataclass

from ortools.linear_solver import pywraplp

import blz_constants as C


class LPError(RuntimeError):
    """Der Löser fand kein Optimum (Status statt eines Plans; die App zeigt nie einen leeren Plan)."""


@dataclass(frozen=True)
class LPResult:
    x: list                  # Plan in Containern (Bruchteile möglich)
    distance: float          # Weg des LP-Plans (m je Container)
    wait: float              # mittlere Wartezeit des LP-Plans über die Szenarien (min je Container)


def solve(week, lam=None, eps_wait=None, min_wait=False, scenarios=None):
    """`min_wait`: minimiere die Wartezeit (zweitrangig der Weg). Sonst minimiere den Weg plus `lam` mal Wartezeit über `scenarios` (Liste von Lastanteilen lf); mit `eps_wait` zusätzlich Wartezeit <= eps.
    `scenarios` ohne Angabe: die pünktliche Woche. Rückgabe LPResult; kein Optimum: LPError."""
    S_, B, T = week.n_ships, week.blocks, week.hours
    scale = C.LP_SCALE
    lfs = scenarios or [week.lf]
    sv = pywraplp.Solver.CreateSolver("GLOP")
    if sv is None:
        raise LPError("Der Löser GLOP steht nicht zur Verfügung.")
    inf = sv.infinity()
    x = [[sv.NumVar(0, inf, "") for _ in range(B)] for _ in range(S_)]
    q = [[[sv.NumVar(0, inf, "") for _ in range(T)] for _ in range(B)] for _ in lfs]
    for s in range(S_):
        c = sv.Constraint(week.ships[s].n / scale, week.ships[s].n / scale)
        for b in range(B):
            c.SetCoefficient(x[s][b], 1)
    for k, lf in enumerate(lfs):
        for b in range(B):
            for t in range(T):
                c = sv.Constraint(-inf, week.mu / scale)
                for s in range(S_):
                    if lf[s][t]:
                        c.SetCoefficient(x[s][b], lf[s][t])
                if t:
                    c.SetCoefficient(q[k][b][t - 1], 1)
                c.SetCoefficient(q[k][b][t], -1)
    if week.limit is not None:
        for b in range(B):
            for t in range(T):
                if any(week.g[s][t] > 0 for s in range(S_)):
                    c = sv.Constraint(-inf, week.limit / scale)
                    for s in range(S_):
                        if week.g[s][t] > 0:
                            c.SetCoefficient(x[s][b], week.g[s][t])
    dist_terms = [(x[s][b], week.d[s][b] / week.total * scale) for s in range(S_) for b in range(B)]
    wait_terms = [(q[k][b][t], 60.0 / week.total / len(lfs) * scale) for k in range(len(lfs)) for b in range(B) for t in range(T)]
    if eps_wait is not None:
        c = sv.Constraint(-inf, eps_wait)
        for v, coef in wait_terms:
            c.SetCoefficient(v, coef)
    obj = sv.Objective()
    if min_wait:
        for v, coef in wait_terms:
            obj.SetCoefficient(v, coef)
        for v, coef in dist_terms:
            obj.SetCoefficient(v, C.WAIT_TIEBREAK * coef)
    else:
        for v, coef in dist_terms:
            obj.SetCoefficient(v, coef)
        for v, coef in wait_terms:
            obj.SetCoefficient(v, (lam if lam else C.WAIT_TIEBREAK) * coef)
    obj.SetMinimization()
    status = sv.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        raise LPError(f"Der Löser meldet kein Optimum (Status {status}).")
    plan = [[x[s][b].solution_value() * scale for b in range(B)] for s in range(S_)]
    return LPResult(plan, sum(v.solution_value() * coef for v, coef in dist_terms), sum(v.solution_value() * coef for v, coef in wait_terms))


def round_plan(week, plan):
    """LP-Plan auf ganze Container: je Schiff die Verteilung der größten Reste (Gleichstand: kleiner Index). Der LP-Wert bleibt Schranke; der gerundete Plan liegt im Zielwert im Mittel 0,8 %,
    höchstens 3 % darüber (Messreihe)."""
    out = []
    for s in range(week.n_ships):
        xs = plan[s]
        base = [int(math.floor(v + 1e-9)) for v in xs]
        rest = week.ships[s].n - sum(base)
        order = sorted(range(len(xs)), key=lambda i: (-(xs[i] - base[i]), i))
        for i in order[:rest]:
            base[i] += 1
        out.append(base)
    return out


def plan_exact(week):
    """Gerechnet: gerundeter Plan der minimalen Wartezeit für pünktliche Schiffe; dazu das LP-Ergebnis (Schranke)."""
    res = solve(week, min_wait=True)
    return round_plan(week, res.x), res


def plan_hedged(week, lam, scenario_lfs):
    """Gerechnet und abgesichert: gerundeter Plan des Szenario-LP mit Preis `lam` (m je min); dazu das LP-Ergebnis (Schranke)."""
    res = solve(week, lam=lam, scenarios=scenario_lfs)
    return round_plan(week, res.x), res


def edge_distance(week, eps, min_wait):
    """Kürzester Weg (LP, ungerundet) bei erlaubter Wartezeit `eps` (min): mindestens die kleinstmögliche Wartezeit `min_wait` plus 1e-6, sonst wäre das LP unzulässig."""
    return solve(week, eps_wait=max(eps, min_wait + 1e-6)).distance
