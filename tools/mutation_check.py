"""Fehler-Einbau-Test: baut einzelne Fehler in die Module ein und prüft, ob die Tests (ohne AppTests) sie finden.

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/mutation_check.py [Teilstring des Dateinamens] [--jobs N] [--indices 60,68,96-230] [--with-app] [--dry-run]
Jeder Mutant ersetzt genau eine Stelle; Überlebende sind entweder gleichwertig (kein sichtbarer Unterschied) oder eine Lücke der Tests. Die Kopie liegt je Mutant in einem temporären Ordner;
PYTHONDONTWRITEBYTECODE=1, damit veralteter Bytecode keine Überlebenden vortäuscht; Quelltexte als LF (Windows-Python schreibt sonst CRLF und die Zeichenketten unten finden nichts).
Ein Mutant kann in eine Endlosschleife laufen; nach TIMEOUT Sekunden gilt er als gefunden. Mutanten laufen parallel (--jobs, Standard 6); die schnellen Testdateien zuerst, `-x` bricht beim ersten Fehler ab.
`--with-app` nimmt die AppTests hinzu (für Mutanten, die nur die Darstellung betreffen, zum Beispiel die Referenz der Deltas). `--dry-run` prüft nur, ob jede Zeichenkette genau einmal vorkommt."""
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
WITH_APP = "--with-app" in sys.argv
TIMEOUT = 600                      # Sekunden je Mutant (parallel unter Last: ein überlebender Mutant braucht die ganze Suite, rund 4 min); Endlosschleifen zählen als gefunden
TEST_ORDER = ["test_stories.py", "test_presets.py", "test_scenario.py", "test_queue.py", "test_visualization.py", "test_pdf_export.py", "test_rules.py", "test_evaluation.py", "test_lp.py",
              "test_preset_stories.py"]

MUTANTS = [
    # blz_scenario.py
    ("blz_scenario.py", "arrivals = sorted(rng.randrange(0, span + 1) for _ in range(ships))", "arrivals = sorted(rng.randrange(0, span) for _ in range(ships))"),
    ("blz_scenario.py", "k = min(range(C.BERTHS), key=lambda j: (free[j], j))", "k = min(range(C.BERTHS), key=lambda j: (free[j], -j))"),
    ("blz_scenario.py", "start = max(arrivals[s], free[k])", "start = min(arrivals[s], free[k])"),
    ("blz_scenario.py", "free[k] = start + length", "free[k] = start + length - 1"),
    ("blz_scenario.py", "y = tuple(C.PITCH * (b + 0.5) for b in range(blocks))", "y = tuple(C.PITCH * (b + 1.0) for b in range(blocks))"),
    ("blz_scenario.py", "C.D0 + abs(sh.pos - y[b])", "C.D0 - abs(sh.pos - y[b])"),
    ("blz_scenario.py", "hours = max(sh.start + sh.length for sh in made) + C.TIME_PAD", "hours = max(sh.start + sh.length for sh in made) + C.TIME_PAD - 1"),
    ("blz_scenario.py", "limit = (100.0 / fill) * max(", "limit = (90.0 / fill) * max("),
    ("blz_scenario.py", "for t in range(hours)) / blocks", "for t in range(hours)) / (blocks + 1)"),
    ("blz_scenario.py", "return (float(upper * 2 // 3), float(upper))", "return (float(upper // 2), float(upper))"),
    ("blz_scenario.py", "if sh.start - delivery <= t < sh.start else 0.0) for t in range(hours)) for sh in ships)", "if sh.start - delivery <= t <= sh.start else 0.0) for t in range(hours)) for sh in ships)"),
    ("blz_scenario.py", "cum_in += h[s][t] if delivery else (1.0 if t == sh.start else 0.0)", "cum_in += h[s][t] if delivery else (1.0 if t == sh.start + 1 else 0.0)"),
    ("blz_scenario.py", "start=min(max(0, sh.start + dl), week.hours - sh.length)", "start=min(sh.start + dl, week.hours - sh.length)"),
    ("blz_scenario.py", "start=min(max(0, sh.start + dl), week.hours - sh.length)", "start=max(0, sh.start + dl)"),
    ("blz_scenario.py", "start=min(max(0, sh.start + dl), week.hours - sh.length)", "start=min(max(0, sh.start - dl), week.hours - sh.length)"),
    ("blz_scenario.py", "return [int(round(rng.gauss(0.0, sigma))) for _ in range(n_ships)]", "return [int(rng.gauss(0.0, sigma)) for _ in range(n_ships)]"),
    ("blz_scenario.py", "random.Random(base + 1000 * seed + k)", "random.Random(base + 100 * seed + k)"),
    ("blz_scenario.py", "return max(dem) / (week.blocks * week.mu)", "return max(dem) / week.mu"),
    ("blz_scenario.py", "length = max(C.MIN_WINDOW, math.ceil(n / rho))", "length = max(C.MIN_WINDOW, math.floor(n / rho))"),
    ("blz_scenario.py", "n = rng.randint(*n_range)", "n = rng.randint(n_range[0], n_range[1] - 1)"),
    # blz_queue.py
    ("blz_queue.py", "prev = max(0.0, prev + load[b][t] - week.mu)", "prev = max(0.0, prev + load[b][t] - week.mu * 0.9)"),
    ("blz_queue.py", "prev = max(0.0, prev + load[b][t] - week.mu)", "prev = max(1.0, prev + load[b][t] - week.mu)"),
    ("blz_queue.py", "wait = sum(q[b][t] for b in range(B) for t in range(T)) / N * 60.0", "wait = sum(q[b][t] for b in range(B) for t in range(T)) / N * 30.0"),
    ("blz_queue.py", "te = min(T - 1, sh.start + sh.length - 1)", "te = min(T - 1, sh.start + sh.length)"),
    ("blz_queue.py", "delays.append(max(q[b][te] for b in used) / mu * 60.0 if used else 0.0)", "delays.append(min(q[b][te] for b in used) / mu * 60.0 if used else 0.0)"),
    ("blz_queue.py", "delays.append(max(q[b][te] for b in used) / mu * 60.0 if used else 0.0)", "delays.append(max(q[b][te] for b in used) * 60.0 if used else 0.0)"),
    ("blz_queue.py", "used = [b for b in range(B) if x[s][b] > 0]", "used = [b for b in range(B) if x[s][b] >= 0]"),
    ("blz_queue.py", "stock_over = max(stock_over, stock - week.limit)", "stock_over = max(stock_over, stock - week.limit / 2)"),
    ("blz_queue.py", "fill = max(fill, stock / week.limit)", "fill = max(fill, stock / week.limit / 2)"),
    ("blz_queue.py", "distance = sum(x[s][b] * week.d[s][b] for s in range(S_) for b in range(B)) / N", "distance = sum(x[s][b] * week.d[s][b] for s in range(S_) for b in range(B)) / S_"),
    ("blz_queue.py", "peak = max(max(row) for row in load) / mu", "peak = min(max(row) for row in load) / mu"),
    ("blz_queue.py", "int(math.ceil(0.95 * len(ordered))) - 1", "int(math.ceil(0.90 * len(ordered))) - 1"),
    ("blz_queue.py", "return Robust(statistics.mean(waits), ordered", "return Robust(max(waits), ordered"),
    ("blz_queue.py", "return Metrics(distance, wait, peak, max(0.0, stock_over), fill, max(delays), tuple(delays)", "return Metrics(distance, wait, peak, stock_over, fill, sum(delays) / S_, tuple(delays)"),
    # blz_rules.py
    ("blz_rules.py", "order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), i))", "order = sorted(range(len(weights)), key=lambda i: (raw[i] - base[i], i))"),
    ("blz_rules.py", "order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), i))", "order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), -i))"),
    ("blz_rules.py", "self.stock[b][t] + take * g[t] <= limit + C.STOCK_EPS", "self.stock[b][t] + take * g[t] < limit"),
    ("blz_rules.py", "self.stock[b][t] + take * g[t] <= limit + C.STOCK_EPS", "self.stock[b][t] - take * g[t] <= limit + C.STOCK_EPS"),
    ("blz_rules.py", "        if limit is None:\n            return True", "        if limit is None:\n            return False"),
    ("blz_rules.py", "for t in range(self.week.hours) if g[t] > 0)", "for t in range(self.week.hours) if g[t] > 1)"),
    ("blz_rules.py", "return max(self.load[b][t] + take * lf[t] for t in range(self.week.hours) if lf[t] > 0) / self.week.mu", "return max(self.load[b][t] - take * lf[t] for t in range(self.week.hours) if lf[t] > 0) / self.week.mu"),
    ("blz_rules.py", "self.stock[b][t] += take * g[t]", "self.stock[b][t] += g[t]"),
    ("blz_rules.py", "self.load[b][t] += take * lf[t]", "self.load[b][t] += lf[t]"),
    ("blz_rules.py", "pick = next((b for b in order if st.fits(s, b, take)), order[0])", "pick = next((b for b in order if st.fits(s, b, take)), order[-1])"),
    ("blz_rules.py", "return [split_rounded(sh.n, [1] * week.blocks) for sh in week.ships]", "return [split_rounded(sh.n, [1] * (week.blocks - 1) + [2]) for sh in week.ships]"),
    ("blz_rules.py", "k = min(week.blocks, max(1, math.ceil(sh.n / sh.length / week.mu)))", "k = min(week.blocks, max(1, math.floor(sh.n / sh.length / week.mu)))"),
    ("blz_rules.py", "k = min(week.blocks, max(1, math.ceil(sh.n / sh.length / week.mu)))", "k = min(week.blocks, max(2, math.ceil(sh.n / sh.length / week.mu)))"),
    ("blz_rules.py", "ring = ring[:k] if ring else [order[0]]", "ring = ring[:k + 1] if ring else [order[0]]"),
    ("blz_rules.py", "ring = ring[:k] if ring else [order[0]]", "ring = ring[:k] if ring else [order[-1]]"),
    ("blz_rules.py", "pick = ring[i % len(ring)]", "pick = ring[0]"),
    ("blz_rules.py", "return sorted(range(week.n_ships), key=lambda s: (week.ships[s].start, s))", "return sorted(range(week.n_ships), key=lambda s: (week.ships[s].start, -s))"),
    ("blz_rules.py", "return sorted(range(week.n_ships), key=lambda s: (week.ships[s].start, s))", "return sorted(range(week.n_ships), key=lambda s: (-week.ships[s].start, s))"),
    ("blz_rules.py", "return sorted(range(week.blocks), key=lambda b: (week.d[s][b], b))", "return sorted(range(week.blocks), key=lambda b: (week.d[s][b], -b))"),
    ("blz_rules.py", "pick = next((b for b in cand if peak[b] <= cap + 1e-9), None)", "pick = next((b for b in cand if peak[b] < cap), None)"),
    ("blz_rules.py", "pick = min(cand, key=lambda b: (round(peak[b], 9), order.index(b)))", "pick = max(cand, key=lambda b: (round(peak[b], 9), order.index(b)))"),
    ("blz_rules.py", "pick = min(cand, key=lambda b: (round(peak[b], 9), order.index(b)))", "pick = min(cand, key=lambda b: (round(peak[b], 9), -order.index(b)))"),
    ("blz_rules.py", "cand = [b for b in order if st.fits(s, b, take)] or list(order)", "cand = [b for b in order if st.fits(s, b, take)] or [order[0]]"),
    # blz_lp.py
    ("blz_lp.py", "c = sv.Constraint(week.ships[s].n / scale, week.ships[s].n / scale)", "c = sv.Constraint(week.ships[s].n / scale, week.ships[s].n / scale + 1)"),
    ("blz_lp.py", "c = sv.Constraint(-inf, week.mu / scale)", "c = sv.Constraint(-inf, week.mu)"),
    ("blz_lp.py", "                if t:\n                    c.SetCoefficient(q[k][b][t - 1], 1)", "                if t > 1:\n                    c.SetCoefficient(q[k][b][t - 1], 1)"),
    ("blz_lp.py", "c = sv.Constraint(-inf, week.limit / scale)", "c = sv.Constraint(-inf, week.limit)"),
    ("blz_lp.py", "c.SetCoefficient(x[s][b], week.g[s][t])", "c.SetCoefficient(x[s][b], week.g[s][t] * 0.5)"),
    ("blz_lp.py", "week.d[s][b] / week.total * scale", "week.d[s][b] / week.total"),
    ("blz_lp.py", "60.0 / week.total / len(lfs) * scale", "60.0 / week.total * scale"),
    ("blz_lp.py", "obj.SetCoefficient(v, C.WAIT_TIEBREAK * coef)", "obj.SetCoefficient(v, coef)"),
    ("blz_lp.py", "obj.SetCoefficient(v, (lam if lam else C.WAIT_TIEBREAK) * coef)", "obj.SetCoefficient(v, C.WAIT_TIEBREAK * coef)"),
    ("blz_lp.py", "obj.SetCoefficient(v, (lam if lam else C.WAIT_TIEBREAK) * coef)", "obj.SetCoefficient(v, 2 * (lam if lam else C.WAIT_TIEBREAK) * coef)"),
    ("blz_lp.py", "if status != pywraplp.Solver.OPTIMAL:", "if status == pywraplp.Solver.INFEASIBLE:"),
    ("blz_lp.py", "if sv is None:", "if sv is False:"),
    ("blz_lp.py", "lfs = scenarios or [week.lf]", "lfs = scenarios or [week.f]"),
    ("blz_lp.py", "base = [int(math.floor(v + 1e-9)) for v in xs]", "base = [int(math.floor(v)) for v in xs]"),
    ("blz_lp.py", "base = [int(math.floor(v + 1e-9)) for v in xs]", "base = [int(math.ceil(v)) for v in xs]"),
    ("blz_lp.py", "order = sorted(range(len(xs)), key=lambda i: (-(xs[i] - base[i]), i))", "order = sorted(range(len(xs)), key=lambda i: (xs[i] - base[i], i))"),
    ("blz_lp.py", "order = sorted(range(len(xs)), key=lambda i: (-(xs[i] - base[i]), i))", "order = sorted(range(len(xs)), key=lambda i: (-(xs[i] - base[i]), -i))"),
    ("blz_lp.py", "return solve(week, eps_wait=max(eps, min_wait + 1e-6)).distance", "return solve(week, eps_wait=min(eps, min_wait + 1e-6)).distance"),
    ("blz_lp.py", "return solve(week, eps_wait=max(eps, min_wait + 1e-6)).distance", "return solve(week, eps_wait=max(eps, min_wait)).distance"),
    ("blz_lp.py", "return round_plan(week, res.x), res\n\n\ndef plan_hedged", "return res.x, res\n\n\ndef plan_hedged"),
    # blz_evaluation.py
    ("blz_evaluation.py", "Bound(res.distance, res.wait, res.distance + lam * res.wait, m.distance + lam * wait_r)", "Bound(res.distance, res.wait, res.distance + lam * res.wait, m.distance + wait_r)"),
    ("blz_evaluation.py", "Bound(res.distance, res.wait, res.distance + lam * res.wait,", "Bound(res.distance, res.wait, res.distance + res.wait,"),
    ("blz_evaluation.py", "b_lp = Bound(res_lp.distance, res_lp.wait, res_lp.wait, m_lp.wait)", "b_lp = Bound(res_lp.distance, res_lp.wait, res_lp.wait, m_lp.distance)"),
    ("blz_evaluation.py", "100.0 * (self.rounded / self.objective - 1.0)", "100.0 * (self.rounded / self.objective + 1.0)"),
    ("blz_evaluation.py", "if self.objective > 1e-9 else None", "if self.objective > 1.0 else None"),
    ("blz_evaluation.py", "wait_r = Q.robust_eval(week, x, train).wait", "wait_r = Q.robust_eval(week, x, S.evaluation_scenarios(week, p.sigma)).wait"),
    ("blz_evaluation.py", "points.append(CurvePoint(lam, m.distance, m.wait, Q.robust_eval(week, x, test).wait))", "points.append(CurvePoint(lam, m.distance, m.wait, Q.robust_eval(week, x, S.train_scenarios(week, p.sigma)).wait))"),
    ("blz_evaluation.py", "min_wait = L.solve(week, min_wait=True).wait", "min_wait = 0.0"),
    ("blz_evaluation.py", "return Curve(tuple(points), edge, min_wait, res[BUNDLE].m.distance, res[SPREAD].m.distance)", "return Curve(tuple(points), edge, min_wait, res[SPREAD].m.distance, res[BUNDLE].m.distance)"),
    ("blz_evaluation.py", "o.m.distance + res.params.lam * o.robust.wait", "o.m.distance + o.robust.wait"),
    ("blz_evaluation.py", "return tuple(week_row(p, seed) for seed in range(base, base + n))", "return tuple(week_row(p, seed) for seed in range(base, base + n - 1))"),
    ("blz_evaluation.py", "return tuple(week_row(p, seed) for seed in range(base, base + n))", "return tuple(week_row(p, seed) for seed in range(n))"),
    ("blz_evaluation.py", "return v[min(len(v) - 1, int(share * len(v)))]", "return v[min(len(v) - 1, int(share * len(v)) - 1)]"),
    ("blz_evaluation.py", "return v[min(len(v) - 1, int(share * len(v)))]", "return v[int(share * len(v))]"),
    ("blz_evaluation.py", "return [getattr(r.m[key], field) - getattr(r.m[reference], field) for r in rows]", "return [getattr(r.m[reference], field) - getattr(r.m[key], field) for r in rows]"),
    ("blz_evaluation.py", "sum(1 for x in d if x < -tol), sum(1 for x in d if x > tol)", "sum(1 for x in d if x < tol), sum(1 for x in d if x > tol)"),
    ("blz_evaluation.py", "-statistics.fmean(d), -statistics.median(d))", "statistics.fmean(d), -statistics.median(d))"),
    ("blz_evaluation.py", "-statistics.fmean(d), -statistics.median(d))", "-statistics.fmean(d), statistics.median(d))"),
    ("blz_evaluation.py", "kind = \"unclear\" if abs(diff) <= C.VERDICT_Z * se else (\"better\" if diff < 0 else \"worse\")", "kind = \"unclear\" if abs(diff) < C.VERDICT_Z * se else (\"better\" if diff < 0 else \"worse\")"),
    ("blz_evaluation.py", "kind = \"unclear\" if abs(diff) <= C.VERDICT_Z * se else (\"better\" if diff < 0 else \"worse\")", "kind = \"unclear\" if abs(diff) <= C.VERDICT_Z * se else (\"better\" if diff > 0 else \"worse\")"),
    ("blz_evaluation.py", "kind = \"unclear\" if diff == 0 else (\"better\" if diff < 0 else \"worse\")", "kind = \"unclear\" if diff == 1 else (\"better\" if diff < 0 else \"worse\")"),
    ("blz_evaluation.py", "kind = \"unclear\" if diff == 0 else (\"better\" if diff < 0 else \"worse\")", "kind = \"unclear\" if diff == 0 else (\"better\" if diff > 0 else \"worse\")"),
    ("blz_evaluation.py", "100.0 * diff / ref if ref else None", "10.0 * diff / ref if ref else None"),
    ("blz_evaluation.py", "statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0", "statistics.stdev(d) / len(d) if len(d) > 1 else 0.0"),
    ("blz_evaluation.py", "ref = mean_of(rows, reference, field)", "ref = mean_of(rows, key, field)"),
    ("blz_evaluation.py", "if kb.m.wait < C.CALM_WAIT and lp.robust.wait < C.CALM_WAIT:", "if kb.m.wait <= C.CALM_WAIT and lp.robust.wait < C.CALM_WAIT:"),
    ("blz_evaluation.py", "if kb.m.wait < C.CALM_WAIT and lp.robust.wait < C.CALM_WAIT:", "if kb.m.wait < C.CALM_WAIT and lp.robust.wait <= C.CALM_WAIT:"),
    ("blz_evaluation.py", "if kb.m.wait < C.CALM_WAIT and lp.robust.wait < C.CALM_WAIT:", "if kb.m.wait < C.CALM_WAIT or lp.robust.wait < C.CALM_WAIT:"),
    ("blz_evaluation.py", "elif p.sigma == 0:", "elif p.sigma <= 1:"),
    ("blz_evaluation.py", "elif lp.m.wait >= C.OVERLOAD_WAIT:", "elif lp.m.wait > C.OVERLOAD_WAIT:"),
    ("blz_evaluation.py", "elif lp.robust.wait >= C.FRAGILE_RATIO * max(lp.m.wait, 1.0):", "elif lp.robust.wait > C.FRAGILE_RATIO * max(lp.m.wait, 1.0):"),
    ("blz_evaluation.py", "elif lp.robust.wait >= C.FRAGILE_RATIO * max(lp.m.wait, 1.0):", "elif lp.robust.wait >= C.FRAGILE_RATIO * max(lp.m.wait, 2.0):"),
    ("blz_evaluation.py", "elif lp.robust.wait >= C.FRAGILE_RATIO * max(lp.m.wait, 1.0):", "elif lp.robust.wait >= C.FRAGILE_RATIO * lp.m.wait:"),
    ("blz_evaluation.py", "kind = \"hedge\" if hd.robust.wait <= C.HEDGE_FACTOR * lp.robust.wait else \"fragile\"", "kind = \"hedge\" if hd.robust.wait < C.HEDGE_FACTOR * lp.robust.wait else \"fragile\""),
    ("blz_evaluation.py", "kind = \"hedge\" if hd.robust.wait <= C.HEDGE_FACTOR * lp.robust.wait else \"fragile\"", "kind = \"fragile\" if hd.robust.wait <= C.HEDGE_FACTOR * lp.robust.wait else \"hedge\""),
    ("blz_evaluation.py", "extra = hd.m.distance - lp.m.distance", "extra = lp.m.distance - hd.m.distance"),
    ("blz_evaluation.py", "100.0 * extra / lp.m.distance", "100.0 * extra / hd.m.distance"),
    ("blz_evaluation.py", "if o.m.stock_over > C.STOCK_TOLERANCE)", "if o.m.stock_over >= C.STOCK_TOLERANCE)"),
    ("blz_evaluation.py", "bei Verspätung {d.lp_wait_shift:.1f} min. Die Absicherung (Preis", "bei Verspätung {d.hedge_wait_shift:.1f} min. Die Absicherung (Preis"),
    ("blz_evaluation.py", "kostet {d.extra:.0f} m Fahrweg \"\n                f\"({signed(d.extra_pct)} %)", "kostet {d.extra_pct:.0f} m Fahrweg \"\n                f\"({signed(d.extra_pct)} %)"),
    ("blz_evaluation.py", "und senkt die Wartezeit bei Verspätung auf {d.hedge_wait_shift:.1f} min.", "und senkt die Wartezeit bei Verspätung auf {d.lp_wait_shift:.1f} min."),
    ("blz_evaluation.py", "Rechnen spart nur wenige Meter ({d.lp_distance:.0f} statt {d.kb_distance:.0f} m)", "Rechnen spart nur wenige Meter ({d.kb_distance:.0f} statt {d.lp_distance:.0f} m)"),
    ("blz_evaluation.py", "{d.hedge_distance:.1f} gegen {d.lp_distance:.1f} m Fahrweg und {d.hedge_wait:.2f} gegen {d.lp_wait:.2f} min", "{d.lp_distance:.1f} gegen {d.hedge_distance:.1f} m Fahrweg und {d.hedge_wait:.2f} gegen {d.lp_wait:.2f} min"),
    ("blz_evaluation.py", "auch der Rechenplan wartet pünktlich {d.lp_wait:.1f} min (bei Verspätung {d.lp_wait_shift:.1f} min)", "auch der Rechenplan wartet pünktlich {d.kb_wait:.1f} min (bei Verspätung {d.lp_wait_shift:.1f} min)"),
    ("blz_evaluation.py", "if not any(k in (LP, HEDGE) for k, _ in d.stock) else", "if any(k in (LP, HEDGE) for k, _ in d.stock) else"),
    ("blz_evaluation.py", "names = \", \".join(f\"{C.METHOD_SHORT[k]} um {v:.0f} Container\" for k, v in d.stock)", "names = \", \".join(f\"{C.METHOD_SHORT[k]} um {v:.1f} Container\" for k, v in d.stock)"),
    ("blz_evaluation.py", "amount = f\"**{abs(v.pct):.0f} % weniger**\" if v.pct is not None", "amount = f\"**{v.pct:.0f} % weniger**\" if v.pct is not None"),
    ("blz_evaluation.py", "amount = f\"**{v.pct:.0f} % mehr**\" if v.pct is not None", "amount = f\"**{abs(v.pct):.0f} % mehr**\" if v.pct is not None"),
    ("blz_evaluation.py", "In **{d.worse * 100:.0f} %** der Wochen ist es umgekehrt.", "In **{d.better * 100:.0f} %** der Wochen ist es umgekehrt."),
    ("blz_evaluation.py", "In **{d.better * 100:.0f} %** der Wochen ist es besser.", "In **{d.worse * 100:.0f} %** der Wochen ist es besser."),
    ("blz_evaluation.py", "    v = round(value, digits)\n    if v == 0:\n        v = 0.0", "    v = round(value, digits)\n    if v == 1:\n        v = 0.0"),
    ("blz_evaluation.py", "    v = round(value, digits)\n    if v == 0:", "    v = value\n    if v == 0:"),
    ("blz_evaluation.py", "(f\"Abgesichert gegen Gierig, Zielwert Weg + {lam} · Wartezeit bei Verspätung\", HEDGE, GREEDY, \"cost\", \"Zielwert\", \"m\"))", "(f\"Abgesichert gegen Gierig, Zielwert Weg + {lam} · Wartezeit bei Verspätung\", HEDGE, KBLOCKS, \"cost\", \"Zielwert\", \"m\"))"),
    ("blz_evaluation.py", "(\"Gerechnet gegen Kranrate passend, Wartezeit pünktlich\", LP, KBLOCKS, \"wait\", \"Wartezeit\", \"min\")", "(\"Gerechnet gegen Kranrate passend, Wartezeit pünktlich\", LP, KBLOCKS, \"wait_shift\", \"Wartezeit\", \"min\")"),
    # blz_stories.py
    ("blz_stories.py", "(kb_w >= 10.0,", "(kb_w > 10.0,"),
    ("blz_stories.py", "(lp_w <= 2.0, f\"Gerechnet, Wartezeit pünktlich <= 2 min: {lp_w:.2f}\"),\n                (lp_r >= 25.0", "(lp_w < 2.0, f\"Gerechnet, Wartezeit pünktlich <= 2 min: {lp_w:.2f}\"),\n                (lp_r >= 25.0"),
    ("blz_stories.py", "(lp_r >= 25.0,", "(lp_r > 25.0,"),
    ("blz_stories.py", "(hd_r <= 15.0, f\"abgesichert, Wartezeit bei Verspätung <= 15 min: {hd_r:.1f}\"),\n                (ratio", "(hd_r < 15.0, f\"abgesichert, Wartezeit bei Verspätung <= 15 min: {hd_r:.1f}\"),\n                (ratio"),
    ("blz_stories.py", "(ratio is not None and ratio >= 3.0,", "(ratio is not None and ratio > 3.0,"),
    ("blz_stories.py", "(extra >= 25.0, f\"Mehrweg der Absicherung >= 25 m: {extra:.1f}\"),", "(extra > 25.0, f\"Mehrweg der Absicherung >= 25 m: {extra:.1f}\"),"),
    ("blz_stories.py", "(extra <= 60.0,", "(extra < 60.0,"),
    ("blz_stories.py", "(lp_r >= 50.0,", "(lp_r > 50.0,"),
    ("blz_stories.py", "(hd_r <= 25.0, f\"abgesichert, Wartezeit bei Verspätung <= 25 min: {hd_r:.1f}\"),\n                (extra >= 45.0", "(hd_r < 25.0, f\"abgesichert, Wartezeit bei Verspätung <= 25 min: {hd_r:.1f}\"),\n                (extra >= 45.0"),
    ("blz_stories.py", "(extra >= 45.0,", "(extra > 45.0,"),
    ("blz_stories.py", "(over_b >= 50.0,", "(over_b > 50.0,"),
    ("blz_stories.py", "(over_lp <= 1.0,", "(over_lp < 1.0,"),
    ("blz_stories.py", "(_share(rows, LP) <= 0.05 and _share(rows, HEDGE) <= 0.05,", "(_share(rows, LP) < 0.05 and _share(rows, HEDGE) <= 0.05,"),
    ("blz_stories.py", "(_share(rows, LP) <= 0.05 and _share(rows, HEDGE) <= 0.05,", "(_share(rows, LP) <= 0.05 and _share(rows, HEDGE) < 0.05,"),
    ("blz_stories.py", "(_share(rows, BUNDLE) >= 0.9,", "(_share(rows, BUNDLE) > 0.9,"),
    ("blz_stories.py", "(lp_w <= 2.0, f\"Gerechnet, Wartezeit pünktlich <= 2 min: {lp_w:.2f}\"),\n                (hd_r <= 15.0", "(lp_w < 2.0, f\"Gerechnet, Wartezeit pünktlich <= 2 min: {lp_w:.2f}\"),\n                (hd_r <= 15.0"),
    ("blz_stories.py", "(hd_r <= 15.0, f\"abgesichert, Wartezeit bei Verspätung <= 15 min: {hd_r:.1f}\")]\n    if name == \"Starke Kräne\"", "(hd_r < 15.0, f\"abgesichert, Wartezeit bei Verspätung <= 15 min: {hd_r:.1f}\")]\n    if name == \"Starke Kräne\""),
    ("blz_stories.py", "(kb_w >= 25.0,", "(kb_w > 25.0,"),
    ("blz_stories.py", "(lp_r >= 15.0,", "(lp_r > 15.0,"),
    ("blz_stories.py", "(hd_r <= 25.0, f\"abgesichert, Wartezeit bei Verspätung <= 25 min: {hd_r:.1f}\")]\n    if name == \"Ruhige Woche\"", "(hd_r < 25.0, f\"abgesichert, Wartezeit bei Verspätung <= 25 min: {hd_r:.1f}\")]\n    if name == \"Ruhige Woche\""),
    ("blz_stories.py", "(kb_w <= 1.0,", "(kb_w < 1.0,"),
    ("blz_stories.py", "(lp_r <= 1.0,", "(lp_r < 1.0,"),
    ("blz_stories.py", "(saving >= 3.0,", "(saving > 3.0,"),
    ("blz_stories.py", "(saving <= 15.0,", "(saving < 15.0,"),
    ("blz_stories.py", "(extra <= 1.0, f\"Mehrweg der Absicherung <= 1 m: {extra:.2f}\")", "(extra < 1.0, f\"Mehrweg der Absicherung <= 1 m: {extra:.2f}\")"),
    ("blz_stories.py", "saving = -E.median_diff(rows, LP, KBLOCKS, \"distance\")", "saving = E.median_diff(rows, LP, KBLOCKS, \"distance\")"),
    ("blz_stories.py", "extra = E.median_diff(rows, HEDGE, LP, \"distance\")", "extra = E.median_diff(rows, LP, HEDGE, \"distance\")"),
    ("blz_stories.py", "return sum(1 for r in rows if getattr(r.m[key], field) > C.STOCK_TOLERANCE) / len(rows)", "return sum(1 for r in rows if getattr(r.m[key], field) >= C.STOCK_TOLERANCE) / len(rows)"),
    ("blz_stories.py", "return E.median_of(rows, num, field) / d if d > 0 else None", "return E.median_of(rows, num, field) / d if d >= 0 else None"),
    ("blz_stories.py", "return all(ok for ok, _ in criteria(name, (row,)))", "return any(ok for ok, _ in criteria(name, (row,)))"),
    # blz_visualization.py
    ("blz_visualization.py", "Y_HEADROOM = 1.2", "Y_HEADROOM = 1.5"),
    ("blz_visualization.py", "LOAD_MIN_MAX = 100.0", "LOAD_MIN_MAX = 50.0"),
    ("blz_visualization.py", "return top if clipped_key_value is not None and clipped_key_value > top else None", "return top if clipped_key_value is not None and clipped_key_value >= top else None"),
    ("blz_visualization.py", "top = max([v for v in values if v is not None] + [1.0]) * Y_HEADROOM", "top = min([v for v in values if v is not None] + [1.0]) * Y_HEADROOM"),
    ("blz_visualization.py", "clipped = limit is not None and y > limit", "clipped = limit is not None and y >= limit"),
    ("blz_visualization.py", "y=[limit if clipped else y]", "y=[y]"),
    ("blz_visualization.py", "chosen = [pt for pt in pts if pt.lam == lam_now]", "chosen = [pt for pt in pts if pt.lam != lam_now]"),
    ("blz_visualization.py", "rule_keys = [k for k in C.METHOD_KEYS if k != C.M_HEDGE] if curve is not None else list(C.METHOD_KEYS)", "rule_keys = list(C.METHOD_KEYS)"),
    ("blz_visualization.py", "fig.update_xaxes(type=\"log\", tickvals=eps, ticktext=[str(e) for e in eps])", "fig.update_xaxes(tickvals=eps, ticktext=[str(e) for e in eps])"),
    ("blz_visualization.py", "x=[min(eps), max(eps)], y=[value, value]", "x=[min(eps), max(eps)], y=[value, value + 1]"),
    ("blz_visualization.py", "text=[[str(v) if v else \"\" for v in r] for r in x]", "text=[[str(v) for v in r] for r in x]"),
    ("blz_visualization.py", "height=90 + 34 * week.n_ships", "height=90 + 34 * week.blocks"),
    ("blz_visualization.py", "z = [[v / week.mu * 100.0 for v in row] for row in load]", "z = [[v / week.mu for v in row] for row in load]"),
    ("blz_visualization.py", "scale = [[0, \"#eef3f9\"], [LOAD_MIN_MAX / top, \"#f0b429\"], [1, \"#b3261e\"]]", "scale = [[0, \"#eef3f9\"], [0.5, \"#f0b429\"], [1, \"#b3261e\"]]"),
    ("blz_visualization.py", "if top > LOAD_MIN_MAX:", "if top >= LOAD_MIN_MAX:"),
    ("blz_visualization.py", "return max([LOAD_MIN_MAX] + [max(max(row) for row in load) / mu * 100.0 for load in loads])", "return min([LOAD_MIN_MAX] + [max(max(row) for row in load) / mu * 100.0 for load in loads])"),
    ("blz_visualization.py", "text=[f\"{v:.0f} %\" if v >= 6 else \"\" for v in shares]", "text=[f\"{v:.0f} %\" if v >= 0 else \"\" for v in shares]"),
    ("blz_visualization.py", "error_x=dict(type=\"data\", symmetric=False, array=[hi - med], arrayminus=[med - lo]", "error_x=dict(type=\"data\", symmetric=False, array=[med - lo], arrayminus=[hi - med]"),
    ("blz_visualization.py", "def _lock_axes(fig):\n    fig.update_xaxes(fixedrange=True)", "def _lock_axes(fig):\n    fig.update_xaxes(fixedrange=False)"),
    ("blz_visualization.py", "    fig.update_yaxes(fixedrange=True)\n    return fig", "    fig.update_yaxes(fixedrange=False)\n    return fig"),
    # blz_pdf_export.py
    ("blz_pdf_export.py", "\"σ\": \"sigma\", ", ""),
    ("blz_pdf_export.py", "\"λ\": \"lambda\", ", ""),
    ("blz_pdf_export.py", "\"μ\": \"mu\", ", ""),
    ("blz_pdf_export.py", "\"**\": \"\",", ""),
    ("blz_pdf_export.py", "\"€\": \"EUR\", ", ""),
    ("blz_pdf_export.py", "\"–\": \"-\", ", ""),
    ("blz_pdf_export.py", "if week.limit is not None else \"unbegrenzt\"", "if week.limit is None else \"unbegrenzt\""),
    ("blz_pdf_export.py", "if diag.stock:\n        note(E.stock_text(diag), 9)", "if not diag.stock:\n        note(E.stock_text(diag), 9)"),
    ("blz_pdf_export.py", "if curve is not None:\n        keep_together(110)", "if curve is None:\n        keep_together(110)"),
    ("blz_pdf_export.py", "if sample is not None:\n        keep_together(110)", "if sample is None:\n        keep_together(110)"),
    ("blz_pdf_export.py", "f\"{o.m.distance:.0f}\", f\"{o.m.wait:.1f}\", f\"{o.robust.wait:.1f}\", f\"{o.m.delay_max:.0f}\"", "f\"{o.m.distance:.0f}\", f\"{o.m.wait:.1f}\", f\"{o.m.wait:.1f}\", f\"{o.m.delay_max:.0f}\""),
    ("blz_pdf_export.py", "for field in (\"distance\", \"wait\", \"wait_shift\"):", "for field in (\"distance\", \"wait\", \"wait\"):"),
    ("blz_pdf_export.py", "for spec in E.verdict_specs(p.lam):", "for spec in E.verdict_specs(p.lam)[:2]:"),
    ("blz_pdf_export.py", "{sample[0].seed}-{sample[-1].seed}", "{sample[0].seed}-{sample[0].seed}"),
    # blz_presets.py
    ("blz_presets.py", "value = spec.lo + round((value - spec.lo) / spec.step) * spec.step", "value = spec.lo + int((value - spec.lo) / spec.step) * spec.step"),
    ("blz_presets.py", "        value = min(spec.hi, value)\n    return value", "        value = min(spec.hi, value + 1)\n    return value"),
    ("blz_presets.py", "if spec.step and spec.step > 1 and spec.lo is not None:", "if spec.step and spec.step > 2 and spec.lo is not None:"),
    ("blz_presets.py", "    if not math.isfinite(value):\n        raise ValueError(raw)\n    return min(", "    return min("),
    ("blz_presets.py", "key=lambda c: (abs(c - value), c))", "key=lambda c: (abs(c - value), -c))"),
    ("blz_presets.py", "if raw not in C.METHOD_KEYS:", "if raw not in C.METHOD_KEYS[:5]:"),
    ("blz_presets.py", "if isinstance(value, float) and not math.isfinite(value):\n        return None", "if isinstance(value, float) and math.isfinite(value):\n        return None"),
    # blz_constants.py
    ("blz_constants.py", "PITCH = 100.0", "PITCH = 90.0"),
    ("blz_constants.py", "D0 = 200.0", "D0 = 150.0"),
    ("blz_constants.py", "N_LO, N_HI = 700, 1300", "N_LO, N_HI = 600, 1300"),
    ("blz_constants.py", "ARRIVAL_SPAN = 30", "ARRIVAL_SPAN = 24"),
    ("blz_constants.py", "DELIVERY_HOURS = 36", "DELIVERY_HOURS = 24"),
    ("blz_constants.py", "TIME_PAD = 22", "TIME_PAD = 20"),
    ("blz_constants.py", "MIN_WINDOW = 3", "MIN_WINDOW = 4"),
    ("blz_constants.py", "LOT = 10", "LOT = 5"),
    ("blz_constants.py", "CAP_HEADROOM = 0.8", "CAP_HEADROOM = 0.7"),
    ("blz_constants.py", "LP_SCALE = 100.0", "LP_SCALE = 1.0"),
    ("blz_constants.py", "WAIT_TIEBREAK = 1e-6", "WAIT_TIEBREAK = 1e-3"),
    ("blz_constants.py", "STOCK_EPS = 1e-9", "STOCK_EPS = 1e-3"),
    ("blz_constants.py", "N_TRAIN, N_TEST = 10, 30", "N_TRAIN, N_TEST = 5, 30"),
    ("blz_constants.py", "N_TRAIN, N_TEST = 10, 30", "N_TRAIN, N_TEST = 10, 20"),
    ("blz_constants.py", "TRAIN_BASE, TEST_BASE = 500000, 0", "TRAIN_BASE, TEST_BASE = 500000, 500000"),
    ("blz_constants.py", "TRAIN_BASE, TEST_BASE = 500000, 0", "TRAIN_BASE, TEST_BASE = 400000, 0"),
    ("blz_constants.py", "SAMPLE_WEEKS, SAMPLE_BASE = 20, 3000", "SAMPLE_WEEKS, SAMPLE_BASE = 20, 2000"),
    ("blz_constants.py", "LAM_CURVE = (1, 2, 5, 10, 20, 50, 100)", "LAM_CURVE = (1, 2, 5, 10, 20, 50)"),
    ("blz_constants.py", "EPS_EDGE = (400, 200, 100, 50, 20, 10, 5, 2, 1)", "EPS_EDGE = (400, 200, 100, 50, 20, 10, 5, 2)"),
    ("blz_constants.py", "VERDICT_Z = 2.0", "VERDICT_Z = 1.0"),
    ("blz_constants.py", "VERDICT_Z = 2.0", "VERDICT_Z = 3.0"),
    ("blz_constants.py", "PCT_LO, PCT_HI = 0.10, 0.90", "PCT_LO, PCT_HI = 0.25, 0.90"),
    ("blz_constants.py", "CALM_WAIT = 2.0", "CALM_WAIT = 1.0"),
    ("blz_constants.py", "OVERLOAD_WAIT = 3.0", "OVERLOAD_WAIT = 2.0"),
    ("blz_constants.py", "FRAGILE_RATIO = 5.0", "FRAGILE_RATIO = 4.0"),
    ("blz_constants.py", "HEDGE_FACTOR = 0.6", "HEDGE_FACTOR = 0.5"),
    ("blz_constants.py", "STOCK_TOLERANCE = 1.5", "STOCK_TOLERANCE = 0.5"),
    ("blz_constants.py", "BASELINE = M_KBLOCKS", "BASELINE = M_GREEDY"),
]


def check_unique():
    bad = []
    for n, (name, old, new) in enumerate(MUTANTS, 1):
        text = (ROOT / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            bad.append((n, name, old[:70], text.count(old)))
        if old == new:
            bad.append((n, name, "alt == neu", 0))
    return bad


def run_one(args):
    n, name, old, new, base = args
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"blz_mut{n}_"))
    try:
        shutil.copytree(base, tmp, dirs_exist_ok=True)
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        files = [f"tests/{f}" for f in TEST_ORDER + (["test_app.py"] if WITH_APP else [])]
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *files], cwd=tmp, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
            return n, name, old, new, r.returncode == 0, False
        except subprocess.TimeoutExpired:
            return n, name, old, new, False, True                 # Endlosschleife oder zu langsam: gilt als gefunden
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else ""
    jobs = 6
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
        only = "" if only == str(jobs) else only
    wanted = None
    if "--indices" in sys.argv:
        spec = sys.argv[sys.argv.index("--indices") + 1]
        only = "" if only == spec else only
        wanted = set()
        for part in spec.split(","):
            lo, _, hi = part.partition("-")
            wanted.update(range(int(lo), int(hi or lo) + 1))
    bad = check_unique()
    for b in bad:
        print("FEHLER (Stelle nicht eindeutig gefunden):", b)
    if "--dry-run" in sys.argv:
        print(f"{len(MUTANTS)} Mutanten, {len(bad)} Fehler in der Mutantenliste")
        return
    base = pathlib.Path(tempfile.mkdtemp(prefix="blz_mut_base_"))
    for f in ROOT.glob("*.py"):
        (base / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    shutil.copytree(ROOT / "tests", base / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    for f in (base / "tests").glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    bad_ids = {b[0] for b in bad}
    work = [(n, name, old, new, base) for n, (name, old, new) in enumerate(MUTANTS, 1) if n not in bad_ids and (not only or only in name) and (wanted is None or n in wanted)]
    survivors, killed = [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for n, name, old, new, survived, timeout in pool.map(run_one, work):
            if timeout:
                print(f"[{n:3d}] Zeitüberschreitung (als gefunden gezählt)  {name}", flush=True)
            if survived:
                survivors.append((n, name, old[:70], new[:70]))
                print(f"[{n:3d}] ÜBERLEBT  {name}: {old[:70]!r} -> {new[:70]!r}", flush=True)
            else:
                killed += 1
                print(f"[{n:3d}] gefunden  {name}", flush=True)
    print(f"\n{killed} gefunden, {len(survivors)} überlebt, {len(bad)} Fehler in der Mutantenliste")
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
