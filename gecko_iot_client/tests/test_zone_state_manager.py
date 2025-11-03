"""
Unit tests for zone state manager functionality.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from concurrent.futures import Future
from typing import Dict, Any

from gecko_iot_client.models.zone_state_manager import ZoneStateManager, ZoneStateUpdateError
from gecko_iot_client.models.zone_types import TemperatureControlZone, FlowZone, LightingZone


class TestZoneStateManager(unittest.TestCase):
    """Test cases for ZoneStateManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_transporter = Mock()
        self.state_manager = ZoneStateManager(self.mock_transporter)
        
        # Create test zones
        self.temp_zone = TemperatureControlZone(
            id="temp_1",
            zone_type="temperatureControl",
            name="Test Heater",
            set_point=22.0,
            temperature_=20.5
        )
        
        self.flow_zone = FlowZone(
            id="flow_1",
            zone_type="flow",
            name="Test Pump",
            speed=60.0
        )
        
        self.lighting_zone = LightingZone(
            id="light_1",
            zone_type="lighting",
            name="Test Light",
            rgbi={"r": 100, "g": 150, "b": 200},
            active=True
        )

    def test_initialization(self):
        """Test ZoneStateManager initialization."""
        manager = ZoneStateManager()
        self.assertIsNone(manager.transporter)
        self.assertEqual(manager._pending_updates, {})
        self.assertEqual(manager._update_callbacks, [])

    def test_set_transporter(self):
        """Test setting transporter."""
        new_transporter = Mock()
        self.state_manager.set_transporter(new_transporter)
        self.assertEqual(self.state_manager.transporter, new_transporter)

    def test_update_zone_desired_state_no_transporter(self):
        """Test update_zone_desired_state raises error without transporter."""
        manager = ZoneStateManager()
        
        with self.assertRaises(ZoneStateUpdateError) as cm:
            manager.update_zone_desired_state(self.temp_zone, {"set_point": 25.0})
        
        self.assertIn("No transporter configured", str(cm.exception))

    def test_update_zone_desired_state_unsupported_transporter(self):
        """Test update_zone_desired_state raises error if transporter doesn't support desired state."""
        unsupported_transporter = Mock()
        delattr(unsupported_transporter, 'publish_desired_state')  # Remove the method
        
        manager = ZoneStateManager(unsupported_transporter)
        
        with self.assertRaises(ZoneStateUpdateError) as cm:
            manager.update_zone_desired_state(self.temp_zone, {"set_point": 25.0})
        
        self.assertIn("does not support desired state publishing", str(cm.exception))

    def test_update_zone_desired_state_success(self):
        """Test successful zone desired state update."""
        # Mock successful future
        mock_future = Mock(spec=Future)
        self.mock_transporter.publish_desired_state.return_value = mock_future
        
        updates = {"set_point": 25.0}
        result = self.state_manager.update_zone_desired_state(self.temp_zone, updates)
        
        # Verify transporter was called correctly
        self.mock_transporter.publish_desired_state.assert_called_once_with(
            "temperatureControl", "temp_1", updates
        )
        
        # Verify pending update is tracked
        self.assertIn("temp_1", self.state_manager._pending_updates)
        self.assertEqual(self.state_manager._pending_updates["temp_1"], updates)
        
        # Verify future is returned
        self.assertEqual(result, mock_future)

    def test_update_multiple_zones_no_transporter(self):
        """Test update_multiple_zones raises error without transporter."""
        manager = ZoneStateManager()
        zone_updates = [(self.temp_zone, {"set_point": 25.0})]
        
        with self.assertRaises(ZoneStateUpdateError) as cm:
            manager.update_multiple_zones(zone_updates)
        
        self.assertIn("No transporter configured", str(cm.exception))

    def test_update_multiple_zones_unsupported_transporter(self):
        """Test update_multiple_zones raises error if transporter doesn't support batch updates."""
        unsupported_transporter = Mock()
        delattr(unsupported_transporter, 'publish_batch_desired_state')
        
        manager = ZoneStateManager(unsupported_transporter)
        zone_updates = [(self.temp_zone, {"set_point": 25.0})]
        
        with self.assertRaises(ZoneStateUpdateError) as cm:
            manager.update_multiple_zones(zone_updates)
        
        self.assertIn("does not support batch desired state publishing", str(cm.exception))

    def test_update_multiple_zones_success(self):
        """Test successful multiple zone updates."""
        # Mock successful future
        mock_future = Mock(spec=Future)
        self.mock_transporter.publish_batch_desired_state.return_value = mock_future
        
        zone_updates = [
            (self.temp_zone, {"set_point": 25.0}),
            (self.flow_zone, {"speed": 80.0}),
            (self.lighting_zone, {"rgbi": {"r": 255, "g": 0, "b": 0}})
        ]
        
        result = self.state_manager.update_multiple_zones(zone_updates)
        
        # Verify transporter was called with correct grouped data
        expected_grouped = {
            "temperatureControl": {"temp_1": {"set_point": 25.0}},
            "flow": {"flow_1": {"speed": 80.0}},
            "lighting": {"light_1": {"rgbi": {"r": 255, "g": 0, "b": 0}}}
        }
        
        self.mock_transporter.publish_batch_desired_state.assert_called_once_with(expected_grouped)
        
        # Verify all pending updates are tracked
        for zone, updates in zone_updates:
            self.assertIn(zone.id, self.state_manager._pending_updates)
            self.assertEqual(self.state_manager._pending_updates[zone.id], updates)
        
        # Verify future is returned
        self.assertEqual(result, mock_future)

    def test_pending_updates_management(self):
        """Test pending updates tracking and management."""
        # Initially empty
        self.assertEqual(self.state_manager.get_pending_updates(), {})
        self.assertFalse(self.state_manager.is_zone_update_pending(self.temp_zone))
        
        # Add pending update
        mock_future = Mock(spec=Future)
        self.mock_transporter.publish_desired_state.return_value = mock_future
        
        self.state_manager.update_zone_desired_state(self.temp_zone, {"set_point": 25.0})
        
        # Verify pending state
        self.assertTrue(self.state_manager.is_zone_update_pending(self.temp_zone))
        pending = self.state_manager.get_pending_updates()
        self.assertIn("temp_1", pending)
        self.assertEqual(pending["temp_1"], {"set_point": 25.0})

    def test_cancel_pending_updates(self):
        """Test canceling pending updates."""
        # Add some pending updates
        mock_future = Mock(spec=Future)
        self.mock_transporter.publish_desired_state.return_value = mock_future
        
        self.state_manager.update_zone_desired_state(self.temp_zone, {"set_point": 25.0})
        self.state_manager.update_zone_desired_state(self.flow_zone, {"speed": 80.0})
        
        # Cancel specific zone
        self.state_manager.cancel_pending_updates(["temp_1"])
        self.assertFalse(self.state_manager.is_zone_update_pending(self.temp_zone))
        self.assertTrue(self.state_manager.is_zone_update_pending(self.flow_zone))
        
        # Cancel all
        self.state_manager.cancel_pending_updates()
        self.assertFalse(self.state_manager.is_zone_update_pending(self.flow_zone))

    def test_update_callbacks(self):
        """Test update callback management."""
        callback1 = Mock()
        callback2 = Mock()
        
        # Add callbacks
        self.state_manager.add_update_callback(callback1)
        self.state_manager.add_update_callback(callback2)
        
        # Verify callbacks are added (but not called twice)
        self.state_manager.add_update_callback(callback1)  # Should not add duplicate
        
        # Test notification (internal method)
        self.state_manager._notify_update_callbacks(True, "Test message", None)
        
        callback1.assert_called_once_with(True, "Test message", None)
        callback2.assert_called_once_with(True, "Test message", None)

    def test_callback_error_handling(self):
        """Test that callback errors don't break the state manager."""
        error_callback = Mock(side_effect=Exception("Callback error"))
        good_callback = Mock()
        
        self.state_manager.add_update_callback(error_callback)
        self.state_manager.add_update_callback(good_callback)
        
        # Should not raise exception even if callback fails
        self.state_manager._notify_update_callbacks(True, "Test", None)
        
        # Good callback should still be called
        good_callback.assert_called_once_with(True, "Test", None)


if __name__ == '__main__':
    unittest.main()