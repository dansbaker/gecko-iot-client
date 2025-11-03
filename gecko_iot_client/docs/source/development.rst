Development
===========

This guide covers setting up a development environment and contributing to the Gecko IoT Client.

Development Setup
-----------------

Prerequisites
~~~~~~~~~~~~~

* Python 3.13 or higher
* Git
* Virtual environment tool (venv, conda, etc.)

Clone and Setup
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Clone the repository
   git clone <repository-url>
   cd geckoIotClient/python/gecko_iot_client
   
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install development dependencies
   pip install -e .[dev,docs]

Project Structure
-----------------

::

   gecko_iot_client/
   ├── src/
   │   └── gecko_iot_client/
   │       ├── __init__.py              # Main client class
   │       ├── models/                  # Zone models and parsers
   │       │   ├── zone_states.py       # Zone state classes
   │       │   ├── zone_parser.py       # Configuration parser
   │       │   └── zone_state_manager.py # State management
   │       └── transporters/            # Transport implementations
   │           ├── __init__.py          # Abstract transporter
   │           ├── mqtt.py              # MQTT/AWS IoT transport
   │           └── exceptions.py        # Transport exceptions
   ├── tests/                           # Unit tests
   ├── examples/                        # Example code
   ├── docs/                           # Documentation
   └── pyproject.toml                  # Project configuration

Code Style
----------

The project follows Python best practices:

* **Black** for code formatting
* **isort** for import sorting  
* **flake8** for linting
* **Type hints** throughout
* **Google-style docstrings**

Format Code
~~~~~~~~~~~

.. code-block:: bash

   # Format code
   black src/ tests/ examples/
   
   # Sort imports
   isort src/ tests/ examples/
   
   # Check linting
   flake8 src/ tests/ examples/

Running Tests
-------------

Unit Tests
~~~~~~~~~~

.. code-block:: bash

   # Run all tests
   pytest
   
   # Run with coverage
   pytest --cov=gecko_iot_client --cov-report=html
   
   # Run specific test file
   pytest tests/test_zone_states.py
   
   # Run with verbose output
   pytest -v

Test Coverage
~~~~~~~~~~~~~

Aim for high test coverage:

.. code-block:: bash

   # Generate coverage report
   pytest --cov=gecko_iot_client --cov-report=term-missing
   
   # Generate HTML coverage report
   pytest --cov=gecko_iot_client --cov-report=html
   open htmlcov/index.html

Writing Tests
~~~~~~~~~~~~~

Example test structure:

.. code-block:: python

   import pytest
   from gecko_iot_client.models.zone_states import FlowZone, ZoneType
   
   
   class TestFlowZone:
       def test_flow_zone_creation(self):
           """Test basic flow zone creation"""
           zone = FlowZone(
               id="pump1",
               name="Main Circulation",
               zone_type=ZoneType.FLOW_ZONE,
               speed=75.0,
               active=True
           )
           
           assert zone.id == "pump1"
           assert zone.name == "Main Circulation"
           assert zone.speed == 75.0
           assert zone.active is True
       
       def test_flow_zone_validation(self):
           """Test flow zone field validation"""
           with pytest.raises(ValueError):
               FlowZone(
                   id="pump1",
                   zone_type=ZoneType.FLOW_ZONE,
                   speed=150.0  # Invalid: > 100
               )
       
       def test_flow_zone_callbacks(self):
           """Test zone change callbacks"""
           zone = FlowZone(id="pump1", zone_type=ZoneType.FLOW_ZONE)
           
           changes = []
           def callback(attr, old, new):
               changes.append((attr, old, new))
           
           zone.register_callback(callback, "speed")
           zone.speed = 50.0
           
           assert len(changes) == 1
           assert changes[0] == ("speed", None, 50.0)

Documentation
-------------

Building Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Build HTML documentation
   cd docs
   make html
   
   # View documentation
   open build/html/index.html
   
   # Clean build
   make clean html

Live Documentation
~~~~~~~~~~~~~~~~~

For development, use auto-rebuild:

.. code-block:: bash

   # Install sphinx-autobuild
   pip install sphinx-autobuild
   
   # Start live documentation server
   cd docs
   make livehtml
   
   # Open http://localhost:8000 in browser

Documentation Guidelines
~~~~~~~~~~~~~~~~~~~~~~~

* Use Google-style docstrings
* Include examples in docstrings
* Document all public methods and classes
* Keep documentation up-to-date with code changes

Example docstring:

.. code-block:: python

   def set_speed_desired(self, speed: float, active: bool = True) -> None:
       """
       Set flow speed in desired state (publishes to AWS IoT).
       
       This method validates the speed value and publishes the desired
       state update to the AWS IoT Device Shadow service.
       
       Args:
           speed: Flow speed percentage between 0.0 and 100.0
           active: Whether to activate the zone (default: True)
           
       Raises:
           ValueError: If speed is outside valid range (0-100)
           
       Example:
           >>> pump = flow_zones[0]
           >>> pump.set_speed_desired(75.0, active=True)
       """

Debugging
---------

Enable Debug Logging
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import logging
   
   # Enable debug logging
   logging.basicConfig(
       level=logging.DEBUG,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )

Mock Testing
~~~~~~~~~~~~

For testing without AWS IoT:

.. code-block:: python

   from unittest.mock import Mock
   from gecko_iot_client import GeckoIotClient
   
   # Create mock transporter
   mock_transporter = Mock()
   mock_transporter.connect.return_value = None
   mock_transporter.disconnect.return_value = None
   
   # Use mock in tests
   client = GeckoIotClient("test-device", mock_transporter)

Integration Testing
~~~~~~~~~~~~~~~~~~

Test with real AWS IoT:

.. code-block:: python

   import os
   import pytest
   from gecko_iot_client import GeckoIotClient
   from gecko_iot_client.transporters.mqtt import MqttTransporter
   
   
   @pytest.mark.integration
   @pytest.mark.skipif(
       not os.getenv("AWS_IOT_ENDPOINT"),
       reason="AWS IoT credentials not available"
   )
   def test_real_connection():
       """Test with real AWS IoT connection"""
       transporter = MqttTransporter(
           endpoint=os.getenv("AWS_IOT_ENDPOINT"),
           certificate_path=os.getenv("AWS_IOT_CERT_PATH"),
           private_key_path=os.getenv("AWS_IOT_KEY_PATH"),
           ca_file_path=os.getenv("AWS_IOT_CA_PATH")
       )
       
       with GeckoIotClient("test-device", transporter) as client:
           # Test basic functionality
           zones = client.get_zones()
           assert isinstance(zones, dict)

Performance Testing
------------------

Benchmark Zone Operations
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import time
   import statistics
   from gecko_iot_client.models.zone_states import FlowZone, ZoneType
   
   
   def benchmark_zone_updates():
       """Benchmark zone attribute updates"""
       zone = FlowZone(id="test", zone_type=ZoneType.FLOW_ZONE)
       
       # Measure update performance
       times = []
       for i in range(1000):
           start = time.perf_counter()
           zone.speed = float(i % 100)
           end = time.perf_counter()
           times.append(end - start)
       
       print(f"Average update time: {statistics.mean(times):.6f}s")
       print(f"Median update time: {statistics.median(times):.6f}s")

Memory Profiling
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install memory profiler
   pip install memory-profiler
   
   # Profile memory usage
   python -m memory_profiler examples/demo.py

Release Process
--------------

Version Management
~~~~~~~~~~~~~~~~~

Update version in `pyproject.toml`:

.. code-block:: toml

   [project]
   version = "0.2.0"

Create Release
~~~~~~~~~~~~~

.. code-block:: bash

   # Ensure tests pass
   pytest
   
   # Update version
   # Edit pyproject.toml
   
   # Build package
   python -m build
   
   # Create git tag
   git tag v0.2.0
   git push origin v0.2.0

Publishing
~~~~~~~~~

.. code-block:: bash

   # Install build tools
   pip install build twine
   
   # Build package
   python -m build
   
   # Check package
   twine check dist/*
   
   # Upload to PyPI (test first)
   twine upload --repository testpypi dist/*
   twine upload dist/*

Continuous Integration
---------------------

GitHub Actions workflow example:

.. code-block:: yaml

   name: Tests
   
   on: [push, pull_request]
   
   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python-version: [3.13]
       
       steps:
       - uses: actions/checkout@v2
       
       - name: Set up Python ${{ matrix.python-version }}
         uses: actions/setup-python@v2
         with:
           python-version: ${{ matrix.python-version }}
       
       - name: Install dependencies
         run: |
           python -m pip install --upgrade pip
           pip install -e .[dev]
       
       - name: Run tests
         run: |
           pytest --cov=gecko_iot_client
       
       - name: Check code style
         run: |
           black --check src/ tests/
           isort --check-only src/ tests/
           flake8 src/ tests/

Common Development Tasks
-----------------------

Add New Zone Type
~~~~~~~~~~~~~~~~

1. Define enum value in `ZoneType`
2. Create zone class inheriting from `AbstractZone`
3. Register with `@AbstractZone.register_zone_type()`
4. Add tests for new zone type
5. Update documentation

Add New Transport
~~~~~~~~~~~~~~~~

1. Create class inheriting from `AbstractTransporter`
2. Implement all abstract methods
3. Add connection handling
4. Add configuration options
5. Add tests and documentation

Add New Feature
~~~~~~~~~~~~~~

1. Create feature branch
2. Implement feature with tests
3. Update documentation
4. Run full test suite
5. Create pull request

Getting Help
-----------

* Read the API documentation
* Check existing tests for examples
* Look at the examples directory
* Create GitHub issues for bugs
* Use discussions for questions