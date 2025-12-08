"""
Gecko-specific MQTT transporter implementation.

This module provides the MqttTransporter class which implements the AbstractTransporter
interface with Gecko IoT-specific logic for configuration loading, state management,
and AWS IoT shadow operations.
"""

import json
import logging
import threading
import time
import uuid
from concurrent.futures import Future
from typing import Any, Callable, Dict, Optional

from .. import AbstractTransporter
from ..exceptions import ConfigurationError, ConnectionError
from .client import MqttClient
from .token_manager import TokenManager
from .reconnection_handler import ReconnectionHandler
from .callback_registry import CallbackRegistry
from .utils import parse_json_safely, complete_future_safely, notify_callbacks_safely
from .constants import (
    NOT_CONNECTED_ERROR,
    CONNECTION_TIMEOUT,
    SUBSCRIPTION_SETTLE_DELAY,
)

logger = logging.getLogger(__name__)


class MqttTransporter(AbstractTransporter):
    """
    Gecko-specific MQTT transporter.
    
    Responsibilities:
    - Gecko topic structure (config, state, shadow)
    - Token refresh and expiration management
    - Configuration and state loading
    - AbstractTransporter interface implementation
    - Reconnection logic with token refresh
    
    This class contains all Gecko IoT business logic and delegates
    MQTT protocol operations to MqttClient.
    """

    def __init__(
        self,
        broker_url: str,
        monitor_id: str,
        token_refresh_callback: Optional[Callable[[str], str]] = None,
        token_refresh_buffer_seconds: int = 300,
    ):
        """
        Initialize MQTT transporter with Gecko-specific logic.

        Args:
            broker_url: WebSocket URL with embedded JWT token
            monitor_id: Device monitor identifier
            token_refresh_callback: Function to get new broker URL with fresh token
            token_refresh_buffer_seconds: Seconds before expiry to refresh token
        """
        if not broker_url or not monitor_id:
            raise ConfigurationError("Both broker_url and monitor_id are required")

        self._broker_url = broker_url
        self._monitor_id = monitor_id
        self._token_refresh_callback = token_refresh_callback

        # Helper components
        self._token_manager = TokenManager(broker_url, token_refresh_buffer_seconds)
        self._reconnection_handler = ReconnectionHandler()
        self._callback_registry = CallbackRegistry()

        # MQTT client - delegates all MQTT operations
        self._mqtt_client = MqttClient(
            on_connected=self._on_mqtt_connected,
            on_message=None,  # We use specific handlers only
        )

        # State management
        self._is_refreshing_token = False
        self._state_lock = threading.RLock()

        # Loading state
        self._config_future: Optional[Future] = None
        self._state_future: Optional[Future] = None
        self._subscriptions_setup = False

        # Threading for expiry monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop_event = threading.Event()

    # ========================================================================
    # AbstractTransporter Interface
    # ========================================================================

    def connect(self, **kwargs):
        """Connect using preformatted WebSocket URL with expiration management."""
        self._monitor_stop_event.clear()
        
        if self._mqtt_client.is_connected():
            logger.info("Already connected")
            return

        # Check if token is already expired before attempting connection
        if self._token_manager.is_expired():
            logger.warning("Token expired, refreshing before connection")
            if self._token_refresh_callback:
                self._refresh_token_before_connect()

        try:
            # Generate unique client ID
            client_id = f"ha-{self._monitor_id}-{uuid.uuid4().hex}"
            
            # Connect via MQTT client
            self._mqtt_client.connect(
                broker_url=self._broker_url,
                client_id=client_id,
                timeout=kwargs.get("timeout", CONNECTION_TIMEOUT)
            )

            # Start expiry monitoring after successful connection
            if self._token_refresh_callback and self._token_manager.expiry:
                self._start_expiry_monitoring()

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect and cleanup."""
        # Stop monitoring first
        self._monitor_stop_event.set()
        self._stop_expiry_monitoring()

        # Disconnect MQTT client
        self._mqtt_client.disconnect()
        
        # Clear subscription state
        with self._state_lock:
            self._subscriptions_setup = False

        logger.info("Transporter disconnected successfully")

    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._mqtt_client.is_connected()

    def update_broker_url(self, new_broker_url: str) -> None:
        """
        Update broker URL with a fresh token.
        
        This is useful when reusing an existing connection that needs a token refresh.
        The method updates the broker URL and token manager without disconnecting.
        
        Args:
            new_broker_url: New WebSocket URL with fresh JWT token
        """
        if not new_broker_url:
            logger.warning("Attempted to update with empty broker URL")
            return
            
        logger.info("Updating broker URL with fresh token")
        self._broker_url = new_broker_url
        self._token_manager.update_broker_url(new_broker_url)
        logger.info(f"Token expiry updated to: {self._token_manager.expiry}")

    def load_configuration(self, timeout: float = 30.0):
        """Load configuration from AWS IoT."""
        if not self._mqtt_client.is_connected():
            raise ConnectionError(NOT_CONNECTED_ERROR)

        # Setup subscriptions if not already done
        if not self._subscriptions_setup:
            logger.info("Setting up subscriptions before loading configuration")
            self._setup_subscriptions()

        if self._config_future and not self._config_future.done():
            logger.info("Configuration request already in progress")
            return

        logger.info(f"Loading configuration for monitor_id: {self._monitor_id}")

        self._config_future = Future()
        topic = self._build_topic("config/get")

        try:
            logger.info(f"📤 Publishing configuration request to: {topic}")
            publish_future = self._mqtt_client.publish(topic, "{}")

            # Wait for publish to complete
            try:
                publish_future.result(timeout=5.0)
                logger.info(f"✅ Configuration request successfully published to {topic}")
            except Exception as e:
                logger.error(f"Failed to publish configuration request: {e}")
                raise ConfigurationError(f"Failed to publish config request: {e}")

            logger.info(f"⏰ Waiting for configuration response (timeout: {timeout} seconds)...")

            # Wait for response
            result = self._config_future.result(timeout=timeout)
            logger.info("Configuration loaded successfully")
            return result

        except Exception as e:
            self._config_future = None
            logger.error(f"Configuration loading failed: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")

    def load_state(self):
        """Load state from AWS IoT shadow."""
        if not self._mqtt_client.is_connected():
            raise ConnectionError(NOT_CONNECTED_ERROR)

        # Setup subscriptions if not already done
        if not self._subscriptions_setup:
            self._setup_subscriptions()

        if self._state_future and not self._state_future.done():
            logger.info("State request already in progress")
            return

        logger.info(f"Loading state for monitor_id: {self._monitor_id}")

        self._state_future = Future()
        topic = self._build_topic("shadow/name/state/get")

        try:
            self._mqtt_client.publish(topic, "{}")
            logger.info(f"State request sent to {topic}")

        except Exception as e:
            self._state_future = None
            logger.error(f"State loading failed: {e}")
            raise ConfigurationError(f"State loading failed: {e}")

    def publish_desired_state(self, desired_state: Dict[str, Any]) -> Future:
        """Publish desired state update to AWS IoT shadow."""
        if not self._mqtt_client.is_connected():
            raise ConnectionError(NOT_CONNECTED_ERROR)

        payload = {"state": {"desired": desired_state}}
        topic = self._build_topic("shadow/name/state/update")
        return self._mqtt_client.publish(topic, json.dumps(payload))

    def publish_batch_desired_state(
        self, zone_updates: Dict[str, Dict[str, Dict[str, Any]]]
    ) -> Future:
        """Publish batch desired state updates for multiple zones."""
        desired_state = {"zones": zone_updates}
        return self.publish_desired_state(desired_state)

    def on_configuration_loaded(self, callback):
        """Register config callback."""
        self._callback_registry.register("config", callback)

    def on_state_loaded(self, callback):
        """Register state callback."""
        self._callback_registry.register("state", callback)

    def on_state_change(self, callback):
        """Register state change callback."""
        self._callback_registry.register("state_update", callback)

    def on_connectivity_change(self, callback):
        """Register connectivity change callback."""
        self._callback_registry.register("connectivity", callback)

    def change_state(self, new_state):
        """Change state (placeholder for interface compliance)."""
        notify_callbacks_safely(
            self._callback_registry.get_callbacks("state_update"), 
            new_state
        )

    # ========================================================================
    # Gecko-Specific Logic
    # ========================================================================

    def _build_topic(self, path: str) -> str:
        """Build AWS IoT topic for this monitor."""
        return f"$aws/things/{self._monitor_id}/{path}"

    def _refresh_token_before_connect(self) -> None:
        """Refresh token before initial connection attempt."""
        if not self._token_refresh_callback:
            return
            
        try:
            new_broker_url = self._token_refresh_callback(self._monitor_id)
            if new_broker_url:
                self._broker_url = new_broker_url
                self._token_manager.update_broker_url(new_broker_url)
                logger.info("Token refreshed successfully before connection")
            else:
                logger.error("Token refresh callback returned empty URL")
        except Exception as e:
            logger.error(f"Failed to refresh expired token before connection: {e}")

    def _setup_subscriptions(self):
        """Setup essential AWS IoT subscriptions."""
        if self._subscriptions_setup:
            logger.info("Subscriptions already set up")
            return

        logger.info(f"Setting up subscriptions for monitor_id: {self._monitor_id}")

        topics = [
            (self._build_topic("config/get/accepted"), self._on_config_response),
            (self._build_topic("config/get/rejected"), self._on_config_rejected),
            (self._build_topic("shadow/name/state/get/accepted"), self._on_state_response),
            (self._build_topic("shadow/name/state/get/rejected"), self._on_state_rejected),
            (self._build_topic("shadow/name/state/update/documents"), self._on_state_document_update),
            (self._build_topic("shadow/name/state/update/rejected"), self._on_state_update_rejected),
        ]

        successful_subscriptions = 0
        for topic, handler in topics:
            try:
                logger.info(f"🎯 Subscribing to: {topic}")
                self._mqtt_client.subscribe(topic, handler)
                successful_subscriptions += 1
                logger.info(f"Successfully subscribed to {topic}")
            except Exception as e:
                logger.error(f"Failed to subscribe to {topic}: {e}")

        if successful_subscriptions > 0:
            self._subscriptions_setup = True
            logger.info(f"✅ Set up {successful_subscriptions}/{len(topics)} subscriptions")
            
            # Give AWS IoT time to process subscriptions
            logger.info("⏳ Waiting for AWS IoT to fully establish subscriptions...")
            time.sleep(SUBSCRIPTION_SETTLE_DELAY)
            logger.info("Subscriptions should now be fully established")
        else:
            logger.error("Failed to set up any subscriptions")
            raise ConnectionError("Failed to establish subscriptions")

    # ========================================================================
    # Token Refresh and Expiry Monitoring
    # ========================================================================

    def _start_expiry_monitoring(self):
        """Start monitoring token expiry in background thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._monitor_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._expiry_monitor_loop, daemon=True
        )
        self._monitor_thread.start()
        logger.info("Started token expiry monitoring")

    def _stop_expiry_monitoring(self):
        """Stop token expiry monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_stop_event.set()
            self._monitor_thread.join(timeout=5)
            logger.info("Stopped token expiry monitoring")

    def _expiry_monitor_loop(self):
        """Background thread loop to monitor token expiry."""
        while not self._monitor_stop_event.is_set():
            try:
                # Check if token needs refreshing
                with self._state_lock:
                    already_refreshing = self._is_refreshing_token
                
                if not already_refreshing and self._should_refresh_token():
                    logger.info("Token approaching expiry, initiating refresh...")
                    self._handle_token_refresh()

                # Check every 30 seconds
                self._monitor_stop_event.wait(30)

            except Exception as e:
                logger.error(f"Error in expiry monitoring: {e}")
                self._monitor_stop_event.wait(60)  # Back off on error

    def _should_refresh_token(self) -> bool:
        """Check if token needs refreshing."""
        return self._token_manager.should_refresh(self._mqtt_client.is_connected())

    def _handle_token_refresh(self):
        """Handle token refresh and reconnection."""
        if not self._token_refresh_callback:
            logger.warning("No token refresh callback configured")
            return

        with self._state_lock:
            self._is_refreshing_token = True
        
        try:
            logger.info("Refreshing token and reconnecting...")

            # Get new broker URL with fresh token
            new_broker_url = self._token_refresh_callback(self._monitor_id)
            if not new_broker_url:
                logger.error("Token refresh callback returned empty URL")
                with self._state_lock:
                    self._is_refreshing_token = False
                self._schedule_reconnect()
                return

            # Stop the old client
            logger.info("Stopping old MQTT client for token refresh...")
            self._mqtt_client.stop_for_refresh()

            # Update broker URL and token expiry
            self._broker_url = new_broker_url
            self._token_manager.update_broker_url(new_broker_url)

            # Clear subscription state since we're reconnecting
            with self._state_lock:
                self._subscriptions_setup = False

            # Attempt to reconnect
            try:
                client_id = f"ha-{self._monitor_id}-{uuid.uuid4().hex}"
                self._mqtt_client.connect(
                    broker_url=self._broker_url,
                    client_id=client_id
                )
                
                # Clear intentional disconnect flag after successful reconnection
                self._mqtt_client.clear_intentional_disconnect_flag()
                
                logger.info("Successfully refreshed token and reconnected")
                self._reconnection_handler.on_success()
                
                with self._state_lock:
                    self._is_refreshing_token = False
                    
            except Exception as e:
                logger.error(f"Reconnection after token refresh failed: {e}")
                with self._state_lock:
                    self._is_refreshing_token = False
                self._schedule_reconnect()

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            with self._state_lock:
                self._is_refreshing_token = False
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule reconnection with exponential backoff."""
        if not self._reconnection_handler.should_attempt():
            logger.error("Max reconnection attempts reached, giving up")
            return

        delay = self._reconnection_handler.get_delay()
        attempt_num = self._reconnection_handler.on_attempt()

        logger.info(f"Scheduling reconnection attempt {attempt_num} in {delay} seconds")

        def delayed_reconnect():
            time.sleep(delay)
            if not self._monitor_stop_event.is_set():
                try:
                    client_id = f"ha-{self._monitor_id}-{uuid.uuid4().hex}"
                    self._mqtt_client.connect(
                        broker_url=self._broker_url,
                        client_id=client_id
                    )
                    logger.info("Reconnection successful")
                    self._reconnection_handler.on_success()
                    
                    # Clear subscription state to force re-setup
                    with self._state_lock:
                        self._subscriptions_setup = False
                        
                except Exception as e:
                    logger.error(f"Reconnection attempt {attempt_num} failed: {e}")
                    self._schedule_reconnect()

        reconnect_thread = threading.Thread(target=delayed_reconnect, daemon=True)
        reconnect_thread.start()

    # ========================================================================
    # MQTT Client Callbacks
    # ========================================================================

    def _on_mqtt_connected(self, connected: bool):
        """Handle MQTT connection status changes."""
        logger.info(f"MQTT connection status changed: {connected}")
        
        if connected:
            # Reset reconnection handler on successful connection
            self._reconnection_handler.on_success()
            # Clear subscription state to force re-setup after reconnection
            with self._state_lock:
                self._subscriptions_setup = False
        else:
            # Check if we should attempt reconnection
            with self._state_lock:
                is_refreshing = self._is_refreshing_token
            
            # Only schedule reconnect if not already refreshing and we have a callback
            if not is_refreshing and self._token_refresh_callback and not self._monitor_stop_event.is_set():
                # Check if token is expired/expiring
                if self._token_manager.is_expired() or self._token_manager.should_refresh(False):
                    logger.info("Token expired/expiring, will refresh on reconnect")
                    self._token_manager.force_expiry()
                
                logger.info("Unexpected disconnection, scheduling reconnection...")
                self._schedule_reconnect()
        
        # Notify connectivity callbacks
        self._callback_registry.notify("connectivity", connected)

    # ========================================================================
    # Message Handlers for Gecko Topics
    # ========================================================================

    def _on_config_response(self, topic: str, payload: str):
        """Handle configuration response."""
        logger.info(f"Configuration response received on topic: {topic}")
        logger.info(
            f"Payload: {payload[:200]}..."
            if len(payload) > 200
            else f"Payload: {payload}"
        )

        config = parse_json_safely(payload)
        if config:
            config = config.get("configuration", {}).get("configuration", {})
            notify_callbacks_safely(
                self._callback_registry.get_callbacks("config"),
                config
            )
            complete_future_safely(self._config_future, config)
        else:
            logger.error("Failed to parse configuration response")
            if self._config_future and not self._config_future.done():
                self._config_future.set_exception(
                    ConfigurationError("Invalid JSON in configuration response")
                )

    def _on_config_rejected(self, topic: str, payload: str):
        """Handle configuration request rejection."""
        logger.warning(f"Configuration request rejected on topic: {topic}")
        logger.warning(f"Rejection payload: {payload}")
        if self._config_future and not self._config_future.done():
            self._config_future.set_exception(
                ConfigurationError(f"Configuration rejected: {payload}")
            )

    def _on_state_response(self, topic: str, payload: str):
        """Handle state response."""
        logger.info("State response received")
        state = parse_json_safely(payload)
        
        if state:
            notify_callbacks_safely(
                self._callback_registry.get_callbacks("state"),
                state
            )
            complete_future_safely(self._state_future, state)
        else:
            logger.error("Failed to parse state response")
            if self._state_future and not self._state_future.done():
                self._state_future.set_exception(
                    ConfigurationError("Invalid JSON in state response")
                )

    def _on_state_rejected(self, topic: str, payload: str):
        """Handle state request rejection."""
        logger.warning(f"State request rejected: {payload}")
        if self._state_future and not self._state_future.done():
            self._state_future.set_exception(
                ConfigurationError(f"State rejected: {payload}")
            )

    def _on_state_document_update(self, topic: str, payload: str):
        """Handle state document update notifications."""
        logger.info("State document update received from /shadow/name/state/update/documents")
        document = parse_json_safely(payload)
        
        if document:
            # Extract current state from document structure
            current_state = document.get("current", {}).get("state", {})
            logger.info(f"Extracted state from document: {current_state}")
            
            notify_callbacks_safely(
                self._callback_registry.get_callbacks("state_update"),
                {"state": current_state}
            )
        else:
            logger.error("Failed to parse state document update")

    def _on_state_update_rejected(self, topic: str, payload: str):
        """Handle state update rejection."""
        logger.warning(f"State update rejected: {payload}")
