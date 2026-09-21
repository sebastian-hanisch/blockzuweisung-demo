"""Tests der Figuren: Portfolio-Konventionen (fixedrange, graue Marker-Linien, plotly_white), Inhalt (Punkte, Beschriftungen, Achsengrenzen, Farbskala), Randfälle (Ausreißer wird am Rand gezeichnet)."""

import pytest

import blz_constants as C
import blz_evaluation as E
import blz_visualization as V

P = E.Params(6, 8, 40, 90, 70, 3, 10)


@pytest.fixture(scope="module")
def res():
    return E.run_week(P, 2017)


@pytest.fixture(scope="module")
def curve(res):
    return E.price_curve(P, 2017, res)


@pytest.fixture(scope="module")
def rows():
    return E.sample(P, 3, 3000)


def assert_locked(fig):
    assert fig.layout.xaxis.fixedrange is True and fig.layout.yaxis.fixedrange is True
    for name in fig.layout:
        if name.startswith(("xaxis", "yaxis")):
            assert fig.layout[name].fixedrange is True, name


def test_tradeoff_with_curve_has_line_ring_and_squares_and_is_locked(res, curve):
    fig = V.tradeoff_figure(res.outcomes, curve, 10)
    assert_locked(fig)
    names = [t.name for t in fig.data]
    assert names[0] == "Gerechnet und abgesichert (Preis λ)" and names[1] == "eingestellt: λ = 10"
    assert names[2:] == ["Bündeln", "Verteilen", "Kranrate passend", "Gierig", "Gerechnet"]
    line = fig.data[0]
    assert list(line.x) == [pt.distance for pt in curve.points] and list(line.y) == [pt.wait_shift for pt in curve.points] and list(line.text) == ["λ 1", "λ 2", "λ 5", "λ 10", "λ 20", "λ 50", "λ 100"]
    ring = fig.data[1]
    assert list(ring.x) == [curve.points[3].distance] and list(ring.y) == [curve.points[3].wait_shift] and ring.marker.line.width == 3


def test_tradeoff_squares_are_the_rules_and_carry_the_grey_marker_line(res, curve):
    fig = V.tradeoff_figure(res.outcomes, curve, 10)
    by_name = {t.name: t for t in fig.data}
    for key in ("verteilen", "kranrate", "gierig", "gerechnet"):
        t = by_name[C.METHOD_SHORT[key]]
        assert list(t.x) == [res[key].m.distance] and list(t.y) == [res[key].robust.wait] and t.marker.symbol == "square" and t.marker.line.color == C.MARKER_LINE_COLOR and t.marker.color == C.METHOD_COLORS[key]
    assert "Gerechnet und abgesichert" not in by_name and by_name["Gerechnet"].marker.color == "#c0392b"


def test_the_outlier_bundling_is_drawn_at_the_axis_limit_and_labelled(res, curve):
    fig = V.tradeoff_figure(res.outcomes, curve, 10)
    bundle = next(t for t in fig.data if t.name == "Bündeln")
    others = [pt.wait_shift for pt in curve.points] + [res[k].robust.wait for k in ("verteilen", "kranrate", "gierig", "gerechnet")]
    limit = max(others + [1.0]) * 1.2
    assert res["buendeln"].robust.wait > limit                                                       # Stoßwoche: Bündeln wartet 185 min, alle anderen unter 60
    assert list(bundle.y) == [pytest.approx(limit)] and bundle.marker.symbol == "triangle-up" and list(bundle.x) == [res["buendeln"].m.distance]
    assert list(bundle.text)[0].startswith("Bündeln: 185 min (Achse gekürzt)")
    assert list(fig.layout.yaxis.range) == [0, pytest.approx(limit)]


def test_no_clipping_when_bundling_is_not_an_outlier():
    calm = E.run_week(E.Params(4, 8, 60, 60, 60, 1, 10), 2017)
    fig = V.tradeoff_figure(calm.outcomes)
    bundle = next(t for t in fig.data if t.name == "Bündeln")
    assert bundle.marker.symbol == "square" and list(bundle.text) == [""] and fig.layout.yaxis.range is None


def test_y_limit_only_applies_when_the_outlier_exceeds_it():
    assert V.y_limit([10.0, 20.0], 24.0) is None and V.y_limit([10.0, 20.0], 24.01) == pytest.approx(24.0) and V.y_limit([0.0, 0.0], 5.0) == pytest.approx(1.2) and V.y_limit([10.0], None) is None
    assert V.y_limit([None, 30.0], 40.0) == pytest.approx(36.0)


def test_comparison_without_curve_shows_all_six_methods_as_points(res):
    fig = V.tradeoff_figure(res.outcomes)
    assert_locked(fig)
    assert [t.name for t in fig.data] == ["Bündeln", "Verteilen", "Kranrate passend", "Gierig", "Gerechnet", "Gerechnet und abgesichert"]
    hedge = fig.data[-1]
    assert list(hedge.x) == [res["abgesichert"].m.distance] and list(hedge.y) == [res["abgesichert"].robust.wait]


def test_edge_figure_has_log_axis_the_edge_and_both_borders(curve):
    fig = V.edge_figure(curve)
    assert_locked(fig)
    assert fig.layout.xaxis.type == "log" and list(fig.layout.xaxis.tickvals) == [400, 200, 100, 50, 20, 10, 5, 2, 1]
    edge = fig.data[0]
    assert list(edge.x) == [400, 200, 100, 50, 20, 10, 5, 2, 1] and list(edge.y) == [d for _, d in curve.edge]
    names = [t.name for t in fig.data[1:]]
    assert names == [f"Bündeln ({curve.bundle_distance:.0f} m)", f"Verteilen ({curve.spread_distance:.0f} m)"]
    assert list(fig.data[1].y) == [curve.bundle_distance] * 2 and list(fig.data[2].y) == [curve.spread_distance] * 2 and list(fig.data[1].x) == [1, 400]


def test_assignment_heatmap_shows_the_plan_with_ship_labels(res):
    o = res["gerechnet"]
    fig = V.assignment_figure(res.week, o.x, "Titel")
    assert_locked(fig)
    hm = fig.data[0]
    assert [list(r) for r in hm.z] == [list(r) for r in o.x] and list(hm.y) == [f"Schiff {s + 1} ({sh.n})" for s, sh in enumerate(res.week.ships)] and list(hm.x) == [f"B{b + 1}" for b in range(8)]
    assert hm.text[0][0] in ("", str(o.x[0][0])) and all((t == "") == (v == 0) for tr, zr in zip(hm.text, o.x) for t, v in zip(tr, zr))
    assert fig.layout.yaxis.autorange == "reversed" and fig.layout.title.text == "Titel" and fig.layout.height == 90 + 34 * 6


def test_load_heatmap_is_in_percent_of_the_rate_with_a_scale_up_to_the_maximum(res):
    o = res["buendeln"]
    fig = V.load_figure(res.week, o.m.load, "Last")
    assert_locked(fig)
    hm = fig.data[0]
    assert hm.z[0][0] == pytest.approx(o.m.load[0][0] / 40 * 100) and max(max(r) for r in hm.z) == pytest.approx(o.m.peak * 100) and hm.zmin == 0
    assert hm.zmax == pytest.approx(o.m.peak * 100) and hm.zmax > 100                                # Bündeln: die Spitze liegt weit über 100 %
    scale = [list(s) for s in hm.colorscale]
    assert scale[1][0] == pytest.approx(100 / hm.zmax) and scale[1][1] == "#f0b429" and scale[-1][1] == "#b3261e"
    assert len(hm.x) == res.week.hours and list(hm.y) == [f"B{b + 1}" for b in range(8)]


def test_load_heatmap_scale_is_two_stops_when_no_block_exceeds_the_rate(res):
    o = res["verteilen"]
    fig = V.load_figure(res.week, o.m.load, "Last")
    hm = fig.data[0]
    assert hm.zmax == 100.0 and len(hm.colorscale) == 2 and hm.colorscale[1][1] == "#f0b429"          # mindestens 100 %


def test_shared_load_max_uses_the_larger_maximum_and_at_least_one_hundred_percent(res):
    b, s = res["buendeln"].m.load, res["verteilen"].m.load
    assert V.shared_load_max([b, s], 40.0) == pytest.approx(res["buendeln"].m.peak * 100) and V.shared_load_max([s], 40.0) == 100.0
    fig = V.load_figure(res.week, s, "Last", zmax=V.shared_load_max([b, s], 40.0))
    assert fig.data[0].zmax == pytest.approx(res["buendeln"].m.peak * 100)


def test_distribution_figure_stacks_better_equal_worse_and_hides_small_labels(rows):
    d = E.distribution(rows, "abgesichert", "gerechnet", "wait_shift")
    fig = V.distribution_figure([d], ["abgesichert"], "Gerechnet", "Wartezeit")
    assert_locked(fig)
    assert fig.layout.barmode == "stack" and [t.name for t in fig.data] == ["weniger Wartezeit als Gerechnet", "gleich", "mehr Wartezeit als Gerechnet"]
    assert [t.x[0] for t in fig.data] == pytest.approx([d.better * 100, d.equal * 100, d.worse * 100]) and [t.marker.color for t in fig.data] == ["#2e7d4f", "#8a94a3", "#c0392b"]
    small = E.Distribution("k", "f", 20, 0.9, 0.05, 0.05, 1.0, 1.0)
    fig2 = V.distribution_figure([small], ["x"], "R", "Wartezeit")
    assert list(fig2.data[0].text) == ["90 %"] and list(fig2.data[1].text) == [""] and list(fig2.data[2].text) == [""]
    assert list(fig2.layout.xaxis.range) == [0, 100]


def test_spread_figure_has_a_marker_at_the_median_and_bars_from_p10_to_p90(rows):
    fig = V.spread_figure(rows, "wait_shift", "Titel")
    assert_locked(fig)
    assert [t.y[0] for t in fig.data] == [C.METHOD_SHORT[k] for k in C.METHOD_KEYS]
    for t, key in zip(fig.data, C.METHOD_KEYS):
        med, lo, hi = E.spread_of(rows, key, "wait_shift")
        assert list(t.x) == [med] and list(t.error_x.array) == [hi - med] and list(t.error_x.arrayminus) == [med - lo] and t.marker.line.color == C.MARKER_LINE_COLOR and t.marker.color == C.METHOD_COLORS[key]
    assert fig.layout.xaxis.title.text == "Titel" and fig.layout.yaxis.autorange == "reversed"


def test_every_figure_uses_the_light_template_and_has_a_hover_text(res, curve, rows):
    figs = [V.tradeoff_figure(res.outcomes, curve, 10), V.edge_figure(curve), V.assignment_figure(res.week, res["gerechnet"].x, "a"), V.load_figure(res.week, res["gerechnet"].m.load, "b"),
            V.spread_figure(rows, "distance", "c"), V.distribution_figure([E.distribution(rows, "abgesichert", "gerechnet", "wait_shift")], ["x"], "R", "W")]
    for fig in figs:
        assert fig.layout.template.layout.paper_bgcolor == "white" or fig.layout.template.layout.plot_bgcolor == "white"
        assert all(getattr(t, "hovertemplate", None) or getattr(t, "hoverinfo", None) == "skip" for t in fig.data)
