# AWS IoT MQTT Transporter

A robust AWS IoT MQTT5 client implementation with automatic token refresh and connection management.

## Features

- **AWS IoT MQTT5 Support**: Built using `awscrt` and `awsiot` libraries for optimal performance
- **Automatic Token Refresh**: Built-in token management with configurable refresh thresholds
- **Connection State Management**: Comprehensive connection state tracking and automatic reconnection
- **Error Handling**: Robust error management with custom exception classes
- **Logging**: Structured logging with connection metrics and event tracking
- **Thread Safe**: Safe for use in multi-threaded applications

## Installation

Add the following dependencies to your project:

```toml
dependencies = [
    "pydantic>=2.0.0",
    "awscrt>=0.19.0",
    "awsiot>=1.20.0"
]
```

## Quick Start

### Certificate-based Authentication

```python
from gecko_iot_client.transporters.mqtt import MqttTransporter

# Create transporter
mqtt = MqttTransporter()

# Setup connection state callback
def on_connection_state_change(state):
    print(f"Connection state: {state}")

mqtt.on_connection_state_change(on_connection_state_change)

# Connect using certificates
mqtt.connect(
    "your-iot-endpoint.iot.us-east-1.amazonaws.com",
    client_id="my-device",
    cert_filepath="/path/to/device.pem.crt",
    pri_key_filepath="/path/to/private.pem.key",
    ca_filepath="/path/to/Amazon-root-CA-1.pem"
)

# Your device is now connected!
print(f"Connected: {mqtt.is_connected()}")

# Disconnect when done
mqtt.disconnect()
```

### Token-based Authentication with Auto-refresh

```python
from gecko_iot_client.transporters.mqtt import MqttTransporter

def get_fresh_token():
    """Your token refresh logic here"""
    return {
        'access_token': 'your_token_here',
        'username': 'your_username',
        'expires_in': 3600  # 1 hour
    }

mqtt = MqttTransporter()

# Connect with token refresh capability
mqtt.connect(
    "your-iot-endpoint.iot.us-east-1.amazonaws.com",
    client_id="my-device", 
    username="device_user",
    password="initial_token",
    region="us-east-1",
    token_refresh_callback=get_fresh_token
)

# Set initial token
mqtt.set_token(get_fresh_token())

# Tokens will be automatically refreshed before expiration
```

## Architecture

The implementation consists of several key components:

### 1. MqttTransporter
The main client class that handles AWS IoT connections using MQTT5.

**Key Methods:**

*Connection Management:*
- `connect(broker_url, **kwargs)` - Connect to AWS IoT
- `disconnect()` - Disconnect from broker
- `is_connected()` - Check connection status

*Token Management:*
- `set_token(token_data)` - Set authentication token
- `refresh_token()` - Manually refresh token

*State Management:*
- `on_connection_state_change(callback)` - Register connection state callback
- `on_connection_event(callback)` - Register detailed connection event callback
- `on_state_change(callback)` - Register general state callback (base class)
- `change_state(new_state)` - Change general application state
- `get_connection_state()` - Get current connection state

### 2. TokenManager
Handles automatic token refresh with configurable thresholds.

**Features:**
- Background monitoring of token expiration
- Configurable refresh threshold (default: 15 minutes before expiry)
- Callback notifications on token refresh
- Thread-safe token operations

### 3. ConnectionStateManager
Manages connection states and automatic reconnection.

**States:**
- `DISCONNECTED` - Not connected
- `CONNECTING` - Establishing connection
- `CONNECTED` - Successfully connected
- `RECONNECTING` - Attempting to reconnect
- `CONNECTION_FAILED` - Connection attempt failed
- `DISCONNECTING` - Gracefully disconnecting
- `CREDENTIAL_REFRESH_FAILED` - Token/credential refresh failed

**Features:**
- Exponential backoff for reconnection attempts
- Configurable maximum retry attempts
- Connection event history tracking

### 4. Exception Handling
Custom exception classes for different error scenarios:

- `ConnectionError` - Connection establishment failures
- `AuthenticationError` - Authentication failures
- `TokenRefreshError` - Token refresh failures
- `DisconnectionError` - Disconnection failures
- `ConfigurationError` - Invalid configuration

### 5. Logging
Structured logging with connection metrics:

- Connection attempt tracking
- Success/failure rates
- Token refresh events
- Detailed error reporting
- Configurable log levels and output

## Configuration Options

### Connection Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `broker_url` | str | AWS IoT endpoint URL | Required |
| `client_id` | str | MQTT client identifier | Auto-generated |
| `port` | int | Connection port | 8883 |
| `cert_filepath` | str | Device certificate path | None |
| `pri_key_filepath` | str | Private key path | None |
| `ca_filepath` | str | CA certificate path | None |
| `username` | str | Username for auth | None |
| `password` | str | Password for auth | None |
| `region` | str | AWS region | us-east-1 |
| `keep_alive_secs` | int | Keep alive interval | 30 |
| `clean_start` | bool | Clean start flag | True |
| `token_refresh_callback` | Callable | Token refresh function | None |

### Token Manager Settings

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `refresh_threshold_minutes` | int | Minutes before expiry to refresh | 15 |

### Connection State Manager Settings

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `reconnect_enabled` | bool | Enable auto-reconnection | True |
| `max_reconnect_attempts` | int | Maximum retry attempts | 5 |
| `initial_retry_delay` | float | Initial retry delay (seconds) | 1.0 |
| `max_retry_delay` | float | Maximum retry delay (seconds) | 60.0 |
| `backoff_multiplier` | float | Exponential backoff multiplier | 2.0 |

## Error Handling

The transporter provides comprehensive error handling:

```python
from gecko_iot_client.transporters.exceptions import (
    ConnectionError, 
    AuthenticationError, 
    TokenRefreshError
)

try:
    mqtt.connect(broker_url, **config)
except ConnectionError as e:
    print(f"Failed to connect: {e}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except TokenRefreshError as e:
    print(f"Token refresh failed: {e}")
```

## Advanced Usage

### Custom State Monitoring

**Connection State Monitoring:**
```python
from gecko_iot_client.transporters.connection_state import ConnectionEvent

# Simple connection state changes
def on_connection_change(state: str):
    print(f"Connection: {state}")

mqtt.on_connection_state_change(on_connection_change)

# Detailed connection events
def on_connection_event(event: ConnectionEvent):
    print(f"Connection Event: {event.state.value} at {event.timestamp}")
    if event.message:
        print(f"Message: {event.message}")
    if event.error:
        print(f"Error: {event.error}")

mqtt.on_connection_event(on_connection_event)
```

**General Application State Monitoring:**
```python
# For IoT device states, sensor data, etc. (base class interface)
def on_device_state_change(state: str):
    print(f"Device State: {state}")

mqtt.on_state_change(on_device_state_change)

# Trigger state changes
mqtt.change_state("sensor_active")      # General state
mqtt.change_state("collecting_data")    # General state
```

### Connection Statistics

```python
# Get connection history
history = mqtt.get_connection_history()
for event in history:
    print(f"{event.timestamp}: {event.state.value}")

# Current connection state
state = mqtt.get_connection_state()
print(f"Current state: {state.value}")

# Reconnection settings
print(f"Reconnection enabled: {mqtt.is_reconnection_enabled()}")
mqtt.disable_reconnection()  # Disable auto-reconnect
mqtt.enable_reconnection()   # Re-enable auto-reconnect
```

### Custom Logging

```python
from gecko_iot_client.transporters.logging_config import setup_mqtt_logging

# Setup custom logging
logger, event_logger = setup_mqtt_logging(
    log_level="DEBUG",
    log_file="mqtt.log",
    enable_console=True
)

# Get connection statistics
stats = event_logger.get_connection_stats()
print(f"Success rate: {stats['success_rate']:.1f}%")
```

## Best Practices

1. **Always handle exceptions** when connecting/disconnecting
2. **Use certificate-based auth** when possible for better security
3. **Implement token refresh callbacks** for long-running applications
4. **Monitor connection state** for application health
5. **Configure appropriate timeouts** based on your network conditions
6. **Enable logging** for debugging and monitoring
7. **Test reconnection scenarios** in your application

## Troubleshooting

### Common Issues

1. **Import errors for AWS libraries**: Install dependencies with `pip install awscrt awsiot`
2. **Certificate authentication fails**: Check file paths and permissions
3. **Connection timeouts**: Verify endpoint URL and network connectivity
4. **Token refresh failures**: Ensure refresh callback is properly implemented
5. **Reconnection not working**: Check if reconnection is enabled and max attempts

### Debug Logging

Enable debug logging to see detailed connection information:

```python
from gecko_iot_client.transporters.logging_config import setup_mqtt_logging

setup_mqtt_logging(log_level="DEBUG", enable_console=True)
```

## License

This implementation is part of the Gecko IoT Client project.