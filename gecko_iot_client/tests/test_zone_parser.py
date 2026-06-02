"""
Unit tests for zone configuration parser.
"""

import unittest
from unittest.mock import patch

from src.gecko_iot_client.models.zone_parser import (
    ZoneConfigurationParser,
    _extract_value_from_config,
)
from src.gecko_iot_client.models.zone_types import FlowZone, LightingZone, ZoneType


class TestZoneParserUtilities(unittest.TestCase):
    """Test utility functions used by the zone parser."""

    def test_extract_value_from_config_direct_value(self):
        """Test extracting direct values."""
        self.assertEqual(_extract_value_from_config(42), 42)
        self.assertEqual(_extract_value_from_config("test"), "test")
        self.assertTrue(_extract_value_from_config(True))

    def test_extract_value_from_config_with_value_key(self):
        """Test extracting from config with 'value' key."""
        config = {"value": 50, "minimum": 0, "maximum": 100}
        self.assertEqual(_extract_value_from_config(config), 50)

    def test_extract_value_from_config_with_current_value(self):
        """Test extracting from config with 'currentValue' key."""
        config = {"currentValue": 75, "minimum": 0, "maximum": 100}
        self.assertEqual(_extract_value_from_config(config), 75)

    def test_extract_value_from_config_with_default(self):
        """Test extracting from config with 'default' key."""
        config = {"default": 25, "minimum": 0, "maximum": 100}
        self.assertEqual(_extract_value_from_config(config), 25)

    def test_extract_value_from_config_fallback_to_minimum(self):
        """Test falling back to minimum when no value keys found."""
        config = {"minimum": 10, "maximum": 100, "stepIncrement": 5}
        self.assertEqual(_extract_value_from_config(config), 10)

    def test_extract_value_from_config_no_value_found(self):
        """Test returning None when no value can be extracted."""
        config = {"someOtherKey": "someValue"}
        self.assertIsNone(_extract_value_from_config(config))


class TestZoneConfigurationParser(unittest.TestCase):
    """Test ZoneConfigurationParser class."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ZoneConfigurationParser()

    def test_parse_empty_configuration(self):
        """Test parsing empty configuration."""
        zones_config = {}
        result = self.parser.parse_zones_configuration(zones_config)
        self.assertEqual(result, {})

    def test_parse_unknown_zone_type(self):
        """Test parsing configuration with unknown zone type."""
        zones_config = {"unknownZoneType": {"1": {"name": "Test Zone"}}}

        with patch("src.gecko_iot_client.models.zone_parser.logger") as mock_logger:
            result = self.parser.parse_zones_configuration(zones_config)
            self.assertEqual(result, {})
            mock_logger.warning.assert_called_with("Unknown zone type: unknownZoneType")

    def test_parse_flow_zones(self):
        """Test parsing flow zone configuration."""
        zones_config = {
            "flow": {
                "1": {
                    "name": "Flow Zone 1",
                    "speed": {"value": 50, "minimum": 0, "maximum": 100},
                    "active": True,
                },
                "2": {
                    "name": "Flow Zone 2",
                    "speed": {
                        "minimum": 0,
                        "maximum": 100,
                    },  # Will use minimum as default
                    "active": False,
                },
            }
        }

        result = self.parser.parse_zones_configuration(zones_config)

        self.assertIn(ZoneType.FLOW_ZONE, result)
        flow_zones = result[ZoneType.FLOW_ZONE]
        self.assertEqual(len(flow_zones), 2)

        # Check first zone
        zone1 = flow_zones[0]
        self.assertIsInstance(zone1, FlowZone)
        self.assertEqual(zone1.id, "1")
        self.assertEqual(zone1.name, "Flow Zone 1")
        self.assertEqual(zone1.speed, 50.0)
        self.assertTrue(zone1.active)

        # Check second zone
        zone2 = flow_zones[1]
        self.assertEqual(zone2.id, "2")
        self.assertEqual(zone2.name, "Flow Zone 2")
        self.assertEqual(zone2.speed, 0.0)  # Should use minimum
        self.assertFalse(zone2.active)

    def test_parse_lighting_zones(self):
        """Test parsing lighting zone configuration."""
        zones_config = {
            "lighting": {
                "1": {"name": "Light Zone 1", "active": True, "effect": "rainbow"}
            }
        }

        result = self.parser.parse_zones_configuration(zones_config)

        self.assertIn(ZoneType.LIGHTING_ZONE, result)
        lighting_zones = result[ZoneType.LIGHTING_ZONE]
        self.assertEqual(len(lighting_zones), 1)

        zone = lighting_zones[0]
        self.assertIsInstance(zone, LightingZone)
        self.assertEqual(zone.id, "1")
        self.assertEqual(zone.name, "Light Zone 1")
        self.assertTrue(zone.active)
        self.assertEqual(zone.effect, "rainbow")

    def test_parse_mixed_zone_types(self):
        """Test parsing configuration with multiple zone types."""
        zones_config = {
            "flow": {"1": {"name": "Flow Zone", "speed": 25, "active": True}},
            "lighting": {"1": {"name": "Light Zone", "active": False}},
            "temperatureControl": {"1": {"name": "Temp Zone", "set_point": 22.0}},
        }

        result = self.parser.parse_zones_configuration(zones_config)

        self.assertEqual(len(result), 3)
        self.assertIn(ZoneType.FLOW_ZONE, result)
        self.assertIn(ZoneType.LIGHTING_ZONE, result)
        self.assertIn(ZoneType.TEMPERATURE_CONTROL_ZONE, result)

        # Verify each zone type has one zone
        self.assertEqual(len(result[ZoneType.FLOW_ZONE]), 1)
        self.assertEqual(len(result[ZoneType.LIGHTING_ZONE]), 1)
        self.assertEqual(len(result[ZoneType.TEMPERATURE_CONTROL_ZONE]), 1)

    def test_parse_with_empty_zone_ids(self):
        """Test parsing configuration with empty zone IDs (should be skipped)."""
        zones_config = {
            "flow": {
                "": {"name": "Empty ID Zone"},  # Should be skipped
                "1": {"name": "Valid Zone", "speed": 50, "active": True},
            }
        }

        result = self.parser.parse_zones_configuration(zones_config)

        self.assertIn(ZoneType.FLOW_ZONE, result)
        flow_zones = result[ZoneType.FLOW_ZONE]
        self.assertEqual(len(flow_zones), 1)  # Only the valid zone
        self.assertEqual(flow_zones[0].id, "1")

    def test_parse_with_invalid_zone_data(self):
        """Test parsing with invalid zone data that causes creation to fail."""
        zones_config = {
            "flow": {
                "1": {"name": "Valid Zone", "speed": 50, "active": True},
                "2": {
                    "speed": "invalid_speed_value"
                },  # This will cause validation error
            }
        }

        with patch("src.gecko_iot_client.models.zone_parser.logger") as mock_logger:
            result = self.parser.parse_zones_configuration(zones_config)

            # Should still get the valid zone
            self.assertIn(ZoneType.FLOW_ZONE, result)
            flow_zones = result[ZoneType.FLOW_ZONE]
            self.assertEqual(len(flow_zones), 1)
            self.assertEqual(flow_zones[0].id, "1")

            # Should have logged the warning about the invalid zone
            mock_logger.warning.assert_called()

    def test_zone_type_mapping(self):
        """Test that zone type mapping is correct."""
        self.assertEqual(self.parser.ZONE_TYPES["flow"], ZoneType.FLOW_ZONE)
        self.assertEqual(self.parser.ZONE_TYPES["lighting"], ZoneType.LIGHTING_ZONE)
        self.assertEqual(
            self.parser.ZONE_TYPES["temperatureControl"],
            ZoneType.TEMPERATURE_CONTROL_ZONE,
        )

    @patch("src.gecko_iot_client.models.zone_parser.logger")
    def test_logging_calls(self, mock_logger):
        """Test that appropriate logging calls are made."""
        zones_config = {
            "flow": {"1": {"name": "Test Zone", "speed": 50, "active": True}}
        }

        self.parser.parse_zones_configuration(zones_config)

        # Should log start and completion
        mock_logger.info.assert_any_call("Parsing zones configuration")
        mock_logger.info.assert_any_call("Parsed 1 zones successfully")


class TestApplyStateToZonesDesiredMerge(unittest.TestCase):
    """``apply_state_to_zones`` must overlay ``desired`` over ``reported`` so
    freshly-published setpoints don't get clobbered while ``reported`` is stale.

    We mock ``update_from_state`` and assert on what state dict the zone
    receives — that decouples the test from per-zone field-name quirks.
    """

    def setUp(self):
        self.parser = ZoneConfigurationParser()

    def _zones_with_flow_and_temp(self):
        return self.parser.parse_zones_configuration(
            {
                "flow": {"1": {"speed": {"minimum": 0, "maximum": 100}}},
                "temperatureControl": {
                    "1": {"minTemperatureSetPointC": 15, "maxTemperatureSetPointC": 40}
                },
            }
        )

    def test_desired_overlay_per_zone_id_on_setpoint(self):
        zones = self._zones_with_flow_and_temp()
        temp_zone = zones[ZoneType.TEMPERATURE_CONTROL_ZONE][0]
        state = {
            "state": {
                "reported": {"zones": {"temperatureControl": {"1": {"setPoint": 36}}}},
                "desired": {"zones": {"temperatureControl": {"1": {"setPoint": 38}}}},
            }
        }
        with patch.object(temp_zone, "update_from_state") as upd:
            self.parser.apply_state_to_zones(zones, state)
        upd.assert_called_once()
        applied = upd.call_args[0][0]
        # Desired wins on the setpoint; reported-only fields are preserved.
        self.assertEqual(applied["setPoint"], 38)

    def test_flow_active_alias_normalized(self):
        zones = self._zones_with_flow_and_temp()
        flow_zone = zones[ZoneType.FLOW_ZONE][0]
        state = {
            "state": {"reported": {"zones": {"flow": {"1": {"isActive": True, "speed": 50}}}}}
        }
        with patch.object(flow_zone, "update_from_state") as upd:
            self.parser.apply_state_to_zones(zones, state)
        applied = upd.call_args[0][0]
        # Both keys are populated regardless of which the shadow used.
        self.assertEqual(applied.get("active"), True)
        self.assertEqual(applied.get("isActive"), True)

    def test_reported_only_still_works(self):
        zones = self._zones_with_flow_and_temp()
        flow_zone = zones[ZoneType.FLOW_ZONE][0]
        state = {"state": {"reported": {"zones": {"flow": {"1": {"active": True, "speed": 30}}}}}}
        with patch.object(flow_zone, "update_from_state") as upd:
            self.parser.apply_state_to_zones(zones, state)
        self.assertEqual(upd.call_args[0][0].get("speed"), 30)

    def test_desired_only_still_works(self):
        zones = self._zones_with_flow_and_temp()
        flow_zone = zones[ZoneType.FLOW_ZONE][0]
        state = {"state": {"desired": {"zones": {"flow": {"1": {"active": True, "speed": 60}}}}}}
        with patch.object(flow_zone, "update_from_state") as upd:
            self.parser.apply_state_to_zones(zones, state)
        self.assertEqual(upd.call_args[0][0].get("speed"), 60)

    def test_reported_only_fields_preserved_when_desired_partial(self):
        """Partial ``desired`` (e.g. just setPoint) must not erase reported fields."""
        zones = self._zones_with_flow_and_temp()
        temp_zone = zones[ZoneType.TEMPERATURE_CONTROL_ZONE][0]
        state = {
            "state": {
                "reported": {
                    "zones": {
                        "temperatureControl": {
                            "1": {"setPoint": 36, "currentTemperature": 35}
                        }
                    }
                },
                "desired": {"zones": {"temperatureControl": {"1": {"setPoint": 38}}}},
            }
        }
        with patch.object(temp_zone, "update_from_state") as upd:
            self.parser.apply_state_to_zones(zones, state)
        applied = upd.call_args[0][0]
        self.assertEqual(applied["setPoint"], 38)
        self.assertEqual(applied["currentTemperature"], 35)


class TestMergeShadowZoneTrees(unittest.TestCase):
    """Direct unit tests for the merge helper."""

    def test_desired_overrides_reported_per_zone_id(self):
        merged = ZoneConfigurationParser._merge_shadow_zone_trees(
            {"temperatureControl": {"1": {"setPoint": 36, "currentTemp": 35}}},
            {"temperatureControl": {"1": {"setPoint": 38}}},
        )
        self.assertEqual(merged["temperatureControl"]["1"]["setPoint"], 38)
        # Fields only in reported are preserved.
        self.assertEqual(merged["temperatureControl"]["1"]["currentTemp"], 35)

    def test_disjoint_zone_ids_unioned(self):
        merged = ZoneConfigurationParser._merge_shadow_zone_trees(
            {"flow": {"1": {"speed": 50}}}, {"flow": {"2": {"speed": 80}}}
        )
        self.assertEqual(merged["flow"]["1"]["speed"], 50)
        self.assertEqual(merged["flow"]["2"]["speed"], 80)

    def test_empty_inputs_return_empty(self):
        self.assertEqual(ZoneConfigurationParser._merge_shadow_zone_trees({}, {}), {})

    def test_does_not_mutate_inputs(self):
        reported = {"flow": {"1": {"speed": 50}}}
        desired = {"flow": {"1": {"speed": 80}}}
        ZoneConfigurationParser._merge_shadow_zone_trees(reported, desired)
        self.assertEqual(reported, {"flow": {"1": {"speed": 50}}})
        self.assertEqual(desired, {"flow": {"1": {"speed": 80}}})


if __name__ == "__main__":
    unittest.main()
