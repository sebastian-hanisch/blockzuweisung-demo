"""Die vier Regeln (Bündeln, Verteilen, Kranrate passend, Gierig): schiffsweise, ganzzahlig, in Portionen zu 10 Containern.

Reihenfolge kanonisch (Schiffe nach (Beginn, Index), Blöcke nach (Fahrweg, Index)), damit Gleichstände deterministisch entschieden werden und alle Verfahren dieselbe Woche sehen. Wie die Regeln der
Messreihe (blz.py); "Kranrate passend" und alle Regeln mit Portionen prüfen den Lagerplatz (Korrektur 3 der Messreihe: ohne Prüfung verletzte "Kranrate passend" die Lagergrenze in 17 bis 30 von 30 Wochen)."""

import math

import blz_constants as C


def ship_order(week):
    return sorted(range(week.n_ships), key=lambda s: (week.ships[s].start, s))


def block_order(week, s):
    return sorted(range(week.blocks), key=lambda b: (week.d[s][b], b))


def split_rounded(n, weights):
    """Größte-Reste-Verteilung von n auf Gewichte (Gleichstand: kleinerer Index); die Summe ist genau n."""
    total = sum(weights)
    raw = [n * w / total for w in weights]
    base = [int(math.floor(r)) for r in raw]
    rest = n - sum(base)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:rest]:
        base[i] += 1
    return base


class _State:
    """Belegung der Blöcke über die Zeit: Bestand (Lagerplatz) und Last (Abrufe plus Anlieferungen)."""

    def __init__(self, week):
        self.week = week
        self.stock = [[0.0] * week.hours for _ in range(week.blocks)]
        self.load = [[0.0] * week.hours for _ in range(week.blocks)]

    def fits(self, s, b, take):
        limit = self.week.limit
        if limit is None:
            return True
        g = self.week.g[s]
        return all(self.stock[b][t] + take * g[t] <= limit + C.STOCK_EPS for t in range(self.week.hours) if g[t] > 0)

    def peak(self, s, b, take):
        lf = self.week.lf[s]
        return max(self.load[b][t] + take * lf[t] for t in range(self.week.hours) if lf[t] > 0) / self.week.mu

    def add(self, s, b, take):
        g, lf = self.week.g[s], self.week.lf[s]
        for t in range(self.week.hours):
            self.stock[b][t] += take * g[t]
            self.load[b][t] += take * lf[t]


def rule_bundle(week):
    """Bündeln: alle Container eines Schiffs in den nächsten Block; ist er nach Lagerplatz voll, in den nächsten (in Portionen)."""
    x = [[0] * week.blocks for _ in range(week.n_ships)]
    st = _State(week)
    for s in ship_order(week):
        left = week.ships[s].n
        order = block_order(week, s)
        while left:
            take = min(C.LOT, left)
            pick = next((b for b in order if st.fits(s, b, take)), order[0])
            x[s][pick] += take
            st.add(s, pick, take)
            left -= take
    return x


def rule_spread(week):
    """Verteilen: gleichmäßig auf alle Blöcke (Unterschied zwischen Blöcken höchstens ein Container)."""
    return [split_rounded(sh.n, [1] * week.blocks) for sh in week.ships]


def rule_kblocks(week):
    """Kranrate passend: k = aufgerundet(Abrufrate des Schiffs / Blockrate) nächste Blöcke, reihum in Portionen; ein Block ohne Lagerplatz wird übersprungen, der nächstnähere kommt hinzu."""
    x = [[0] * week.blocks for _ in range(week.n_ships)]
    st = _State(week)
    for s in ship_order(week):
        sh = week.ships[s]
        k = min(week.blocks, max(1, math.ceil(sh.n / sh.length / week.mu)))
        order = block_order(week, s)
        left, i = sh.n, 0
        while left:
            take = min(C.LOT, left)
            ring = [b for b in order if st.fits(s, b, take)]
            ring = ring[:k] if ring else [order[0]]
            pick = ring[i % len(ring)]
            i += 1
            x[s][pick] += take
            st.add(s, pick, take)
            left -= take
    return x


def rule_greedy(week, cap=C.CAP_HEADROOM):
    """Gierig: Schiff für Schiff nach Fensterbeginn, je Portion der nächste Block, dessen Spitzenauslastung im Fenster nach der Portion höchstens `cap` bleibt (sonst der Block mit der kleinsten)."""
    x = [[0] * week.blocks for _ in range(week.n_ships)]
    st = _State(week)
    for s in ship_order(week):
        left = week.ships[s].n
        order = block_order(week, s)
        while left:
            take = min(C.LOT, left)
            cand = [b for b in order if st.fits(s, b, take)] or list(order)
            peak = {b: st.peak(s, b, take) for b in cand}
            pick = next((b for b in cand if peak[b] <= cap + 1e-9), None)
            if pick is None:
                pick = min(cand, key=lambda b: (round(peak[b], 9), order.index(b)))
            x[s][pick] += take
            st.add(s, pick, take)
            left -= take
    return x
