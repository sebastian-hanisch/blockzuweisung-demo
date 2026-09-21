"""Die Woche: Schiffe mit Beladefenstern, Blöcke am Kai, Anlieferung vor dem Fenster, Lagergrenze, Verspätungsszenarien.

Flüssigkeitsmodell in Stundenschritten. Ein Schiff hat n Exportcontainer und ruft sie gleichmäßig über sein Beladefenster ab; dieselben Container kommen gleichmäßig in den DELIVERY_HOURS Stunden vorher
an und belasten den Block ebenfalls (ein Move je Container). Erzeugung mit random.Random (stabile Zahlenfolge auf allen Rechnern), Reihenfolge der Zufallszahlen wie in der Messreihe
(hafen-planung/messreihe_blockzuweisung/blz.py, make_instance und common.py, deltas und scen_set), damit deren Zahlen reproduzierbar sind."""

import math
import random
from dataclasses import dataclass, replace
from typing import Optional

import blz_constants as C


@dataclass(frozen=True)
class Ship:
    n: int                   # Exportcontainer
    start: int               # Beginn des Beladefensters (Stunde)
    length: int              # Länge des Fensters (h)
    pos: float               # Liegeplatz am Kai (m)
    berth: int


@dataclass(frozen=True, eq=False)
class Week:
    ships: tuple
    blocks: int
    y: tuple                 # Lage der Blöcke am Kai (m)
    mu: float                # Abrufrate je Block (Moves je Stunde)
    hours: int               # Zahl der Stunden (T)
    d: tuple                 # Fahrweg d[s][b] (m, einfach)
    total: int               # alle Exportcontainer der Woche (N)
    seed: int
    f: tuple                 # Abrufanteil je Stunde: f[s][t], Summe je Schiff 1
    h: tuple                 # Anlieferanteil je Stunde: h[s][t], Summe je Schiff 1
    g: tuple                 # Bestandsanteil im Block am Ende der Stunde: g[s][t]
    lf: tuple                # Lastanteil je Stunde = Abruf + Anlieferung: lf[s][t] (Summe je Schiff 2)
    limit: Optional[float]   # Lagergrenze K je Block (Container); None = unbegrenzt

    @property
    def n_ships(self):
        return len(self.ships)


def crane_rates(upper):
    """Abrufraten der Schiffe: die obere Rate r und zwei Drittel davon (60 -> 40, 90 -> 60, 120 -> 80 Moves je Stunde)."""
    return (float(upper * 2 // 3), float(upper))


def _fractions(ships, hours, delivery):
    f = tuple(tuple((1.0 / sh.length if sh.start <= t < sh.start + sh.length else 0.0) for t in range(hours)) for sh in ships)
    if delivery:
        h = tuple(tuple((1.0 / delivery if sh.start - delivery <= t < sh.start else 0.0) for t in range(hours)) for sh in ships)
    else:
        h = tuple(tuple(0.0 for _ in range(hours)) for _ in ships)
    return f, h


def _stock(ships, hours, f, h, delivery):
    """Bestandsanteil im Block (Ende der Stunde): angeliefert minus abgerufen; ohne Anlieferzeit liegt alles ab Beginn des Fensters im Block."""
    g = []
    for s, sh in enumerate(ships):
        row, cum_in, cum_out = [], 0.0, 0.0
        for t in range(hours):
            cum_in += h[s][t] if delivery else (1.0 if t == sh.start else 0.0)
            cum_out += f[s][t]
            v = cum_in - cum_out
            row.append(v if v > 1e-9 else 0.0)
        g.append(tuple(row))
    return tuple(g)


def make_week(seed, ships=6, blocks=8, mu=40.0, crane=90, fill=70, delivery=C.DELIVERY_HOURS, n_range=(C.N_LO, C.N_HI), span=C.ARRIVAL_SPAN):
    """Eine Woche. `fill` = Lagerfüllung im Spitzenbestand in Prozent (None: keine Lagergrenze); `delivery` = Anlieferzeit in Stunden (im Modell fest C.DELIVERY_HOURS; 0 nur für den Vergleich in
    Tests: ohne Anlieferlast trifft die einfache Regel den Rechenplan, siehe README); `n_range` und `span` (Container je Schiff, Ankunftsspanne in Stunden) gelten nur für Kleinstinstanzen in Tests."""
    rng = random.Random(seed)
    quay = blocks * C.PITCH
    berth_pos = [quay * (k + 0.5) / C.BERTHS for k in range(C.BERTHS)]
    arrivals = sorted(rng.randrange(0, span + 1) for _ in range(ships))
    free = [0] * C.BERTHS
    rates = crane_rates(crane)
    made = []
    for s in range(ships):
        n = rng.randint(*n_range)
        rho = rng.choice(rates)
        length = max(C.MIN_WINDOW, math.ceil(n / rho))
        k = min(range(C.BERTHS), key=lambda j: (free[j], j))
        start = max(arrivals[s], free[k])
        free[k] = start + length
        made.append(Ship(n, start, length, berth_pos[k], k))
    y = tuple(C.PITCH * (b + 0.5) for b in range(blocks))
    made = tuple(replace(sh, start=sh.start + delivery) for sh in made)                       # das Beladefenster beginnt nach der Anlieferzeit
    hours = max(sh.start + sh.length for sh in made) + C.TIME_PAD
    d = tuple(tuple(C.D0 + abs(sh.pos - y[b]) for b in range(blocks)) for sh in made)
    f, h = _fractions(made, hours, delivery)
    g = _stock(made, hours, f, h, delivery)
    lf = tuple(tuple(f[s][t] + h[s][t] for t in range(hours)) for s in range(ships))
    limit = None
    if fill is not None:
        limit = (100.0 / fill) * max(sum(g[s][t] * made[s].n for s in range(ships)) for t in range(hours)) / blocks
    return Week(made, blocks, y, float(mu), hours, d, sum(sh.n for sh in made), seed, f, h, g, lf, limit)


def peak_ratio(week):
    """Spitzenbedarf aller Schiffe gleichzeitig gegen die Gesamtrate der Blöcke (Belastung; über 1: das Lager kommt in der Spitze nicht mit)."""
    dem = [sum(sh.n / sh.length for sh in week.ships if sh.start <= t < sh.start + sh.length) for t in range(week.hours)]
    return max(dem) / (week.blocks * week.mu)


def shifted(week, deltas):
    """Dieselbe Woche, aber Schiff s hat sein Beladefenster um deltas[s] Stunden verschoben (Anlieferung und Bestand bleiben). Das Fenster bleibt innerhalb der Woche (Verschiebung nach hinten
    endet am Wochenende: bei σ bis 6 h praktisch nie nötig)."""
    ships = tuple(replace(sh, start=min(max(0, sh.start + dl), week.hours - sh.length)) for sh, dl in zip(week.ships, deltas))
    f = tuple(tuple((1.0 / sh.length if sh.start <= t < sh.start + sh.length else 0.0) for t in range(week.hours)) for sh in ships)
    lf = tuple(tuple(f[s][t] + week.h[s][t] for t in range(week.hours)) for s in range(week.n_ships))
    return replace(week, ships=ships, f=f, lf=lf)


def deltas(rng, n_ships, sigma):
    """Verschiebung des Beladefensters je Schiff in ganzen Stunden (gerundet aus N(0, sigma))."""
    return [int(round(rng.gauss(0.0, sigma))) for _ in range(n_ships)]


def scenario_set(seed, n_ships, sigma, n, base):
    """n Verschiebungsszenarien einer Woche; Seeds base + 1000 * seed + k (Planung und Test haben getrennte Basen, damit die Bewertung nie auf den Planungsszenarien läuft)."""
    return [deltas(random.Random(base + 1000 * seed + k), n_ships, sigma) for k in range(n)]


def train_scenarios(week, sigma):
    return scenario_set(week.seed, week.n_ships, sigma, C.N_TRAIN, C.TRAIN_BASE)


def evaluation_scenarios(week, sigma):
    return scenario_set(week.seed, week.n_ships, sigma, C.N_TEST, C.TEST_BASE)
