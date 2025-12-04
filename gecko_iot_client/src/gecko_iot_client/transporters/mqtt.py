"""
Enhanced AWS IoT MQTT5 transporter with WebSocket expiration management.

This module provides a robust MQTT transport layer that connects to AWS IoT Core
using WebSocket connections with JWT token expiration handling and automatic reconnection.
"""

import base64
import json
import logging
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import Future
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from awscrt import mqtt5
from awsiot import mqtt5_client_builder

from . import AbstractTransporter
from .exceptions import ConfigurationError, ConnectionError

logger = logging.getLogger(__name__)

# Constants
NOT_CONNECTED_ERROR = "Not connected"
DEFAULT_TOKEN_REFRESH_BUFFER = 300  # 5 minutes before expiry
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0
SUBSCRIPTION_TIMEOUT = 5.0
CONNECTION_TIMEOUT = 10
PUBLISH_TIMEOUT = 5.0
SUBSCRIPTION_SETTLE_DELAY = 2.0


# Type aliases for clarity
StateCallback = Callable[[Dict[str, Any]], None]
TopicHandler = Callable[[str, str], None]


# Utility functions for error handling and callback notification
def _parse_json_safely(payload: str) -> Optional[Dict[str, Any]]:
    """Safely parse JSON payload, returning None on error."""
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return None


def _complete_future_safely(
    future: Optional[Future], result: Any = None, error: Optional[Exception] = None
) -> None:
    """Complete a future with result or exception if not already done."""
    if future and not future.done():
        if error:
            future.set_exception(error)
        else:
            future.set_result(result)


def _notify_callbacks_safely(callbacks: list, data: Any) -> None:
    """Notify all callbacks, catching and logging individual errors."""
    for callback in callbacks:
        try:
            callback(data)
        except Exception as e:
            logger.error(f"Error in callback: {e}")


class _TokenManager:
    """Manages JWT token parsing, expiry tracking, and refresh timing."""

    def __init__(self, broker_url: str, refresh_buffer_seconds: int):
        self._broker_url = broker_url
        self._refresh_buffer = refresh_buffer_seconds
        self._current_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._parse_token()

    def _parse_token(self) -> None:
        """Parse JWT token from broker URL to extract expiry."""
        try:
            parsed_url = urllib.parse.urlparse(self._broker_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            token = query_params.get("token", [None])[0]

            if not token:
                return

            # Decode JWT payload (second part of token)
            parts = token.split(".")
            if len(parts) < 2:
                logger.warning("Invalid JWT token format")
                return

            # Decode payload with padding
            payload_part = parts[1]
            payload_part += "=" * (4 - len(payload_part) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_part)
            payload_json = json.loads(payload_bytes)

            exp_timestamp = payload_json.get("exp")
            if exp_timestamp:
                self._token_expiry = datetime.fromtimestamp(exp_timestamp)
                self._current_token = token
                logger.info(f"Token expires at: {self._token_expiry}")
            else:
                logger.warning("JWT token does not contain expiry claim")

        except Exception as e:
            logger.warning(f"Failed to parse token expiry: {e}")

    def update_broker_url(self, new_broker_url: str) -> None:
        """Update broker URL and re-parse token."""
        self._broker_url = new_broker_url
        self._parse_token()

    def is_expired(self) -> bool:
        """Check if token is currently expired."""
        if not self._token_expiry:
            return False
        return datetime.now() >= self._token_expiry

    def should_refresh(self, is_connected: bool) -> bool:
        """Check if token should be refreshed based on expiry buffer."""
        if not self._token_expiry or not is_connected:
            return False
        time_to_expiry = self._token_expiry - datetime.now()
        return time_to_expiry.total_seconds() <= self._refresh_buffer

    def force_expiry(self) -> None:
        """Force token to be expired (for handling authorization failures)."""
        self._token_expiry = datetime.now()

    @property
    def expiry(self) -> Optional[datetime]:
        """Get token expiry datetime."""
        return self._token_expiry


class _ReconnectionHandler:
    """Manages reconnection attempts with exponential backoff."""

    def __init__(
        self,
        max_attempts: int = MAX_RECONNECT_ATTEMPTS,
        base_delay: float = RECONNECT_BASE_DELAY,
        max_delay: float = RECONNECT_MAX_DELAY,
    ):
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._attempts = 0

    def should_attempt(self) -> bool:
        """Check if another reconnection attempt should be made."""
        return self._attempts < self._max_attempts

    def get_delay(self) -> float:
        """Calculate delay for next reconnection attempt with exponential backoff."""
        return min(self._base_delay * (2**self._attempts), self._max_delay)

    def on_attempt(self) -> int:
        """Record a reconnection attempt and return attempt number."""
        self._attempts += 1
        return self._attempts

    def on_success(self) -> None:
        """Reset attempt counter after successful connection."""
        self._attempts = 0

    @property
    def attempts(self) -> int:
        """Get current number of attempts."""
        return self._attempts


class _CallbackRegistry:
    """Thread-safe registry for managing callbacks by category."""

    def __init__(self):
        self._callbacks: Dict[str, list] = {}
        self._lock = threading.RLock()

    def register(self, category: str, callback: Callable) -> None:
        """Register a callback for a specific category."""
        with self._lock:
            if category not in self._callbacks:
                self._callbacks[category] = []
            if callback not in self._callbacks[category]:
                self._callbacks[category].append(callback)

    def get_callbacks(self, category: str) -> list:
        """Get all callbacks for a category (returns copy for thread safety)."""
        with self._lock:
            return self._callbacks.get(category, []).copy()

    def notify(self, category: str, data: Any) -> None:
        """Notify all callbacks in a category with data."""
        with self._lock:
            callbacks = self._callbacks.get(category, []).copy()
        _notify_callbacks_safely(callbacks, data)

    def clear(self, category: Optional[str] = None) -> None:
        """Clear callbacks for a category or all categories."""
        with self._lock:
            if category:
                self._callbacks.pop(category, None)
            else:
                self._callbacks.clear()


class MqttTransporter(AbstractTransporter):
    """Enhanced AWS IoT MQTT5 WebSocket transporter with expiration management."""

    def __init__(
        self,
        broker_url: str,
        monitor_id: str,
        token_refresh_callback: Optional[Callable[[str], str]] = None,
        token_refresh_buffer_seconds: int = DEFAULT_TOKEN_REFRESH_BUFFER,
    ):
        """
        Initialize MQTT transporter with expiration management.

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
        self._token_manager = _TokenManager(broker_url, token_refresh_buffer_seconds)
        self._reconnection_handler = _ReconnectionHandler()
        self._callback_registry = _CallbackRegistry()

        # Connection state
        self._client: Optional[mqtt5.Client] = None
        self._connected = False
        self._is_refreshing_token = False
        self._state_lock = threading.RLock()

        # Topic handlers (direct mapping, not in callback registry)
        self._topic_handlers: Dict[str, TopicHandler] = {}

        # Loading state
        self._config_future: Optional[Future] = None
        self._state_future: Optional[Future] = None
        self._subscriptions_setup = False

        # Threading for expiry monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop_event = threading.Event()

    def connect(self, **kwargs):
        """Connect using preformatted WebSocket URL with expiration management."""
        self._monitor_stop_event.clear()
        
        with self._state_lock:
            if self._connected:
                logger.info("Already connected")
                return

        # Check if token is already expired before attempting connection
        if self._token_manager.is_expired():
            logger.warning("Token expired, refreshing before connection")
            if self._token_refresh_callback:
                self._refresh_token_before_connect()

        try:
            self._do_connect(**kwargs)

            # Start expiry monitoring after successful connection
            if self._token_refresh_callback and self._token_manager.expiry:
                self._start_expiry_monitoring()

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Connection failed: {e}")
    
    def _refresh_token_before_connect(self) -> None:
        """Refresh token before initial connection attempt."""
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

    def _do_connect(self, **kwargs):
        """Internal connection logic."""
        try:
            # Generate a new unique client ID for each connection attempt
            # This prevents "Duplicate ClientId" errors when reconnecting
            client_id = f"ha-{self._monitor_id}-{uuid.uuid4().hex}"
            
            # Parse WebSocket URL for custom authorizer
            endpoint, auth_params = self._parse_websocket_url(self._broker_url)

            # Build client with extracted parameters
            self._client = mqtt5_client_builder.direct_with_custom_authorizer(
                endpoint=endpoint,
                auth_authorizer_name=auth_params["authorizer"],
                auth_username="",
                auth_password=b"",
                auth_token_key_name="token",
                auth_token_value=auth_params["token"],
                auth_authorizer_signature=auth_params["signature"],
                client_id=client_id,
                clean_start=kwargs.get("clean_start", True),
                keep_alive_secs=kwargs.get("keep_alive_secs", 30),
                on_lifecycle_connection_success=self._on_connection_success,
                on_lifecycle_connection_failure=self._on_connection_failure,
                on_lifecycle_disconnection=self._on_disconnection,
                on_publish_received=self._on_message,
            )

            logger.info(
                f"Connecting to AWS IoT at {endpoint} with client ID: {client_id}"
            )
            self._client.start()

            # Wait for connection
            if not self._wait_for_connection(timeout=10):
                raise ConnectionError("Connection timeout")

            self._connected = True
            self._reconnect_attempts = 0  # Reset on successful connection
            logger.info("Successfully connected to AWS IoT")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connected = False
            if self._client:
                try:
                    self._client.stop()
                except Exception:
                    pass
                self._client = None
            raise

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
                if self._should_refresh_token():
                    logger.info("Token approaching expiry, initiating refresh...")
                    self._handle_token_refresh()

                # Check every 30 seconds
                self._monitor_stop_event.wait(30)

            except Exception as e:
                logger.error(f"Error in expiry monitoring: {e}")
                self._monitor_stop_event.wait(60)  # Back off on error

    def _should_refresh_token(self) -> bool:
        """Check if token needs refreshing."""
        return self._token_manager.should_refresh(self._connected)

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

            # Stop the old client without triggering full disconnect logic
            if self._client:
                try:
                    logger.info("Stopping old MQTT client...")
                    self._client.stop()
                    self._client = None
                    with self._state_lock:
                        self._connected = False
                except Exception as e:
                    logger.warning(f"Error stopping old client: {e}")

            # Update broker URL and token expiry
            self._broker_url = new_broker_url
            self._token_manager.update_broker_url(new_broker_url)

            # Attempt to reconnect after token refresh
            try:
                self._do_connect()
                logger.info("Successfully refreshed token and reconnected")
                self._reconnection_handler.on_success()
            except Exception as e:
                logger.error(f"Reconnection after token refresh failed: {e}")
                self._schedule_reconnect()

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            self._schedule_reconnect()
        finally:
            with self._state_lock:
                self._is_refreshing_token = False

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
                    self._do_connect()
                    logger.info("Reconnection successful")
                    self._reconnection_handler.on_success()
                except Exception as e:
                    logger.error(f"Reconnection attempt {attempt_num} failed: {e}")
                    self._schedule_reconnect()

        reconnect_thread = threading.Thread(target=delayed_reconnect, daemon=True)
        reconnect_thread.start()

    def disconnect(self):
        """Disconnect and cleanup."""
        self._monitor_stop_event.set()
        self._stop_expiry_monitoring()

        with self._state_lock:
            if not self._connected or not self._client:
                return
            client = self._client

        try:
            logger.info("Disconnecting from AWS IoT...")
            client.stop()

            # Wait for disconnection
            start_time = time.time()
            while self._connected and (time.time() - start_time) < 5:
                time.sleep(0.1)

            with self._state_lock:
                self._connected = False
                self._client = None
                self._topic_handlers.clear()
                self._subscriptions_setup = False

            logger.info("Disconnected successfully")

        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            with self._state_lock:
                self._connected = False
                self._client = None

    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected

    def _topic(self, path: str) -> str:
        """Build AWS IoT topic for this monitor."""
        return f"$aws/things/{self._monitor_id}/{path}"

    # AbstractTransporter interface implementation

    def load_configuration(self, timeout: float = 30.0):
        """Load configuration from AWS IoT."""
        if not self._connected:
            raise ConnectionError(NOT_CONNECTED_ERROR)

        # Setup subscriptions if not already done
        if not self._subscriptions_setup:
            logger.info("Setting up subscriptions before loading configuration")
            self._setup_subscriptions_sync()

        if self._config_future and not self._config_future.done():
            logger.info("Configuration request already in progress")
            return

        logger.info(f"Loading configuration for monitor_id: {self._monitor_id}")

        self._config_future = Future()
        topic = self._topic("config/get")

        try:
            logger.info(f"📤 Publishing configuration request to: {topic}")
            publish_future = self._publish(topic, "{}")

            # Check if publish was successful (wait briefly)
            try:
                publish_future.result(timeout=5.0)
                logger.info(
                    f"✅ Configuration request successfully published to {topic}"
                )
            except Exception as e:
                logger.error(f"Failed to publish configuration request: {e}")
                raise ConfigurationError(f"Failed to publish config request: {e}")

            logger.info(
                f"⏰ Waiting for configuration response (timeout: {timeout} seconds)..."
            )

            # Wait for response with timeout
            result = self._config_future.result(timeout=timeout)
            logger.info("Configuration loaded successfully")
            return result

        except Exception as e:
            self._config_future = None
            logger.error(f"Configuration loading failed: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")

    def load_state(self):
        """Load state from AWS IoT shadow."""
        if not self._connected:
            raise ConnectionError(NOT_CONNECTED_ERROR)

        # Setup subscriptions if not already done
        if not self._subscriptions_setup:
            self._setup_subscriptions_sync()

        if self._state_future and not self._state_future.done():
            logger.info("State request already in progress")
            return

        logger.info(f"Loading state for monitor_id: {self._monitor_id}")

        self._state_future = Future()
        topic = self._topic("shadow/name/state/get")

        try:
            self._publish(topic, "{}")
            logger.info(f"State request sent to {topic}")

        except Exception as e:
            self._state_future = None
            logger.error(f"State loading failed: {e}")
            raise ConfigurationError(f"State loading failed: {e}")

    def publish_desired_state(self, desired_state: Dict[str, Any]) -> Future:
        """
        Publish desired state update to AWS IoT shadow.

        This is a low-level transport method that publishes the provided desired state
        structure directly without any business logic. Higher-level components should
        build the appropriate state structure before calling this method.

        Args:
            desired_state: The complete desired state structure to publish

        Returns:
            Future: Publication future
        """
        if not self._connected:
            raise ConnectionError(NOT_CONNECTED_ERROR)

        payload = {"state": {"desired": desired_state}}
        topic = self._topic("shadow/name/state/update")
        return self._publish(topic, json.dumps(payload))

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
        _notify_callbacks_safely(
            self._callback_registry.get_callbacks("state_update"), 
            new_state
        )

    def _notify_connectivity_change(self, mqtt_connected: bool):
        """Notify all connectivity callbacks of MQTT connection status change."""
        _notify_callbacks_safely(
            self._callback_registry.get_callbacks("connectivity"),
            mqtt_connected
        )

    # Internal implementation methods

    def _parse_websocket_url(self, url: str) -> tuple:
        """Parse WebSocket URL to extract connection parameters."""
        try:
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)

            # Extract the endpoint (remove wss:// prefix and /mqtt path)
            endpoint = parsed_url.netloc

            # Extract custom authorizer parameters
            auth_name = query_params.get("x-amz-customauthorizer-name", [None])[0]
            token = query_params.get("token", [None])[0]
            signature = query_params.get("x-amz-customauthorizer-signature", [None])[0]

            if not auth_name or not token or not signature:
                raise ConfigurationError(
                    "Missing required custom authorizer parameters in URL"
                )

            # URL decode the signature
            signature = urllib.parse.unquote(signature)

            auth_params = {
                "authorizer": auth_name,
                "token": token,
                "signature": signature,
            }

            logger.info(f"Parsed endpoint: {endpoint}, authorizer: {auth_name}")
            return endpoint, auth_params

        except Exception as e:
            raise ConfigurationError(f"Failed to parse WebSocket URL: {e}")

    def _wait_for_connection(self, timeout: int = 10) -> bool:
        """Wait for connection establishment."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._connected:
                return True
            time.sleep(0.1)

        return False

    def _setup_subscriptions_sync(self):
        """Setup essential AWS IoT subscriptions synchronously."""
        if self._subscriptions_setup:
            logger.info("Subscriptions already set up")
            return

        logger.info(f"Setting up subscriptions for monitor_id: {self._monitor_id}")

        topics = [
            (
                self._topic("config/get/accepted"),
                self._on_config_response,
            ),
            (
                self._topic("config/get/rejected"),
                self._on_config_rejected,
            ),
            (
                self._topic("shadow/name/state/get/accepted"),
                self._on_state_response,
            ),
            (
                self._topic("shadow/name/state/get/rejected"),
                self._on_state_rejected,
            ),
            (
                self._topic("shadow/name/state/update/documents"),
                self._on_state_document_update,
            ),
            (
                self._topic("shadow/name/state/update/rejected"),
                self._on_state_update_rejected,
            ),
        ]

        successful_subscriptions = 0
        for topic, handler in topics:
            try:
                logger.info(f"🎯 Subscribing to: {topic}")
                self._subscribe_sync(topic, handler)
                successful_subscriptions += 1
                logger.info(f"Successfully subscribed to {topic}")
            except Exception as e:
                logger.error(f"Failed to subscribe to {topic}: {e}")

        if successful_subscriptions > 0:
            self._subscriptions_setup = True
            logger.info(
                f"✅ Set up {successful_subscriptions}/{len(topics)} subscriptions"
            )
            # Give AWS IoT time to fully process and establish subscriptions
            # This prevents timing issues where config requests are sent before
            # subscriptions are fully active on the AWS side
            logger.info("⏳ Waiting for AWS IoT to fully establish subscriptions...")
            time.sleep(2.0)  # Simple 2-second delay to ensure routing is ready
            logger.info("Subscriptions should now be fully established")
        else:
            logger.error("Failed to set up any subscriptions")
            raise ConnectionError("Failed to establish subscriptions")

    def _subscribe_sync(self, topic: str, handler: Callable):
        """Internal synchronous subscription method."""
        if not self._client:
            raise ConnectionError("Client not available")

        self._topic_handlers[topic] = handler

        packet = mqtt5.SubscribePacket(
            subscriptions=[
                mqtt5.Subscription(topic_filter=topic, qos=mqtt5.QoS.AT_LEAST_ONCE)
            ]
        )

        # Use synchronous subscription (this will block until complete)
        future = self._client.subscribe(packet)
        # Wait for completion with timeout
        try:
            future.result(timeout=5.0)
        except Exception as e:
            logger.error(f"Subscription failed for {topic}: {e}")
            raise

    def _publish(self, topic: str, payload: str) -> Future:
        """Internal publish method."""
        if not self._client:
            raise ConnectionError("Client not initialized")

        packet = mqtt5.PublishPacket(
            topic=topic, payload=payload.encode("utf-8"), qos=mqtt5.QoS.AT_LEAST_ONCE
        )

        return self._client.publish(packet)

    # Message handlers

    def _on_message(self, publish_data):
        """Route incoming messages to handlers."""
        try:
            topic = publish_data.publish_packet.topic
            payload = (
                publish_data.publish_packet.payload.decode("utf-8")
                if publish_data.publish_packet.payload
                else ""
            )

            logger.info(f"Received message on topic '{topic}': {payload[:100]}...")

            handler = self._topic_handlers.get(topic)
            if handler:
                try:
                    logger.info(f"🎯 Routing message to handler for topic: {topic}")
                    handler(topic, payload)
                except Exception as e:
                    logger.error(f"Handler error for {topic}: {e}")
            else:
                logger.warning(f"⚠️  No handler registered for topic '{topic}'")
                logger.info(
                    f"🗂️  Available handlers: {list(self._topic_handlers.keys())}"
                )

        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    def _on_config_response(self, topic: str, payload: str):
        """Handle configuration response."""
        logger.info(f"Configuration response received on topic: {topic}")
        logger.info(
            f"Payload: {payload[:200]}..."
            if len(payload) > 200
            else f"Payload: {payload}"
        )

        config = _parse_json_safely(payload)
        if config:
            config = config.get("configuration", {}).get("configuration", {})
            _notify_callbacks_safely(
                self._callback_registry.get_callbacks("config"),
                config
            )
            _complete_future_safely(self._config_future, config)
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
        state = _parse_json_safely(payload)
        
        if state:
            _notify_callbacks_safely(
                self._callback_registry.get_callbacks("state"),
                state
            )
            _complete_future_safely(self._state_future, state)
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
        """Handle state document update notifications from update/documents topic."""
        logger.info("State document update received from /shadow/name/state/update/documents")
        document = _parse_json_safely(payload)
        
        if document:
            # Extract the current state from the document structure
            current_state = document.get("current", {}).get("state", {})
            logger.info(f"Extracted state from document: {current_state}")
            
            _notify_callbacks_safely(
                self._callback_registry.get_callbacks("state_update"),
                {"state": current_state}
            )
        else:
            logger.error("Failed to parse state document update")

    def _on_state_update_rejected(self, topic: str, payload: str):
        """Handle state update rejection."""
        logger.warning(f"State update rejected: {payload}")

    # Lifecycle callbacks

    def _on_connection_success(self, connack_packet: mqtt5.LifecycleConnectSuccessData):
        """Handle successful connection."""
        logger.info(f"Connection successful: {connack_packet}")
        with self._state_lock:
            self._connected = True
        self._reconnection_handler.on_success()
        self._notify_connectivity_change(True)

    def _on_connection_failure(self, connack_packet: mqtt5.LifecycleConnectFailureData):
        """Handle connection failure."""
        logger.error(f"Connection failed: {connack_packet}")
        with self._state_lock:
            self._connected = False
        self._notify_connectivity_change(False)

        # Check if this is an authorization failure (likely expired token)
        if connack_packet.connack_packet and connack_packet.connack_packet.reason_code == mqtt5.ConnectReasonCode.NOT_AUTHORIZED:
            logger.warning("Connection failed due to authorization - token may be expired")
            # If we have a refresh callback, attempt token refresh
            if self._token_refresh_callback and not self._monitor_stop_event.is_set():
                logger.info("Triggering token refresh due to authorization failure...")
                # Mark token as expired to force immediate refresh
                self._token_manager.force_expiry()
                # Attempt token refresh and reconnection
                threading.Thread(target=self._handle_token_refresh, daemon=True).start()
                return

        # For other failures, schedule normal reconnect if we have a refresh callback
        if self._token_refresh_callback and not self._monitor_stop_event.is_set():
            logger.info("Connection failed, scheduling reconnection...")
            self._schedule_reconnect()

    def _on_disconnection(self, disconnect_packet: mqtt5.LifecycleDisconnectData):
        """Handle disconnection."""
        logger.info(f"Disconnected: {disconnect_packet}")
        self._connected = False
        self._notify_connectivity_change(False)

        # Don't schedule reconnect if we're in the middle of a token refresh
        # or if we've been asked to stop
        if self._is_refreshing_token:
            logger.info("Disconnection during token refresh - ignoring")
            return
            
        # If we have a token refresh callback, attempt to reconnect
        if self._token_refresh_callback and not self._monitor_stop_event.is_set():
            logger.info("Unexpected disconnection, attempting to reconnect...")
            self._schedule_reconnect()
