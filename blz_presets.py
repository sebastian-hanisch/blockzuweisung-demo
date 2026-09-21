"""Regler-Spezifikation, Permalink, Presets und Seed-Knopf (Standardmuster aus dem OR-Demo-Portfolio, siehe gate_presets.py)."""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import blz_constants as C


def _view(raw):
    if raw not in C.METHOD_KEYS:
        raise ValueError(raw)
    return raw


def _lam(raw):
    """Preis der Wartezeit: der nächste erlaubte Wert (die Regler-Stufen 2 / 5 / 10 / 20 / 50)."""
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(raw)
    return min(C.LAM_CHOICES, key=lambda c: (abs(c - value), c))


def _int_text(value):
    return str(int(value))


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None
    step: Optional[int] = None
    encoder: Callable = _int_text


SETTING_SPECS = {
    "ships_slider": SettingSpec("sh", int, C.SHIPS_DEFAULT, *C.SHIPS_RANGE, 1),
    "blocks_slider": SettingSpec("bl", int, C.BLOCKS_DEFAULT, *C.BLOCKS_RANGE, 1),
    "rate_slider": SettingSpec("mu", int, C.RATE_DEFAULT, *C.RATE_RANGE, C.RATE_STEP),
    "crane_slider": SettingSpec("cr", int, C.CRANE_DEFAULT, *C.CRANE_RANGE, C.CRANE_STEP),
    "fill_slider": SettingSpec("fl", int, C.FILL_DEFAULT, *C.FILL_RANGE, C.FILL_STEP),
    "sigma_slider": SettingSpec("sg", int, C.SIGMA_DEFAULT, *C.SIGMA_RANGE, 1),
    "lam_slider": SettingSpec("lm", _lam, C.LAM_DEFAULT),
    "seed_input": SettingSpec("seed", int, C.SEED_DEFAULT, *C.SEED_RANGE, 1),
    "view_radio": SettingSpec("vw", _view, C.VIEW_DEFAULT, encoder=str),
}

PRESET_STATE_KEYS = {"ships": "ships_slider", "blocks": "blocks_slider", "mu": "rate_slider", "crane": "crane_slider", "fill": "fill_slider", "sigma": "sigma_slider", "lam": "lam_slider",
                     "seed": "seed_input"}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def parse_setting(spec, raw):
    """Wert aus der Adresszeile: umwandeln, auf den Bereich begrenzen, auf die Schrittweite runden. None, wenn er sich nicht auswerten lässt."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    if spec.step and spec.step > 1 and spec.lo is not None:
        value = spec.lo + round((value - spec.lo) / spec.step) * spec.step
        value = min(spec.hi, value)
    return value


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = parse_setting(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """values: dict state_key -> aktueller Wert (aus den Widgets, damit dieselbe Änderung, die gerade gerendert wurde, sofort in der Adresszeile landet)."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = SETTING_SPECS[state_key].encoder(value)
    except Exception:
        pass


def apply_preset(name):
    for field, state_key in PRESET_STATE_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][field]


def randomize_seed():
    """Würfelt einen neuen Seed für die Woche."""
    st.session_state["seed_input"] = random.randint(*C.SEED_RANGE)
