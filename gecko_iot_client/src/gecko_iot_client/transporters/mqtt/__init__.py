"""
MQTT transporter package for Gecko IoT devices.

This package provides MQTT5 connectivity for AWS IoT Core with JWT token authentication,
automatic token refresh, and Gecko-specific shadow operations.

Main exports:
- MqttTransporter: High-level Gecko IoT transporter (primary interface)
- MqttClient: Low-level MQTT protocol client (for advanced use)
"""

from .transporter import MqttTransporter
from .client import MqttClient

__all__ = ["MqttTransporter", "MqttClient"]
