"""Tests for extension_metrics shadow walking.

The module is pure Python and intentionally has no dependencies beyond
``math``/``re``, so these tests are equally light-weight.
"""

import unittest

from src.gecko_iot_client.extension_metrics import (
    KNOWN_ZONE_TYPES,
    extract_extension_booleans,
    extract_extension_metrics,
    extract_extension_strings,
    path_reserved_for_number_control,
    shadow_topology_summary,
)


def _shadow(reported=None, desired=None):
    state: dict[str, dict] = {}
    if reported is not None:
        state["reported"] = reported
    if desired is not None:
        state["desired"] = desired
    return {"state": state}


class TestExtractExtensionMetrics(unittest.TestCase):
    def test_returns_empty_for_no_state(self):
        self.assertEqual(extract_extension_metrics(None), {})
        self.assertEqual(extract_extension_metrics({}), {})
        self.assertEqual(extract_extension_metrics(_shadow(reported={})), {})

    def test_skips_known_zone_types(self):
        """Flow / lighting / temperatureControl already have first-class zones."""
        state = _shadow(
            reported={
                "zones": {
                    "flow": {"1": {"speed": 50, "active": True}},
                    "lighting": {"1": {"intensity": 80}},
                    "temperatureControl": {"1": {"setPoint": 36.5}},
                }
            }
        )
        self.assertEqual(extract_extension_metrics(state), {})

    def test_collects_unknown_zone_numeric_leaves(self):
        state = _shadow(
            reported={
                "zones": {
                    "energy": {"1": {"kwhToday": 12.3, "watts": 850}},
                    "heatPump": {"1": {"copEstimate": 4.1}},
                }
            }
        )
        out = extract_extension_metrics(state)
        self.assertEqual(out["zones.energy.1.kwhToday"], 12.3)
        self.assertEqual(out["zones.energy.1.watts"], 850)
        self.assertEqual(out["zones.heatPump.1.copEstimate"], 4.1)
        # Booleans must not bleed into the numeric output.
        self.assertNotIn("zones.energy.1.active", out)

    def test_walks_features_branch(self):
        state = _shadow(
            reported={
                "features": {
                    "waterlab": {
                        "readings": {"ph": 7.2, "orp": 720, "alkalinity": 110}
                    }
                }
            }
        )
        out = extract_extension_metrics(state)
        self.assertEqual(out["features.waterlab.readings.ph"], 7.2)
        self.assertEqual(out["features.waterlab.readings.orp"], 720)
        self.assertEqual(out["features.waterlab.readings.alkalinity"], 110)

    def test_drops_nan_and_inf(self):
        state = _shadow(
            reported={
                "features": {
                    "waterlab": {"readings": {"ph": float("nan"), "orp": float("inf")}}
                }
            }
        )
        out = extract_extension_metrics(state)
        self.assertNotIn("features.waterlab.readings.ph", out)
        self.assertNotIn("features.waterlab.readings.orp", out)


class TestExtractExtensionBooleans(unittest.TestCase):
    def test_collects_booleans_under_unknown_zones(self):
        state = _shadow(
            reported={"zones": {"energy": {"1": {"enabled": True, "watts": 800}}}}
        )
        out = extract_extension_booleans(state)
        self.assertEqual(out["zones.energy.1.enabled"], True)
        # Numeric leaves don't bleed in.
        self.assertNotIn("zones.energy.1.watts", out)


class TestExtractExtensionStrings(unittest.TestCase):
    def test_collects_short_strings(self):
        state = _shadow(
            reported={
                "features": {
                    "waterlab": {
                        "firmware": {"version": "1.2.3", "buildDate": "2026-04-22"}
                    }
                }
            }
        )
        out = extract_extension_strings(state)
        self.assertIn("features.waterlab.firmware.version", out)
        self.assertEqual(out["features.waterlab.firmware.version"], "1.2.3")


class TestShadowTopologySummary(unittest.TestCase):
    def test_summary_includes_unknown_zone_types(self):
        state = _shadow(
            reported={
                "zones": {
                    "flow": {"1": {}},
                    "energy": {"1": {}, "2": {}},
                },
                "features": {"waterlab": {}},
            }
        )
        summary = shadow_topology_summary(state)
        self.assertIsInstance(summary, dict)
        flat = repr(summary)
        # Either form of representation should mention the new branches.
        self.assertTrue("energy" in flat)
        self.assertTrue("waterlab" in flat)


class TestPathReservedForNumberControl(unittest.TestCase):
    def test_unknown_zone_setpoint_path_recognized(self):
        # Setpoint-shaped path on a non-builtin zone type should be marked
        # for number-control (rather than a read-only sensor).
        self.assertTrue(
            path_reserved_for_number_control("zones.energy.1.setPoint")
        )

    def test_random_leaf_is_not_reserved(self):
        self.assertFalse(path_reserved_for_number_control("zones.energy.1.watts"))
        self.assertFalse(path_reserved_for_number_control("features.waterlab.readings.ph"))


class TestKnownZoneTypes(unittest.TestCase):
    def test_known_zone_types_includes_builtins(self):
        self.assertIn("flow", KNOWN_ZONE_TYPES)
        self.assertIn("lighting", KNOWN_ZONE_TYPES)
        self.assertIn("temperatureControl", KNOWN_ZONE_TYPES)


if __name__ == "__main__":
    unittest.main()
