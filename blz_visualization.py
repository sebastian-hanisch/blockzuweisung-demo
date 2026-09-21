"""Plotly-Figuren der Blockzuweisungs-Demo: Preis der Absicherung (Weg gegen Wartezeit bei Verspätung), Kante, Belegung Schiff x Block, Blocklast, Verteilung, Spannweite.

Konventionen des Portfolios: Achsen `fixedrange` (Touch-Scrollen), Vorlage plotly_white, Marker-Linien in mittlerem Grau, Überschriften stehen als Markdown ÜBER dem Diagramm. Plotly wird erst in den
Funktionen importiert, damit die reine Rechnung ohne Plotly testbar bleibt."""

import blz_constants as C
import blz_evaluation as E

LEGEND_BOTTOM = dict(orientation="h", yref="container", yanchor="bottom", y=0.0, x=0)
Y_HEADROOM = 1.2                         # obere Achsengrenze der Kurve: so viel über dem größten Wert, der nicht Bündeln ist
LOAD_MIN_MAX = 100.0                     # die Farbskala der Blocklast reicht mindestens bis 100 % der Rate


def _lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _marker(color, size=11, symbol="circle"):
    return dict(color=color, size=size, symbol=symbol, line=dict(color=C.MARKER_LINE_COLOR, width=1))


# ---------------------------------------------------------------------------------------------------
# Preis der Absicherung
# ---------------------------------------------------------------------------------------------------
def y_limit(values, clipped_key_value):
    """Obere Grenze der Wartezeit-Achse: die größten Werte ohne den Ausreißer (Bündeln wartet oft mehr als das Zehnfache) mal Luft; None, wenn nichts zu begrenzen ist."""
    top = max([v for v in values if v is not None] + [1.0]) * Y_HEADROOM
    return top if clipped_key_value is not None and clipped_key_value > top else None


def tradeoff_figure(outcomes, curve=None, lam_now=None):
    """Fahrweg (m, x) gegen Wartezeit bei Verspätung (min, y). Quadrate: die Verfahren der Woche (Bündeln, Verteilen, Kranrate passend, Gierig, Gerechnet); Linie: der Szenario-LP mit Preis λ
    (`curve`), der eingestellte Preis `lam_now` hervorgehoben. Ohne `curve` zeigt es alle sechs Verfahren als Punkte. Was weit über den übrigen liegt (Bündeln), wird an der Achsengrenze gezeichnet und
    beschriftet."""
    import plotly.graph_objects as go

    by_key = {o.key: o for o in outcomes}
    fig = go.Figure()
    rule_keys = [k for k in C.METHOD_KEYS if k != C.M_HEDGE] if curve is not None else list(C.METHOD_KEYS)
    non_bundle = [by_key[k].robust.wait for k in rule_keys if k != C.M_BUNDLE] + ([pt.wait_shift for pt in curve.points] if curve is not None else [by_key[C.M_HEDGE].robust.wait])
    bundle_wait = by_key[C.M_BUNDLE].robust.wait
    limit = y_limit(non_bundle, bundle_wait)
    if curve is not None:
        pts = curve.points
        fig.add_trace(go.Scatter(x=[pt.distance for pt in pts], y=[pt.wait_shift for pt in pts], mode="lines+markers+text", name="Gerechnet und abgesichert (Preis λ)", text=[f"λ {pt.lam:g}" for pt in pts],
                                 textposition="top right", line=dict(color=C.METHOD_COLORS[C.M_HEDGE], width=2.5), marker=_marker(C.METHOD_COLORS[C.M_HEDGE], 8), textfont=dict(size=10),
                                 hovertemplate="λ = %{text}<br>Weg %{x:.0f} m<br>Wartezeit bei Verspätung %{y:.1f} min<extra></extra>"))
        chosen = [pt for pt in pts if pt.lam == lam_now]
        if chosen:
            fig.add_trace(go.Scatter(x=[chosen[0].distance], y=[chosen[0].wait_shift], mode="markers", name=f"eingestellt: λ = {lam_now:g}", marker=dict(color="rgba(0,0,0,0)", size=20, symbol="circle",
                                     line=dict(color=C.METHOD_COLORS[C.M_HEDGE], width=3)), hoverinfo="skip"))
    for key in rule_keys:
        o = by_key[key]
        y = o.robust.wait
        clipped = limit is not None and y > limit
        fig.add_trace(go.Scatter(x=[o.m.distance], y=[limit if clipped else y], mode="markers+text", name=C.METHOD_SHORT[key] if key != C.M_HEDGE else "Gerechnet und abgesichert",
                                 marker=_marker(C.METHOD_COLORS[key], 12, "triangle-up" if clipped else "square"), text=[f"{C.METHOD_SHORT[key]}: {y:.0f} min (Achse gekürzt)" if clipped else ""],
                                 textposition="middle right" if clipped else "bottom left", textfont=dict(size=10),
                                 hovertemplate=f"<b>{C.METHOD_SHORT[key]}</b><br>Weg %{{x:.0f}} m<br>Wartezeit bei Verspätung {y:.1f} min<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT + 20, legend=LEGEND_BOTTOM, margin=dict(t=25, b=130), hovermode="closest", xaxis_title="Fahrweg je Container (m)",
                      yaxis_title="Wartezeit bei Verspätung (min)")
    fig.update_yaxes(range=[0, limit] if limit is not None else None, rangemode="tozero")
    return _lock_axes(fig)


def edge_figure(curve):
    """Kürzester Fahrweg (LP, pünktliche Schiffe) gegen die erlaubte Wartezeit (logarithmisch), dazu Bündeln und Verteilen als Ränder."""
    import plotly.graph_objects as go

    eps = [e for e, _ in curve.edge]
    dist = [d for _, d in curve.edge]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eps, y=dist, mode="lines+markers", name="kürzester Weg bei erlaubter Wartezeit", line=dict(color=C.METHOD_COLORS[C.M_LP], width=2.5), marker=_marker(C.METHOD_COLORS[C.M_LP], 8),
                             hovertemplate="erlaubte Wartezeit %{x} min<br>kürzester Weg %{y:.1f} m<extra></extra>"))
    for value, key in ((curve.bundle_distance, C.M_BUNDLE), (curve.spread_distance, C.M_SPREAD)):
        fig.add_trace(go.Scatter(x=[min(eps), max(eps)], y=[value, value], mode="lines", name=f"{C.METHOD_SHORT[key]} ({value:.0f} m)", line=dict(color=C.METHOD_COLORS[key], width=2, dash="dash"),
                                 hovertemplate=f"{C.METHOD_SHORT[key]}: {value:.0f} m<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT - 40, legend=LEGEND_BOTTOM, margin=dict(t=25, b=110), hovermode="closest", xaxis_title="erlaubte Wartezeit (min, logarithmisch)",
                      yaxis_title="Fahrweg je Container (m)")
    fig.update_xaxes(type="log", tickvals=eps, ticktext=[str(e) for e in eps])
    fig.update_yaxes(rangemode="normal")
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Die Woche: Belegung und Blocklast
# ---------------------------------------------------------------------------------------------------
def assignment_figure(week, x, title):
    """Belegung Schiff x Block als Heatmap mit Zahlen: wie viele Container von Schiff s in Block b liegen."""
    import plotly.graph_objects as go

    ships = [f"Schiff {s + 1} ({sh.n})" for s, sh in enumerate(week.ships)]
    blocks = [f"B{b + 1}" for b in range(week.blocks)]
    fig = go.Figure(go.Heatmap(z=[list(r) for r in x], x=blocks, y=ships, text=[[str(v) if v else "" for v in r] for r in x], texttemplate="%{text}", textfont=dict(size=10), colorscale=[[0, "#f4f7fb"], [1, "#2a6fb0"]],
                               showscale=False, xgap=1, ygap=1, hovertemplate="%{y}, Block %{x}: %{z} Container<extra></extra>"))
    fig.update_layout(title=dict(text=title, font=dict(size=13), x=0.02), template="plotly_white", height=90 + 34 * week.n_ships, margin=dict(t=44, b=10, l=10, r=8))
    fig.update_yaxes(autorange="reversed")
    return _lock_axes(fig)


def shared_load_max(loads, mu):
    """Gemeinsame obere Grenze der Farbskala (Prozent der Rate) für mehrere Blocklast-Diagramme, damit sie sich vergleichen lassen; mindestens 100 %."""
    return max([LOAD_MIN_MAX] + [max(max(row) for row in load) / mu * 100.0 for load in loads])


def load_figure(week, load, title, zmax=None):
    """Blocklast in Prozent der Rate (Block x Stunde): über 100 % wächst der Rückstand, unter 100 % baut er ab."""
    import plotly.graph_objects as go

    z = [[v / week.mu * 100.0 for v in row] for row in load]
    top = zmax if zmax is not None else shared_load_max([load], week.mu)
    if top > LOAD_MIN_MAX:
        scale = [[0, "#eef3f9"], [LOAD_MIN_MAX / top, "#f0b429"], [1, "#b3261e"]]
    else:
        scale = [[0, "#eef3f9"], [1, "#f0b429"]]
    fig = go.Figure(go.Heatmap(z=z, x=list(range(week.hours)), y=[f"B{b + 1}" for b in range(week.blocks)], zmin=0, zmax=top, colorscale=scale, colorbar=dict(title=dict(text="% der Rate"), thickness=10),
                               hovertemplate="Block %{y}, Stunde %{x}: %{z:.0f} % der Rate<extra></extra>"))
    fig.update_layout(title=dict(text=title, font=dict(size=13), x=0.02), template="plotly_white", height=110 + 22 * week.blocks, margin=dict(t=44, b=44, l=10, r=8), xaxis_title="Stunde der Woche")
    fig.update_yaxes(autorange="reversed")
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Stichprobe: Verteilung und Spannweite
# ---------------------------------------------------------------------------------------------------
def distribution_figure(dists, labels, reference_label, unit):
    """Je Zeile ein gestapelter Balken: Anteil der Wochen mit weniger / gleich viel / mehr (unit) als die Referenz."""
    import plotly.graph_objects as go

    fig = go.Figure()
    for attr, name in (("better", f"weniger {unit} als {reference_label}"), ("equal", "gleich"), ("worse", f"mehr {unit} als {reference_label}")):
        shares = [getattr(d, attr) * 100 for d in dists]
        fig.add_trace(go.Bar(y=labels, x=shares, orientation="h", name=name, marker_color=C.OUTCOME_COLORS[attr], text=[f"{v:.0f} %" if v >= 6 else "" for v in shares], textposition="inside",
                             insidetextanchor="middle", hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:.0f}} % der Wochen<extra></extra>"))
    fig.update_layout(barmode="stack", template="plotly_white", height=150 + 70 * len(dists), legend=dict(LEGEND_BOTTOM, y=-0.45, traceorder="normal"), margin=dict(t=20, b=110, l=10),
                      xaxis_title="Anteil der Wochen (%)")
    fig.update_xaxes(range=[0, 100])
    fig.update_yaxes(autorange="reversed")
    return _lock_axes(fig)


def spread_figure(rows, field, axis_title):
    """Je Verfahren der Median über die Wochen (Punkt) und das 10. bis 90. Perzentil (Balken): die Kennzahlen sind schief, das Mittel allein täuscht."""
    import plotly.graph_objects as go

    fig = go.Figure()
    for key in C.METHOD_KEYS:
        med, lo, hi = E.spread_of(rows, key, field)
        fig.add_trace(go.Scatter(x=[med], y=[C.METHOD_SHORT[key]], mode="markers", name=C.METHOD_SHORT[key], showlegend=False, marker=_marker(C.METHOD_COLORS[key], 11),
                                 error_x=dict(type="data", symmetric=False, array=[hi - med], arrayminus=[med - lo], color=C.METHOD_COLORS[key], thickness=2.5, width=6),
                                 hovertemplate=f"<b>{C.METHOD_SHORT[key]}</b><br>Median {med:.1f}<br>10. bis 90. Perzentil {lo:.1f} bis {hi:.1f}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=300, margin=dict(t=15, b=50, l=10, r=10), xaxis_title=axis_title, hovermode="closest")
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(rangemode="tozero")
    return _lock_axes(fig)
