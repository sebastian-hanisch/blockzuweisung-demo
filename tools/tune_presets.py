"""Preset-Abstimmung per Sweep: trägt die Geschichte jedes Presets im MEDIAN über viele Wochen, und an der einen Woche, die das Preset zeigt?

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/tune_presets.py <modus>
  population   Grundgesamtheit (Seeds 1000-1099): Median-Kriterien aller Presets; Kennzahlen je Verfahren (Median, 10. bis 90. Perzentil); Häufigkeit der Lagerüberschreitung
  seeds        Kandidaten (Seeds 2000-2059, außerhalb der Grundgesamtheit): an welchen Wochen tragen alle fünf Presets, Abstand zum Median; nennt die besten gemeinsamen Seeds
  shown        die gezeigte Woche (C.SEED_DEFAULT): Kriterien, Kennzahlen und ihre Lage in der Grundgesamtheit

Grundsätze (aus den Hafen-Demos): den Seed nicht nach der schönsten Einzelwoche wählen, sondern nahe am MEDIAN; der Preset-Seed liegt außerhalb der Grundgesamtheit; alle Presets teilen sich EINE Wochen-Nummer.
Deterministisch, ohne Zeitlimit: die Kennzahlen hängen nicht vom Rechner ab (LP-Zielwerte eindeutig). Rechnet parallel (eine Woche mit sechs Verfahren kostet etwa 0,7 s)."""
import concurrent.futures
import os
import statistics
import sys

sys.path.insert(0, ".")
import blz_constants as C
import blz_evaluation as E
import blz_stories as ST

NAMES = list(C.PRESETS)
POPULATION = range(1000, 1100)
CANDIDATES = range(2000, 2060)


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["ships"], p["blocks"], p["mu"], p["crane"], p["fill"], p["sigma"], p["lam"])


def _row(args):
    name, seed = args
    return E.week_row(params(name), seed)


def rows_for(seeds):
    """{Preset: {Seed: WeekRow}} für alle Presets und Seeds, parallel."""
    jobs = [(n, s) for n in NAMES for s in seeds]
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        rows = list(pool.map(_row, jobs, chunksize=4))
    table = {n: {} for n in NAMES}
    for (n, s), r in zip(jobs, rows):
        table[n][s] = r
    return table


def cmd_population():
    table = rows_for(POPULATION)
    for name in NAMES:
        rows = tuple(table[name].values())
        print(f"\n### {name}")
        for ok, text in ST.criteria(name, rows):
            print(("  OK   " if ok else "  FAIL ") + text)
        for k in C.METHOD_KEYS:
            print(f"    {C.METHOD_SHORT[k]:17s}", *(f"{lab} {m:7.2f} [{lo:7.2f};{hi:7.2f}]" for lab, f in (("Weg", "distance"), ("W pünktl.", "wait"), ("W Versp.", "wait_shift"))
                                                   for m, lo, hi in [E.spread_of(rows, k, f)]))
        print("    Lagergrenze verletzt in", {C.METHOD_SHORT[k]: sum(1 for r in rows if r.m[k].stock_over > C.STOCK_TOLERANCE) for k in C.METHOD_KEYS})
        print("    Mehrweg der Absicherung Median", round(E.median_diff(rows, C.M_HEDGE, C.M_LP), 1), "Ersparnis Rechenplan gegen Kranrate", round(-E.median_diff(rows, C.M_LP, C.M_KBLOCKS), 1))


def _iqr(vals):
    v = sorted(vals)
    return max(1e-6, v[int(0.75 * len(v))] - v[int(0.25 * len(v))])


def cmd_seeds():
    pop = rows_for(POPULATION)
    cand = rows_for(CANDIDATES)
    scale = {(n, k, f): (statistics.median(E.values(tuple(pop[n].values()), k, f)), _iqr(E.values(tuple(pop[n].values()), k, f)) if _iqr(E.values(tuple(pop[n].values()), k, f)) > 1e-5 else 1.0)
             for n in NAMES for k, f in ST.TYPICAL}

    def dist(seed):
        d = [abs(getattr(cand[n][seed].m[k], f) - scale[(n, k, f)][0]) / scale[(n, k, f)][1] for n in NAMES for k, f in ST.TYPICAL]
        return sum(d), max(d)

    for n in NAMES:
        print(f"{n}: trägt an {sum(ST.holds(n, cand[n][s]) for s in CANDIDATES)} von {len(CANDIDATES)} Wochen")
    good = sorted((s for s in CANDIDATES if all(ST.holds(n, cand[n][s]) for n in NAMES)), key=lambda s: dist(s)[0])
    print("\nalle fünf tragen an:", good[:12], f"({len(good)} von {len(CANDIDATES)})")
    for s in good[:6]:
        tot, worst = dist(s)
        print(f"  seed {s} | Summe {tot:.2f} | schlechtester Abstand {worst:.2f} Interquartilsbreiten")


def cmd_shown():
    seed = C.SEED_DEFAULT
    pop = rows_for(POPULATION)
    for name in NAMES:
        row = _row((name, seed))
        print(f"\n### {name}, Seed {seed}: {'trägt' if ST.holds(name, row) else 'TRÄGT NICHT'}")
        for ok, text in ST.criteria(name, (row,)):
            print(("  OK   " if ok else "  FAIL ") + text)
        rows = tuple(pop[name].values())
        for k, f in ST.TYPICAL:
            vals = E.values(rows, k, f)
            v = getattr(row.m[k], f)
            rank = sum(1 for x in vals if x <= v) / len(vals)
            print(f"    {C.METHOD_SHORT[k]:12s} {f:11s} Woche {v:8.2f} | Median {statistics.median(vals):8.2f} | Rang {rank * 100:3.0f} %")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "population"
    {"population": cmd_population, "seeds": cmd_seeds, "shown": cmd_shown}.get(mode, lambda: sys.exit(__doc__))()
