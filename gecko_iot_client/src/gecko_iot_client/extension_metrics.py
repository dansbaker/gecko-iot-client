"""Extract extension metrics from Gecko device-shadow state.

The base Gecko configuration only models flow / lighting / temperatureControl
zones. Many devices publish additional state under other shadow branches
(e.g. ``zones.energy``, ``zones.heatPump``, ``features.waterlab``, etc.) —
this module walks those branches and collects numeric, boolean, and string
leaves so consumers (e.g. the Home Assistant integration) can surface them
without hard-coding every possible field name.

This module is intentionally pure Python: it does no I/O and does not
depend on Home Assistant or any other downstream consumer. Higher-level
device-class / unit / icon mapping belongs in the consumer.

The walking logic was originally written by Markus Lassfolk for the
``hass_gecko_in_touch3_spa`` fork; this is a refactored, dependency-free
port of the pure-Python portion of his ``shadow_metrics.py``.

Key entry points:

* :func:`extract_extension_metrics` — numeric leaves
* :func:`extract_extension_booleans` — boolean leaves
* :func:`extract_extension_strings` — short string leaves (firmware versions etc.)
* :func:`shadow_topology_summary` — high-level zones/feature key map
* :func:`path_reserved_for_number_control` — recognizes unknown-zone
  setpoint paths the consumer may want to expose as writable controls
  instead of read-only sensors.
"""

from __future__ import annotations

import math
import re
from typing import Any

KNOWN_ZONE_TYPES = frozenset({"flow", "lighting", "temperatureControl"})

_MAX_DEPTH = 16
_MAX_SENSORS = 192
_MAX_BOOLEANS = 128
_MAX_STRINGS = 128

_UNKNOWN_ZONE_SETPOINT_RE = re.compile(
    r"^zones\.(?P<zt>[^.]+)\.(?P<zid>[^.]+)\.(?P<leaf>[^.]+)$"
)
_SETPOINT_LEAF_RE = re.compile(
    r"(setpoint|set_point|targettemp|target_temp|targettemperature|goal|sp)$",
    re.IGNORECASE,
)


def path_reserved_for_number_control(path: str) -> bool:
    """True for single-leaf unknown-zone paths that get a Number entity instead of Sensor."""
    m = _UNKNOWN_ZONE_SETPOINT_RE.match(path)
    if not m:
        return False
    zt = m.group("zt")
    if zt in KNOWN_ZONE_TYPES:
        return False
    return bool(_SETPOINT_LEAF_RE.search(m.group("leaf")))


def _path_looks_sensitive(path: str) -> bool:
    lower = path.lower()
    return any(
        tok in lower
        for tok in ("password", "secret", "token", "credential", "ssid", "email")
    )


def _string_value_ok(s: str) -> bool:
    if not s or len(s) > 255:
        return False
    if s.startswith("eyJ"):
        return False
    return True


def _path_segments(path: str) -> list[str]:
    """Lowercased path segments (``.`` / ``_`` / ``-`` and camelCase boundaries).

    Matches ``shadow_dump._key_segments`` style so tokens like ``phosphateLevel``
    become ``phosphate`` + ``level``, letting ``_PH_FALSE_POSITIVE_SEGMENTS`` apply.
    """
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", path)
    return [s for s in re.split(r"[._-]+", spaced.lower()) if s]


_PH_FALSE_POSITIVE_SEGMENTS = frozenset(
    {
        "phase",
        "phone",
        "photo",
        "phantom",
        "phosphate",
        "photon",
        "physical",
        "phonetic",
        "phoning",
        "phoney",
        "phosphor",
    }
)

_ORP_FALSE_POSITIVE_SEGMENTS = frozenset({"orphan", "orphaned"})


def _segment_is_ph(seg: str) -> bool:
    """True if segment denotes pH (handles camelCase keys like ``phValue`` → ``phvalue``)."""
    seg = seg.lower()
    if seg == "ph":
        return True
    if not seg.startswith("ph"):
        return False
    if seg.startswith("phosphate"):
        return False
    if seg in _PH_FALSE_POSITIVE_SEGMENTS:
        return False
    return bool(re.fullmatch(r"ph[a-z0-9]+", seg))


def _segment_is_orp(seg: str) -> bool:
    """True for ORP tokens including ``orpValue`` / ``orpmv`` style segments."""
    seg = seg.lower()
    if seg == "orp":
        return True
    if not seg.startswith("orp"):
        return False
    if seg in _ORP_FALSE_POSITIVE_SEGMENTS:
        return False
    return bool(re.fullmatch(r"orp[a-z0-9]+", seg))


def _is_calibration_or_model_param_path(path: str) -> bool:
    """True when the path is sensor calibration / thermistor model data, not a live reading.

    Derived from production shadow samples under ``features.waterlab.sensor.*`` where
    ``ph`` / ``orp`` leaves are offset/slope in mV, and ``therm`` holds R0/T0/beta.
    """
    lower = path.lower()
    # Millivolt offsets and slopes (Waterlab pH/ORP sensor calibration).
    if (
        "offsetmv" in lower
        or "slopemv" in lower
        or "mvperph" in lower
        or "mvatph" in lower
    ):
        return True
    # Thermistor / NTC model parameters (not spa water temperature).
    if re.search(r"\.therm\.(r0|t0|beta)(\.|$)", lower):
        return True
    return False


def _get_reported(state_data: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize shadow payload to the ``reported`` object."""
    if not state_data or not isinstance(state_data, dict):
        return {}
    inner = state_data.get("state")
    if isinstance(inner, dict):
        reported = inner.get("reported")
        if isinstance(reported, dict):
            return reported
    reported = state_data.get("reported")
    if isinstance(reported, dict):
        return reported
    return {}


def _flatten_numeric(
    obj: Any,
    prefix: str,
    out: dict[str, float | int],
    depth: int,
) -> None:
    """Append numeric leaves to ``out`` keyed by dotted path."""
    if depth > _MAX_DEPTH or len(out) >= _MAX_SENSORS:
        return
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return
        out[prefix] = obj
        return
    if not isinstance(obj, dict):
        return
    for key, val in obj.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        _flatten_numeric(val, path, out, depth + 1)


def _flatten_bool(
    obj: Any,
    prefix: str,
    out: dict[str, bool],
    depth: int,
) -> None:
    if depth > _MAX_DEPTH or len(out) >= _MAX_BOOLEANS:
        return
    if isinstance(obj, bool):
        out[prefix] = obj
        return
    if not isinstance(obj, dict):
        return
    for key, val in obj.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        _flatten_bool(val, path, out, depth + 1)


def _flatten_string(
    obj: Any,
    prefix: str,
    out: dict[str, str],
    depth: int,
) -> None:
    if depth > _MAX_DEPTH or len(out) >= _MAX_STRINGS:
        return
    if isinstance(obj, str):
        if _string_value_ok(obj) and not _path_looks_sensitive(prefix):
            out[prefix] = obj
        return
    if not isinstance(obj, dict):
        return
    for key, val in obj.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        _flatten_string(val, path, out, depth + 1)


def extract_extension_metrics(
    state_data: dict[str, Any] | None,
) -> dict[str, float | int]:
    """Return path -> numeric value for unknown zone types and non-mode features."""
    reported = _get_reported(state_data)
    if not reported:
        return {}

    out: dict[str, float | int] = {}

    zones = reported.get("zones")
    if isinstance(zones, dict):
        for zone_type, zone_bundle in zones.items():
            if not isinstance(zone_type, str) or not isinstance(zone_bundle, dict):
                continue
            if zone_type in KNOWN_ZONE_TYPES:
                continue
            for zone_id, zone_state in zone_bundle.items():
                if not isinstance(zone_id, str):
                    continue
                base = f"zones.{zone_type}.{zone_id}"
                _flatten_numeric(zone_state, base, out, 0)

    features = reported.get("features")
    if isinstance(features, dict):
        for feat_key, feat_val in features.items():
            if not isinstance(feat_key, str):
                continue
            _flatten_numeric(feat_val, f"features.{feat_key}", out, 0)

    # Do not flatten arbitrary other top-level ``reported`` keys: firmware counters,
    # timestamps, and vendor metadata would become misleading "measurement" sensors.

    # Top-level connectivity / RF-style roots (skipped above to avoid crowding chemistry).
    for root_key, root_val in reported.items():
        if not isinstance(root_key, str):
            continue
        lk = root_key.lower()
        if lk == "connectivity" or lk.startswith("connectivity"):
            _flatten_numeric(root_val, root_key, out, 0)

    return out


def _iter_extension_bases(
    state_data: dict[str, Any] | None,
) -> list[tuple[str, Any]]:
    """(prefix, subtree) pairs matching extension numeric coverage (bool/string)."""
    reported = _get_reported(state_data)
    if not reported:
        return []
    pairs: list[tuple[str, Any]] = []
    zones = reported.get("zones")
    if isinstance(zones, dict):
        for zone_type, zone_bundle in zones.items():
            if not isinstance(zone_type, str) or not isinstance(zone_bundle, dict):
                continue
            if zone_type in KNOWN_ZONE_TYPES:
                continue
            for zone_id, zone_state in zone_bundle.items():
                if not isinstance(zone_id, str):
                    continue
                pairs.append((f"zones.{zone_type}.{zone_id}", zone_state))
    features = reported.get("features")
    if isinstance(features, dict):
        for feat_key, feat_val in features.items():
            if not isinstance(feat_key, str):
                continue
            pairs.append((f"features.{feat_key}", feat_val))
    for root_key, root_val in reported.items():
        if not isinstance(root_key, str):
            continue
        lk = root_key.lower()
        if lk == "connectivity" or lk.startswith("connectivity"):
            pairs.append((root_key, root_val))

    return pairs


def extract_extension_booleans(
    state_data: dict[str, Any] | None,
) -> dict[str, bool]:
    """Boolean leaves under unknown zones, features, and other reported roots."""
    out: dict[str, bool] = {}
    for base, obj in _iter_extension_bases(state_data):
        if _path_looks_sensitive(base):
            continue
        _flatten_bool(obj, base, out, 0)
    return out


def extract_extension_strings(
    state_data: dict[str, Any] | None,
) -> dict[str, str]:
    """String leaves (short, non-sensitive paths) for text sensors."""
    out: dict[str, str] = {}
    for base, obj in _iter_extension_bases(state_data):
        if _path_looks_sensitive(base):
            continue
        _flatten_string(obj, base, out, 0)
    # Watercare mode is already a Select entity; skip duplicate strings.
    return {
        k: v
        for k, v in out.items()
        if not k.lower().startswith("features.operationmode")
    }


def shadow_topology_summary(state_data: dict[str, Any] | None) -> dict[str, Any]:
    """Redacted structural summary for diagnostics (no large leaf values)."""
    reported = _get_reported(state_data)
    if not reported:
        return {"reported_top_level_keys": []}

    summary: dict[str, Any] = {
        "reported_top_level_keys": sorted(reported.keys()),
    }

    zones = reported.get("zones")
    if isinstance(zones, dict):
        summary["zones_zone_type_keys"] = sorted(zones.keys())
        unknown = sorted(
            k for k in zones if isinstance(k, str) and k not in KNOWN_ZONE_TYPES
        )
        summary["zones_unknown_types"] = unknown
        for zt in unknown[:8]:
            zb = zones.get(zt)
            if isinstance(zb, dict):
                summary[f"zones.{zt}_zone_ids"] = sorted(zb.keys())[:16]

    features = reported.get("features")
    if isinstance(features, dict):
        summary["features_keys"] = sorted(features.keys())

    return summary

