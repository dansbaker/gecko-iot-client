Gecko IoT Client Documentation
=============================

Welcome to the Gecko IoT Client documentation! This library provides a Python client for
interacting with Gecko IoT devices through AWS IoT integration.

Overview
--------

The Gecko IoT Client is a comprehensive Python library that allows you to:

* Connect to and control Gecko IoT devices
* Manage different types of zones (temperature, flow, lighting)
* Handle real-time state updates via MQTT
* Integrate with AWS IoT Device Shadow service

Quick Start
-----------

.. code-block:: python

   from gecko_iot_client import GeckoIotClient
   from gecko_iot_client.transporters.mqtt import MqttTransporter

   # Create transporter with WebSocket URL (recommended)
   broker_url = 'wss://your-endpoint.iot.us-east-1.amazonaws.com/mqtt?x-amz-customauthorizer-name=YourAuthorizer&token=your_token&x-amz-customauthorizer-signature=your_signature'
   transporter = MqttTransporter(broker_url)

   # Alternative: Certificate-based authentication
   # transporter = MqttTransporter()
   # transporter.connect(
   #     broker_url="your-iot-endpoint.amazonaws.com",
   #     cert_filepath="path/to/certificate.pem.crt",
   #     pri_key_filepath="path/to/private.pem.key",
   #     ca_filepath="path/to/AmazonRootCA1.pem"
   # )

   # Create and use client
   with GeckoIotClient("your-device-id", transporter) as client:
       zones = client.get_zones()
       print(f"Found {len(zones)} zone types")

Installation
------------

.. code-block:: bash

   pip install gecko-iot-client

   # For development with documentation tools
   pip install gecko-iot-client[docs,dev]

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart
   examples
   configuration

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   
   api

.. toctree::
   :maxdepth: 1
   :caption: Development

   development
   contributing
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`