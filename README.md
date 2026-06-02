# 🦎 Gecko IoT Client (Community Fork)

[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/gecko-iot-client-community.svg)](https://pypi.org/project/gecko-iot-client-community/)

A modern, asynchronous Python client library for Gecko IoT devices with AWS IoT integration. Control and monitor your Gecko-powered spas, hot tubs, and pool equipment with ease.

> **Community fork.** Published to PyPI as `gecko-iot-client-community` to track community-driven fixes (e.g. Gecko's June 2026 cloud migration, Waterlab support) without colliding with the upstream `gecko-iot-client` package. The import name remains `gecko_iot_client`, so application code is unchanged. Upstream: [geckoal/gecko-iot-client](https://github.com/geckoal/gecko-iot-client).

## ✨ Features

- 🌐 **AWS IoT Integration**: Secure MQTT communication via AWS IoT Core
- 🏊 **Multi-Zone Control**: Temperature, lighting, and flow zone management
- 📡 **Real-time Updates**: Event-driven state synchronization
- 🔄 **Async/Await Support**: Modern Python async programming patterns
- 🛡️ **Type Safety**: Full type hints and mypy compatibility
- 📊 **Comprehensive Logging**: Detailed debug and monitoring capabilities
- 🧪 **Well Tested**: Extensive test suite with code coverage
- 📖 **Rich Documentation**: Auto-generated API docs and examples

## 🚀 Quick Start

### Installation

```bash
pip install gecko-iot-client-community
```

### Basic Usage

```python
import asyncio
from gecko_iot_client import GeckoIotClient
from gecko_iot_client.transporters.mqtt import MqttTransporter

async def main():
    # Create MQTT transporter with your AWS IoT endpoint
    transporter = MqttTransporter(
        endpoint="wss://your-endpoint.iot.region.amazonaws.com/mqtt",
        device_id="your-device-id"
    )

    # Initialize client
    client = GeckoIotClient(idd="your-device-id", transporter=transporter)

    async with client:
        # Get all temperature control zones
        temp_zones = client.get_zones_by_type(ZoneType.TEMPERATURE_CONTROL_ZONE)

        for zone in temp_zones:
            print(f"Zone {zone.name}: {zone.temperature}°C (target: {zone.target_temperature}°C)")

        # Control lighting
        lighting_zones = client.get_zones_by_type(ZoneType.LIGHTING_ZONE)
        if lighting_zones:
            light = lighting_zones[0]
            await light.activate()  # Turn on
            await light.set_color(255, 0, 0)  # Set to red

if __name__ == "__main__":
    asyncio.run(main())
```

## 🏗️ Architecture

### Zone Types

The client supports three main zone types:

- **🌡️ Temperature Control Zones**: Heater and temperature management
- **💡 Lighting Zones**: LED lighting control with color support
- **🌊 Flow Zones**: Pump and circulation control

### Event System

```python
def on_temperature_change(zone, old_temp, new_temp):
    print(f"Temperature changed from {old_temp}°C to {new_temp}°C")

client.register_zone_callbacks(lambda zone_name: on_temperature_change)
```

## 📁 Project Structure

```text
gecko-iot-client/
├── .github/workflows/     # CI/CD pipelines
├── gecko_iot_client/      # Main package
│   ├── src/              # Source code
│   │   └── gecko_iot_client/
│   │       ├── models/   # Data models and zone types
│   │       └── transporters/  # Communication layers
│   ├── tests/            # Test suite
│   ├── docs/             # Sphinx documentation
│   └── examples/         # Usage examples
└── README.md             # This file
```

## 🛠️ Development

### Prerequisites

- Python 3.13+
- Poetry (recommended) or pip

### Setup

```bash
# Clone the repository
git clone https://github.com/geckoal/gecko-iot-client.git
cd gecko-iot-client

# Install dependencies
cd gecko_iot_client
pip install -e ".[dev,docs]"

# Run tests
pytest tests/ --cov=gecko_iot_client

# Format code
black src/ tests/
isort src/ tests/

# Build documentation
sphinx-build docs/source docs/build/html

# Generate changelog from git history
./scripts/generate-changelog.sh
# or using the Python entry point
gecko-build-changelog
```

### Running Examples

```bash
# Run the demo script
python gecko_iot_client/examples/demo.py
```

## 📚 Documentation

- **📖 [Full Documentation](https://geckoal.github.io/gecko-iot-client/)** - Complete API reference and guides
- **🎯 [Quick Start Guide](https://geckoal.github.io/gecko-iot-client/quickstart.html)** - Get up and running fast
- **🔧 [Configuration](https://geckoal.github.io/gecko-iot-client/configuration.html)** - Setup and configuration options
- **💡 [Examples](https://geckoal.github.io/gecko-iot-client/examples.html)** - Code examples and use cases

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📊 Testing & Quality

- **✅ Automated Testing**: GitHub Actions run tests on every push and PR
- **📈 Code Coverage**: Monitored via SonarCloud with detailed quality reports
- **🔍 Code Quality**: SonarCloud analysis with Black, isort, and flake8 for consistent style
- **📝 Documentation**: Auto-generated and deployed on every release

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **🐛 Issues**: [GitHub Issues](https://github.com/geckoal/gecko-iot-client/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/geckoal/gecko-iot-client/discussions)

## 🏷️ Versioning Strategy

This project follows [Semantic Versioning (SemVer)](https://semver.org/) combined with [PEP 440](https://peps.python.org/pep-0440/) for Python compatibility.

### Version Format

```text
MAJOR.MINOR.PATCH[-PRERELEASE]
```

- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backward-compatible functionality)
- **PATCH**: Bug fixes (backward-compatible fixes)

### Git Tag Format

All releases use the `v` prefix in git tags:

```bash
# Release versions
v1.0.0          # Major release
v1.1.0          # Minor release
v1.1.1          # Patch release

# Pre-release versions
v1.0.0-alpha.1  # Alpha release
v1.0.0-beta.1   # Beta release
v1.0.0-rc.1     # Release candidate
```

### Release Lifecycle

| Stage | Git Tag Example | PyPI Version | Purpose |
|-------|----------------|--------------|---------|
| **Alpha** | `v0.1.0-alpha.1` | `0.1.0a1` | Early development, internal testing |
| **Beta** | `v0.1.0-beta.1` | `0.1.0b1` | Feature complete, external testing |
| **Release Candidate** | `v0.1.0-rc.1` | `0.1.0rc1` | Final validation before release |
| **Stable Release** | `v0.1.0` | `0.1.0` | Production ready |
| **Patch Release** | `v0.1.1` | `0.1.1` | Bug fixes only |
| **Minor Release** | `v0.2.0` | `0.2.0` | New features, backward compatible |
| **Major Release** | `v1.0.0` | `1.0.0` | Breaking changes |

### Version Detection

Versions are automatically determined from git tags using `setuptools-scm`:

```python
import gecko_iot_client
print(gecko_iot_client.__version__)  # e.g., "0.1.0a2.post1"
```

**Version Components:**

- `0.1.0a2` - Alpha version 2 of release 0.1.0
- `.post1` - 1 commit after the tagged release
- `+dirty` - Local uncommitted changes (development builds)

### Release Process

1. **Development** happens on the `develop` branch
2. **Tagging** creates releases: `git tag v0.1.0-alpha.3 && git push origin v0.1.0-alpha.3`
3. **GitHub Actions** automatically builds and publishes to PyPI
4. **Documentation** is automatically updated and deployed

## 🏷️ Version History

See [CHANGELOG.md](CHANGELOG.md) for a detailed version history.

---

**Made with ❤️ by the Gecko Team**
*Powering the future of spa control*
