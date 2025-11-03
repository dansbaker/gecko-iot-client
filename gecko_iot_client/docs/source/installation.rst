Installation
============

Requirements
------------

* Python 3.13 or higher
* Active internet connection for AWS IoT communication

Basic Installation
------------------

Install the Gecko IoT Client using pip:

.. code-block:: bash

   pip install gecko-iot-client

Development Installation
-----------------------

For development with additional tools:

.. code-block:: bash

   pip install gecko-iot-client[dev,docs]

This includes:
* Testing tools (pytest, pytest-cov)
* Code formatting (black, isort, flake8)
* Documentation tools (sphinx, sphinx-rtd-theme)

From Source
-----------

To install from source:

.. code-block:: bash

   git clone <repository-url>
   cd geckoIotClient/python/gecko_iot_client
   pip install -e .

AWS IoT Prerequisites
---------------------

Before using the Gecko IoT Client, you'll need:

1. **AWS IoT Core Setup**: An AWS IoT Core thing configured for your device
2. **Certificates**: Device certificate, private key, and root CA certificate
3. **Permissions**: Proper IAM policies for IoT operations


Verification
------------

Verify your installation:

.. code-block:: python

   import gecko_iot_client
   print(gecko_iot_client.__version__)  # Should print version number