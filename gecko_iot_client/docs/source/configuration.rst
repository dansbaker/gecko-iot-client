Configuration
=============

This page covers advanced configuration options for the Gecko IoT Client.

Transport Configuration
-----------------------

MQTT Transport Options
~~~~~~~~~~~~~~~~~~~~~~

The Gecko IoT Client supports multiple authentication methods for AWS IoT.

WebSocket with Custom Authorizer (Recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method embeds authentication directly in the broker URL:

.. code-block:: python

   from gecko_iot_client.transporters.mqtt import MqttTransporter
   
   # Complete broker URL with embedded authentication
   broker_url = 'wss://your-endpoint.iot.us-east-1.amazonaws.com/mqtt?x-amz-customauthorizer-name=YourCustomAuthorizer&token=your_auth_token&x-amz-customauthorizer-signature=your_signature'
   
   transporter = MqttTransporter(broker_url)

URL Format Details
^^^^^^^^^^^^^^^^^^

For WebSocket connections, the broker URL format is:

::

   wss://ENDPOINT/mqtt?PARAMETERS

Required URL parameters:

- ``x-amz-customauthorizer-name``: Name of your custom authorizer
- ``token``: Authentication token (JWT or custom format)
- ``x-amz-customauthorizer-signature``: Signature for the token (URL-encoded)

Example URL breakdown:

::

   wss://a28a28s8rcruem-ats.iot.us-east-1.amazonaws.com/mqtt
   ?x-amz-customauthorizer-name=ThirdPartyMqttCustomAuthorizer
   &token=eyJ1c2VySWQiOiJhdXRoMHw2ODg0ZjRjNjYzZTliOTg3YTYyMTUzNDIi...
   &x-amz-customauthorizer-signature=nOoaeoOoXweFx3uJ1UoxJ0zh4737BSIAmPq9Q%2FKtZj4n...

Connection Monitoring
~~~~~~~~~~~~~~~~~~~~~

Monitor connection state changes:

.. code-block:: python

   def on_connection_state_change(state):
       print(f"🔌 Connection state changed to: {state}")
   
   def on_connection_event(event):
       print(f"🔌 Connection event: {event.state.value} - {event.message}")
   
   transporter = MqttTransporter(broker_url)
   transporter.on_connection_state_change(on_connection_state_change)
   transporter.on_connection_event(on_connection_event)

Logging Configuration
--------------------

Configure logging for better debugging:

.. code-block:: python

   import logging
   
   # Basic logging setup
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   
   # More detailed logging for debugging
   logging.basicConfig(
       level=logging.DEBUG,
       format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
       handlers=[
           logging.FileHandler('gecko_iot.log'),
           logging.StreamHandler()
       ]
   )

Logger Categories
~~~~~~~~~~~~~~~~~

Different components use different loggers:

.. code-block:: python

   # Main client logger
   client_logger = logging.getLogger('GeckoIotClient')
   client_logger.setLevel(logging.INFO)
   
   # Transport logger
   transport_logger = logging.getLogger('MqttTransporter')
   transport_logger.setLevel(logging.DEBUG)
   
   # Zone logger
   zone_logger = logging.getLogger('ZoneStateManager')
   zone_logger.setLevel(logging.INFO)

AWS IoT Configuration
--------------------

Thing Configuration
~~~~~~~~~~~~~~~~~~~

Your AWS IoT Thing should have these attributes:

.. code-block:: json

   {
     "attributes": {
       "deviceType": "gecko-spa",
       "model": "spa-controller-v1",
       "serialNumber": "SPA001234"
     }
   }

Environment Variables
--------------------

Use environment variables for configuration:

WebSocket Authentication
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import os
   from gecko_iot_client import GeckoIotClient
   from gecko_iot_client.transporters.mqtt import MqttTransporter
   
   # Configuration from environment
   device_id = os.getenv("GECKO_DEVICE_ID")
   broker_url = os.getenv("GECKO_BROKER_URL")
   
   # Validate required configuration
   if not device_id:
       raise ValueError("GECKO_DEVICE_ID environment variable required")
   if not broker_url:
       raise ValueError("GECKO_BROKER_URL environment variable required")
   
   # Create client
   transporter = MqttTransporter(broker_url)
   client = GeckoIotClient(device_id, transporter)

Performance Tuning
------------------

Connection Optimization
~~~~~~~~~~~~~~~~~~~~~~~

For high-frequency updates:

.. code-block:: python

   transporter = MqttTransporter(
       # ... connection details
       keep_alive_secs=60,          # Longer keep alive
       ping_timeout_ms=10000,       # Longer ping timeout
       reconnect_min_timeout_secs=5,    # Faster initial reconnect
       clean_session=False,         # Preserve session
   )

Callback Optimization
~~~~~~~~~~~~~~~~~~~~~

Efficient zone monitoring:

.. code-block:: python

   def efficient_zone_callback(zone_name):
       """Optimized callback that only logs important changes"""
       important_attributes = {'active', 'speed', 'temperature_', 'set_point'}
       
       def callback(attribute, old_value, new_value):
           if attribute in important_attributes:
               print(f"[{zone_name}] {attribute}: {old_value} → {new_value}")
       return callback

Troubleshooting
--------------

Common Issues
~~~~~~~~~~~~~

1. **Connection Timeout**: Check endpoint URL and network connectivity
2. **Certificate Errors**: Verify certificate files and permissions
3. **Policy Errors**: Ensure AWS IoT policy allows required actions
4. **Zone Not Found**: Verify device configuration in AWS IoT

Debug Mode
~~~~~~~~~~

Enable debug logging for troubleshooting:

.. code-block:: python

   import logging
   
   # Enable debug logging for all gecko components
   logging.getLogger('gecko_iot_client').setLevel(logging.DEBUG)
   logging.getLogger('awscrt').setLevel(logging.WARNING)  # Reduce AWS noise
   
   # Use debug transporter
   transporter = MqttTransporter(
       # ... config
       ping_timeout_ms=10000,  # Longer timeout for debugging
   )

Testing Connectivity
~~~~~~~~~~~~~~~~~~~~

Test basic connectivity:

.. code-block:: python

   def test_basic_connectivity(transporter):
       """Test basic MQTT connectivity"""
       try:
           transporter.connect()
           print("✓ MQTT connection successful")
           
           # Test configuration loading
           transporter.load_configuration()
           print("✓ Configuration loading initiated")
           
           transporter.disconnect()
           print("✓ Clean disconnection")
           
       except Exception as e:
           print(f"❌ Connectivity test failed: {e}")
           raise