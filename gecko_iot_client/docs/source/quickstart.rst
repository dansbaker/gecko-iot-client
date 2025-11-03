Quick Start Guide
================

This guide will get you up and running with the Gecko IoT Client in just a few minutes.

Basic Usage
-----------

1. Import the Required Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from gecko_iot_client import GeckoIotClient
   from gecko_iot_client.transporters.mqtt import MqttTransporter

2. Create a Transport Instance  
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using WebSocket with Custom Authorizer (Recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Direct broker URL with embedded authentication
   broker_url = 'wss://your-endpoint.iot.us-east-1.amazonaws.com/mqtt?x-amz-customauthorizer-name=YourCustomAuthorizer&token=your_auth_token&x-amz-customauthorizer-signature=your_signature'
   
   transporter = MqttTransporter(broker_url)


3. Connect and Use the Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Using context manager (recommended)
   with GeckoIotClient("your-device-id", transporter) as client:
       # Get all zones
       zones = client.get_zones()
       print(f"Found {len(zones)} zone types")
       
       # Get specific zone types
       flow_zones = client.get_zones_by_type(ZoneType.FLOW_ZONE)
       temp_zones = client.get_zones_by_type(ZoneType.TEMPERATURE_CONTROL_ZONE)
       
       # List all zones with basic info
       zone_list = client.list_zones()
       for zone_info in zone_list:
           print(f"Zone {zone_info['name']} ({zone_info['type']})")

Working with Zones
------------------

Flow Zones
~~~~~~~~~~

.. code-block:: python

   # Get flow zones
   flow_zones = client.get_zones_by_type(ZoneType.FLOW_ZONE)
   
   if flow_zones:
       pump = flow_zones[0]
       
       # Set desired flow speed (publishes to AWS IoT)
       pump.set_speed_desired(75.0, active=True)
       
       # Activate/deactivate
       pump.activate_desired()
       pump.deactivate_desired()

Temperature Control Zones
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Get temperature zones
   temp_zones = client.get_zones_by_type(ZoneType.TEMPERATURE_CONTROL_ZONE)
   
   if temp_zones:
       heater = temp_zones[0]
       
       # Set target temperature (publishes to AWS IoT)
       heater.set_target_temperature_desired(25.5)  # 25.5°C
       
       # Check current state
       current_temp = heater.temperature_
       target_temp = heater.set_point
       print(f"Current: {current_temp}°C, Target: {target_temp}°C")

Lighting Zones
~~~~~~~~~~~~~~

.. code-block:: python

   # Get lighting zones
   light_zones = client.get_zones_by_type(ZoneType.LIGHTING_ZONE)
   
   if light_zones:
       light = light_zones[0]
       
       # Set color (publishes to AWS IoT)
       light.set_color_desired(255, 100, 50, active=True)  # Orange color
       
       # Set lighting effect
       light.set_effect_desired("rainbow", active=True)

Monitoring Changes
------------------

Zone Change Callbacks
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def zone_change_handler(zone_name):
       def callback(attribute, old_value, new_value):
           print(f"[{zone_name}] {attribute}: {old_value} → {new_value}")
       return callback
   
   # Register callbacks for all zones
   client.register_zone_callbacks(zone_change_handler)

Zone Update Callbacks
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def on_zones_updated(zones_dict):
       print("Zones were updated with new state!")
       for zone_type, zone_list in zones_dict.items():
           print(f"  {zone_type.value}: {len(zone_list)} zones")
   
   client.on_zone_update(on_zones_updated)

Error Handling
--------------

Always handle potential errors:

.. code-block:: python

   try:
       with GeckoIotClient("device-123", transporter) as client:
           zones = client.get_zones()
           
           # Control zones
           flow_zones = client.get_zones_by_type(ZoneType.FLOW_ZONE)
           if flow_zones:
               flow_zones[0].set_speed_desired(50.0)
               
   except Exception as e:
       print(f"Error: {e}")

Complete Example
----------------

Here's a complete working example:

.. code-block:: python

   from gecko_iot_client import GeckoIotClient, ZoneType
   from gecko_iot_client.transporters.mqtt import MqttTransporter
   import time
   
   def main():
       # Setup transporter with WebSocket URL (recommended)
       broker_url = 'wss://your-endpoint.iot.us-east-1.amazonaws.com/mqtt?x-amz-customauthorizer-name=YourCustomAuthorizer&token=your_token&x-amz-customauthorizer-signature=your_signature'
       transporter = MqttTransporter(broker_url)
       
       # Setup client
       with GeckoIotClient("my-spa-device", transporter) as client:
           # Wait for configuration to load
           time.sleep(2)
           
           # List all zones
           zones = client.list_zones()
           print(f"Available zones:")
           for zone in zones:
               print(f"  {zone['name']} ({zone['type']})")
           
           # Control flow zones
           flow_zones = client.get_zones_by_type(ZoneType.FLOW_ZONE)
           for pump in flow_zones:
               print(f"Setting {pump.name} to 60% speed")
               pump.set_speed_desired(60.0, active=True)
           
           # Monitor for a while
           print("Monitoring for 30 seconds...")
           time.sleep(30)
   
   if __name__ == "__main__":
       main()

Next Steps
----------

* Read the :doc:`examples` for more detailed use cases
* Check the :doc:`api/client` for complete API reference
* See :doc:`configuration` for advanced setup options