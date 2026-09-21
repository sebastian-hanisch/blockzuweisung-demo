"""Tests der Regler-Spezifikation: Permalink-Auswertung (begrenzen, einrasten, Müll ignorieren), Presets innerhalb der Reglergrenzen, Konsistenz mit den Konstanten."""

import blz_constants as C
import blz_presets as P

S = P.SETTING_SPECS


def test_parse_clamps_to_range():
    assert P.parse_setting(S["ships_slider"], "99") == 8 and P.parse_setting(S["ships_slider"], "1") == 3 and P.parse_setting(S["ships_slider"], "5") == 5
    assert P.parse_setting(S["blocks_slider"], "2") == 6 and P.parse_setting(S["blocks_slider"], "30") == 10
    assert P.parse_setting(S["seed_input"], "12345") == 9999 and P.parse_setting(S["seed_input"], "-4") == 0 and P.parse_setting(S["sigma_slider"], "50") == 6 and P.parse_setting(S["sigma_slider"], "-1") == 0


def test_parse_snaps_to_step_from_lower_bound():
    rate, crane, fill = S["rate_slider"], S["crane_slider"], S["fill_slider"]
    assert P.parse_setting(rate, "44") == 40 and P.parse_setting(rate, "46") == 50 and P.parse_setting(rate, "1") == 30 and P.parse_setting(rate, "500") == 60
    assert P.parse_setting(crane, "70") == 60 and P.parse_setting(crane, "80") == 90 and P.parse_setting(crane, "111") == 120 and P.parse_setting(crane, "5") == 60
    assert P.parse_setting(fill, "72") == 70 and P.parse_setting(fill, "73") == 75 and P.parse_setting(fill, "10") == 50 and P.parse_setting(fill, "99") == 90
    assert P.parse_setting(rate, "35") == 30 and P.parse_setting(rate, "45") == 50                    # Python rundet halbe Werte zur geraden Zahl: 0,5 Schritte -> 0, 1,5 -> 2


def test_step_grid_starts_at_the_lower_bound_not_at_zero():
    spec = P.SettingSpec("x", int, 1, 1, 21, 5)
    assert [P.parse_setting(spec, str(v)) for v in (1, 3, 4, 7, 9, 14, 19, 21)] == [1, 1, 6, 6, 11, 16, 21, 21]


def test_a_step_of_two_snaps_too_and_a_float_setting_rejects_non_finite_values():
    even = P.SettingSpec("x", float, 0.0, 0.0, 10.0, 2)
    assert [P.parse_setting(even, v) for v in ("3.3", "2.9", "9.1", "4", "0", "12")] == [4.0, 2.0, 10.0, 4.0, 0.0, 10.0]
    real = P.SettingSpec("y", float, 1.0, 0.0, 10.0)
    assert P.parse_setting(real, "nan") is None and P.parse_setting(real, "inf") is None and P.parse_setting(real, "-inf") is None
    assert P.parse_setting(real, "2.5") == 2.5 and P.parse_setting(real, "99") == 10.0


def test_the_price_snaps_to_the_nearest_allowed_value():
    lam = S["lam_slider"]
    assert [P.parse_setting(lam, v) for v in ("2", "5", "10", "20", "50")] == [2, 5, 10, 20, 50]
    assert P.parse_setting(lam, "1") == 2 and P.parse_setting(lam, "100") == 50 and P.parse_setting(lam, "7") == 5 and P.parse_setting(lam, "8") == 10 and P.parse_setting(lam, "30") == 20 and P.parse_setting(lam, "36") == 50
    assert P.parse_setting(lam, "3.4") == 2 and P.parse_setting(lam, "3.6") == 5
    assert P.parse_setting(lam, "3.5") == 2 and P.parse_setting(lam, "15") == 10                      # Gleichstand: der kleinere Wert
    assert P.parse_setting(lam, "abc") is None and P.parse_setting(lam, "nan") is None and P.parse_setting(lam, "inf") is None and P.parse_setting(lam, None) is None


def test_parse_ignores_garbage():
    for key in ("ships_slider", "seed_input", "rate_slider", "fill_slider", "sigma_slider"):
        assert P.parse_setting(S[key], "abc") is None and P.parse_setting(S[key], None) is None and P.parse_setting(S[key], "") is None
    assert P.parse_setting(S["ships_slider"], "4.5") is None                                            # nur ganze Zahlen
    assert P.parse_setting(S["view_radio"], "junk") is None and P.parse_setting(S["view_radio"], "") is None
    assert [m for m in C.METHOD_KEYS if P.parse_setting(S["view_radio"], m) == m] == list(C.METHOD_KEYS)


def test_specs_match_constants_and_defaults_inside_bounds():
    assert S["ships_slider"].default == C.SHIPS_DEFAULT == 6 and S["blocks_slider"].default == 8 and S["rate_slider"].default == 40 and S["crane_slider"].default == 90
    assert S["fill_slider"].default == 70 and S["sigma_slider"].default == 3 and S["lam_slider"].default == 10 and S["seed_input"].default == C.SEED_DEFAULT == 2017 and S["view_radio"].default == "abgesichert"
    for spec in S.values():
        if spec.lo is not None:
            assert spec.lo <= spec.default <= spec.hi


def test_url_params_are_unique_and_short():
    params = [s.url_param for s in S.values()]
    assert len(params) == len(set(params)) and all(len(p) <= 4 for p in params)
    assert {k: s.url_param for k, s in S.items()} == {"ships_slider": "sh", "blocks_slider": "bl", "rate_slider": "mu", "crane_slider": "cr", "fill_slider": "fl", "sigma_slider": "sg",
                                                       "lam_slider": "lm", "seed_input": "seed", "view_radio": "vw"}


def test_encoders_round_trip_through_the_parser():
    for key, spec in S.items():
        assert P.parse_setting(spec, spec.encoder(spec.default)) == spec.default, key


def test_every_preset_covers_all_settings_and_lies_inside_the_widget_grid():
    assert set(P.PRESET_STATE_KEYS.values()) == {k for k in S if k != "view_radio"}
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_STATE_KEYS), name
        for field, state_key in P.PRESET_STATE_KEYS.items():
            spec = S[state_key]
            v = preset[field]
            if spec.lo is not None:
                assert spec.lo <= v <= spec.hi and (spec.step in (None, 1) or (v - spec.lo) % spec.step == 0), (name, field, v)
            if state_key == "lam_slider":
                assert v in C.LAM_CHOICES


def test_preset_names_are_short_enough_for_three_buttons_per_row():
    assert all(len(n) <= 16 for n in C.PRESETS) and len(C.PRESETS) == 5
    assert C.PRESETS["Späte Schiffe"]["sigma"] == 5 and C.PRESETS["Voller Platz"]["fill"] == 90 and C.PRESETS["Starke Kräne"]["crane"] == 120 and C.PRESETS["Starke Kräne"]["ships"] == 5
    ruhig = C.PRESETS["Ruhige Woche"]
    assert (ruhig["ships"], ruhig["mu"], ruhig["crane"], ruhig["fill"], ruhig["sigma"]) == (4, 60, 60, 60, 1)
    assert C.PRESETS["Stoßwoche"] == dict(ships=6, blocks=8, mu=40, crane=90, fill=70, sigma=3, lam=10, seed=2017)
