Changelog
=========

All notable changes to the Gecko IoT Client will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[Unreleased]
------------

Added
~~~~~
- Comprehensive documentation with Sphinx
- API reference documentation
- User guide and examples
- Development guide

Changed
~~~~~~~

Deprecated
~~~~~~~~~~

Removed
~~~~~~~

Fixed
~~~~~

Security
~~~~~~~~

[0.1.0] - 2024-10-21
--------------------

Added
~~~~~
- Initial release of Gecko IoT Client
- Support for three zone types: flow, temperature control, and lighting
- MQTT transport layer for AWS IoT integration
- Zone state management with callbacks
- Pydantic-based validation for zone models
- Context manager support for client lifecycle
- Automatic configuration and state loading
- Desired state publishing to AWS IoT Device Shadow

Features
~~~~~~~~
- **Flow Zones**: Control pump speed and activation
- **Temperature Control Zones**: Manage heating setpoints and eco mode
- **Lighting Zones**: Control RGBI colors and lighting effects
- **Transport Abstraction**: Pluggable transport layer architecture
- **Real-time Updates**: Callbacks for zone state changes
- **AWS IoT Integration**: Full Device Shadow support

Technical
~~~~~~~~~
- Python 3.13+ support
- Type hints throughout
- Comprehensive error handling
- Logging integration
- Clean architecture with separation of concerns