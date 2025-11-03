"""
Enhanced AWS IoT MQTT5 transporter with WebSocket expiration management.

This module provides a robust MQTT transport layer that connects to AWS IoT Core
using WebSocket connections with JWT token expiration handling and automatic reconnection.
"""

import json
import logging
import time
import urllib.parse
import threading
from concurrent.futures import Future
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
import base64

from awscrt import mqtt5
from awsiot import mqtt5_client_builder

from . import AbstractTransporter
from .exceptions import ConnectionError, ConfigurationError

logger = logging.getLogger(__name__)

# Constants
NOT_CONNECTED_ERROR = "Not connected"
DEFAULT_TOKEN_REFRESH_BUFFER = 300  # 5 minutes before expiry
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0


class MqttTransporter(AbstractTransporter):
    """Enhanced AWS IoT MQTT5 WebSocket transporter with expiration management."""
    
    def __init__(self, broker_url: str, monitor_id: str, 
                 token_refresh_callback: Optional[Callable[[], str]] = None,
                 token_refresh_buffer_seconds: int = DEFAULT_TOKEN_REFRESH_BUFFER):
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
        self._token_refresh_buffer = token_refresh_buffer_seconds
        
        # Connection state
        self._client: Optional[mqtt5.Client] = None
        self._connected = False
        self._client_id = f"gecko-{monitor_id}-{int(time.time())}"
        self._reconnect_attempts = 0
        
        # Token management
        self._current_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
        # Callback storage
        self._state_callbacks = []
        self._config_callbacks = []
        self._connectivity_callbacks = []
        self._topic_handlers: Dict[str, Callable] = {}
        
        # Loading state
        self._config_future: Optional[Future] = None
        self._state_future: Optional[Future] = None
        self._subscriptions_setup = False
        
        # Threading for expiry monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop_event = threading.Event()
        
        # Parse initial token expiry
        self._parse_token_expiry()
    
    def connect(self, **kwargs):
        """Connect using preformatted WebSocket URL with expiration management."""
        if self._connected:
            logger.info("Already connected")
            return
            
        try:
            self._do_connect(**kwargs)
            
            # Start expiry monitoring after successful connection
            if self._token_refresh_callback and self._token_expiry:
                self._start_expiry_monitoring()
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Connection failed: {e}")
    
    def _do_connect(self, **kwargs):
        """Internal connection logic."""
        try:
            # Parse WebSocket URL for custom authorizer
            endpoint, auth_params = self._parse_websocket_url(self._broker_url)
            
            # Build client with extracted parameters
            self._client = mqtt5_client_builder.direct_with_custom_authorizer(
                endpoint=endpoint,
                auth_authorizer_name=auth_params['authorizer'],
                auth_username="",
                auth_password=b"",
                auth_token_key_name="token",
                auth_token_value=auth_params['token'],
                auth_authorizer_signature=auth_params['signature'],
                client_id=self._client_id,
                clean_start=kwargs.get('clean_start', True),
                keep_alive_secs=kwargs.get('keep_alive_secs', 30),
                on_lifecycle_connection_success=self._on_connection_success,
                on_lifecycle_connection_failure=self._on_connection_failure,
                on_lifecycle_disconnection=self._on_disconnection,
                on_publish_received=self._on_message
            )
            
            logger.info(f"Connecting to AWS IoT at {endpoint} with client ID: {self._client_id}")
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
    
    def _parse_token_expiry(self):
        """Parse JWT token from broker URL to extract expiry."""
        try:
            parsed_url = urllib.parse.urlparse(self._broker_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            token = query_params.get('token', [None])[0]
            
            if token:
                # Decode JWT header and payload manually for expiry check
                try:
                    # Split JWT token into parts
                    parts = token.split('.')
                    if len(parts) >= 2:
                        # Decode payload (second part)
                        payload_part = parts[1]
                        # Add padding if needed
                        payload_part += '=' * (4 - len(payload_part) % 4)
                        payload_bytes = base64.urlsafe_b64decode(payload_part)
                        payload_json = json.loads(payload_bytes)
                        
                        exp_timestamp = payload_json.get('exp')
                        if exp_timestamp:
                            self._token_expiry = datetime.fromtimestamp(exp_timestamp)
                            self._current_token = token
                            logger.info(f"Token expires at: {self._token_expiry}")
                        else:
                            logger.warning("JWT token does not contain expiry claim")
                    else:
                        logger.warning("Invalid JWT token format")
                except Exception as e:
                    logger.warning(f"Failed to decode JWT token: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to parse token expiry: {e}")
    
    def _start_expiry_monitoring(self):
        """Start monitoring token expiry in background thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
            
        self._monitor_stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._expiry_monitor_loop, daemon=True)
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
        if not self._token_expiry or not self._connected:
            return False
            
        time_to_expiry = self._token_expiry - datetime.now()
        return time_to_expiry.total_seconds() <= self._token_refresh_buffer
    
    def _handle_token_refresh(self):
        """Handle token refresh and reconnection."""
        if not self._token_refresh_callback:
            logger.warning("No token refresh callback configured")
            return
            
        try:
            logger.info("Refreshing token and reconnecting...")
            
            # Get new broker URL with fresh token
            new_broker_url = self._token_refresh_callback()
            if not new_broker_url:
                logger.error("Token refresh callback returned empty URL")
                return
                
            # Disconnect current connection
            old_connected = self._connected
            self.disconnect()
            
            # Update broker URL and parse new token
            self._broker_url = new_broker_url
            self._parse_token_expiry()
            
            # Reconnect if we were previously connected
            if old_connected:
                self._do_connect()
                logger.info("Successfully refreshed token and reconnected")
                
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            # Attempt exponential backoff reconnection
            self._schedule_reconnect()
    
    def _schedule_reconnect(self):
        """Schedule reconnection with exponential backoff."""
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached, giving up")
            return
            
        delay = min(RECONNECT_BASE_DELAY * (2 ** self._reconnect_attempts), RECONNECT_MAX_DELAY)
        self._reconnect_attempts += 1
        
        logger.info(f"Scheduling reconnection attempt {self._reconnect_attempts} in {delay} seconds")
        
        def delayed_reconnect():
            time.sleep(delay)
            if not self._monitor_stop_event.is_set():
                try:
                    self._do_connect()
                    logger.info("Reconnection successful")
                except Exception as e:
                    logger.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")
                    self._schedule_reconnect()
        
        reconnect_thread = threading.Thread(target=delayed_reconnect, daemon=True)
        reconnect_thread.start()
    
    def disconnect(self):
        """Disconnect and cleanup."""
        # Stop expiry monitoring
        self._stop_expiry_monitoring()
        
        if not self._connected or not self._client:
            return
            
        try:
            logger.info("Disconnecting from AWS IoT...")
            self._client.stop()
            
            # Wait for disconnection
            start_time = time.time()
            while self._connected and (time.time() - start_time) < 5:
                time.sleep(0.1)
                
            self._connected = False
            self._client = None
            self._topic_handlers.clear()
            self._subscriptions_setup = False
                
            logger.info("Disconnected successfully")
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            self._connected = False
            self._client = None
    
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected
    
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
            
        logger.info(f"🔄 Loading configuration for monitor_id: {self._monitor_id}")
        
        self._config_future = Future()
        topic = f"$aws/things/{self._monitor_id}/config/get"
        
        try:
            logger.info(f"📤 Publishing configuration request to: {topic}")
            publish_future = self._publish(topic, "{}")
            
            # Check if publish was successful (wait briefly)
            try:
                publish_future.result(timeout=5.0)
                logger.info(f"✅ Configuration request successfully published to {topic}")
            except Exception as e:
                logger.error(f"❌ Failed to publish configuration request: {e}")
                raise ConfigurationError(f"Failed to publish config request: {e}")
            
            logger.info(f"⏰ Waiting for configuration response (timeout: {timeout} seconds)...")
            
            # Wait for response with timeout
            result = self._config_future.result(timeout=timeout)
            logger.info("✅ Configuration loaded successfully")
            return result
            
        except Exception as e:
            self._config_future = None
            logger.error(f"❌ Configuration loading failed: {e}")
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
        topic = f"$aws/things/{self._monitor_id}/shadow/name/state/get"
        
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
        topic = f"$aws/things/{self._monitor_id}/shadow/name/state/update"
        return self._publish(topic, json.dumps(payload))
    
    def publish_batch_desired_state(self, zone_updates: Dict[str, Dict[str, Dict[str, Any]]]) -> Future:
        """Publish batch desired state updates for multiple zones."""
        desired_state = {"zones": zone_updates}
        return self.publish_desired_state(desired_state)
    
    def _register_callback(self, callback_list: list, callback: Callable):
        """Generic callback registration helper."""
        if callback not in callback_list:
            callback_list.append(callback)
    
    def on_configuration_loaded(self, callback):
        """Register config callback."""
        self._register_callback(self._config_callbacks, callback)
    
    def on_state_loaded(self, callback):
        """Register state callback."""
        self._register_callback(self._state_callbacks, callback)
    
    def on_state_change(self, callback):
        """Register state change callback."""
        self._register_callback(self._state_callbacks, callback)
    
    def on_connectivity_change(self, callback):
        """Register connectivity change callback."""
        self._register_callback(self._connectivity_callbacks, callback)
    
    def change_state(self, new_state):
        """Change state (placeholder for interface compliance)."""
        # Notify state change callbacks
        for callback in self._state_callbacks:
            try:
                callback(new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def _notify_connectivity_change(self, mqtt_connected: bool):
        """Notify all connectivity callbacks of MQTT connection status change."""
        for callback in self._connectivity_callbacks:
            try:
                callback(mqtt_connected)
            except Exception as e:
                logger.error(f"Error in connectivity change callback: {e}")
    
    # Internal implementation methods
    
    def _parse_websocket_url(self, url: str) -> tuple:
        """Parse WebSocket URL to extract connection parameters."""
        try:
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Extract the endpoint (remove wss:// prefix and /mqtt path)
            endpoint = parsed_url.netloc
            
            # Extract custom authorizer parameters
            auth_name = query_params.get('x-amz-customauthorizer-name', [None])[0]
            token = query_params.get('token', [None])[0]
            signature = query_params.get('x-amz-customauthorizer-signature', [None])[0]
            
            if not auth_name or not token or not signature:
                raise ConfigurationError("Missing required custom authorizer parameters in URL")
            
            # URL decode the signature
            signature = urllib.parse.unquote(signature)
            
            auth_params = {
                'authorizer': auth_name,
                'token': token,
                'signature': signature
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
            (f"$aws/things/{self._monitor_id}/config/get/accepted", self._on_config_response),
            (f"$aws/things/{self._monitor_id}/config/get/rejected", self._on_config_rejected),
            (f"$aws/things/{self._monitor_id}/shadow/name/state/get/accepted", self._on_state_response),
            (f"$aws/things/{self._monitor_id}/shadow/name/state/get/rejected", self._on_state_rejected),
            (f"$aws/things/{self._monitor_id}/shadow/name/state/update/accepted", self._on_state_update),
            (f"$aws/things/{self._monitor_id}/shadow/name/state/update/rejected", self._on_state_update_rejected)
        ]
        
        successful_subscriptions = 0
        for topic, handler in topics:
            try:
                logger.info(f"🎯 Subscribing to: {topic}")
                self._subscribe_sync(topic, handler)
                successful_subscriptions += 1
                logger.info(f"✅ Successfully subscribed to {topic}")
            except Exception as e:
                logger.error(f"❌ Failed to subscribe to {topic}: {e}")
        
        if successful_subscriptions > 0:
            self._subscriptions_setup = True
            logger.info(f"✅ Set up {successful_subscriptions}/{len(topics)} subscriptions")
            # Give AWS IoT time to fully process and establish subscriptions
            # This prevents timing issues where config requests are sent before
            # subscriptions are fully active on the AWS side
            logger.info("⏳ Waiting for AWS IoT to fully establish subscriptions...")
            time.sleep(2.0)  # Simple 2-second delay to ensure routing is ready
            logger.info("✅ Subscriptions should now be fully established")
        else:
            logger.error("❌ Failed to set up any subscriptions")
            raise ConnectionError("Failed to establish subscriptions")
    
    def _subscribe_sync(self, topic: str, handler: Callable):
        """Internal synchronous subscription method."""
        if not self._client:
            raise ConnectionError("Client not available")
            
        self._topic_handlers[topic] = handler
        
        packet = mqtt5.SubscribePacket(
            subscriptions=[mqtt5.Subscription(topic_filter=topic, qos=mqtt5.QoS.AT_LEAST_ONCE)]
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
            topic=topic,
            payload=payload.encode('utf-8'),
            qos=mqtt5.QoS.AT_LEAST_ONCE
        )
        
        return self._client.publish(packet)
    
    # Message handlers
    
    def _on_message(self, publish_data):
        """Route incoming messages to handlers."""
        try:
            topic = publish_data.publish_packet.topic
            payload = publish_data.publish_packet.payload.decode('utf-8') if publish_data.publish_packet.payload else ""
            
            logger.info(f"📥 Received message on topic '{topic}': {payload[:100]}...")
            
            handler = self._topic_handlers.get(topic)
            if handler:
                try:
                    logger.info(f"🎯 Routing message to handler for topic: {topic}")
                    handler(topic, payload)
                except Exception as e:
                    logger.error(f"❌ Handler error for {topic}: {e}")
            else:
                logger.warning(f"⚠️  No handler registered for topic '{topic}'")
                logger.info(f"🗂️  Available handlers: {list(self._topic_handlers.keys())}")
                
        except Exception as e:
            logger.error(f"❌ Error in message handler: {e}")
    
    def _on_config_response(self, topic: str, payload: str):
        """Handle configuration response."""
        try:
            logger.info(f"📥 Configuration response received on topic: {topic}")
            logger.info(f"📄 Payload: {payload[:200]}..." if len(payload) > 200 else f"📄 Payload: {payload}")
            
            config = json.loads(payload) if payload else {}
            config = config.get("configuration", {}).get("configuration", {})
            
            # Notify callbacks
            for callback in self._config_callbacks:
                try:
                    callback(config)
                except Exception as e:
                    logger.error(f"Error in config callback: {e}")
            
            # Complete future
            if self._config_future and not self._config_future.done():
                self._config_future.set_result(config)
                logger.info("✅ Configuration future completed")
            else:
                logger.warning("No pending config future to complete")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse config JSON: {e}")
            if self._config_future and not self._config_future.done():
                self._config_future.set_exception(ConfigurationError(f"Invalid JSON: {e}"))
        except Exception as e:
            logger.error(f"❌ Config response error: {e}")
            if self._config_future and not self._config_future.done():
                self._config_future.set_exception(ConfigurationError(str(e)))
    
    def _on_config_rejected(self, topic: str, payload: str):
        """Handle configuration request rejection."""
        logger.warning(f"❌ Configuration request rejected on topic: {topic}")
        logger.warning(f"📄 Rejection payload: {payload}")
        if self._config_future and not self._config_future.done():
            self._config_future.set_exception(ConfigurationError(f"Configuration rejected: {payload}"))
    
    def _on_state_response(self, topic: str, payload: str):
        """Handle state response."""
        try:
            logger.info("State response received")
            state = json.loads(payload) if payload else {}
            
            # Notify callbacks
            for callback in self._state_callbacks:
                try:
                    callback(state)
                except Exception as e:
                    logger.error(f"Error in state callback: {e}")
            
            # Complete future
            if self._state_future and not self._state_future.done():
                self._state_future.set_result(state)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state JSON: {e}")
            if self._state_future and not self._state_future.done():
                self._state_future.set_exception(ConfigurationError(f"Invalid JSON: {e}"))
        except Exception as e:
            logger.error(f"State response error: {e}")
            if self._state_future and not self._state_future.done():
                self._state_future.set_exception(ConfigurationError(str(e)))
    
    def _on_state_rejected(self, topic: str, payload: str):
        """Handle state request rejection."""
        logger.warning(f"State request rejected: {payload}")
        if self._state_future and not self._state_future.done():
            self._state_future.set_exception(ConfigurationError(f"State rejected: {payload}"))
    
    def _on_state_update(self, topic: str, payload: str):
        """Handle state update notifications."""
        try:
            logger.info("State update received")
            update = json.loads(payload) if payload else {}
            
            # Notify callbacks with update
            for callback in self._state_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Error in state update callback: {e}")
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state update JSON: {e}")
        except Exception as e:
            logger.error(f"State update error: {e}")
    
    def _on_state_update_rejected(self, topic: str, payload: str):
        """Handle state update rejection."""
        logger.warning(f"State update rejected: {payload}")
    
    # Lifecycle callbacks
    
    def _on_connection_success(self, connack_packet):
        """Handle successful connection."""
        logger.info(f"Connection successful: {connack_packet}")
        self._connected = True
        self._notify_connectivity_change(True)
    
    def _on_connection_failure(self, connack_packet):
        """Handle connection failure."""
        logger.error(f"Connection failed: {connack_packet}")
        self._connected = False
        self._notify_connectivity_change(False)
    
    def _on_disconnection(self, disconnect_packet):
        """Handle disconnection."""
        logger.info(f"Disconnected: {disconnect_packet}")
        self._connected = False
        self._notify_connectivity_change(False)
        
        # If we have a token refresh callback, attempt to reconnect
        if self._token_refresh_callback and not self._monitor_stop_event.is_set():
            logger.info("Unexpected disconnection, attempting to reconnect...")
            self._schedule_reconnect()
    """AWS IoT MQTT5 client transporter with token refresh capabilities."""
    
