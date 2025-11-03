# 🦎 Gecko IoT Client

[![Python Version](https://img.shields.io/badge/python-3.13+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/geckoal/gecko-iot-client/workflows/Tests/badge.svg)](https://github.com/geckoal/gecko-iot-client/actions/workflows/test.yml)
[![Documentation](https://github.com/geckoal/gecko-iot-client/workflows/Documentation/badge.svg)](https://github.com/geckoal/gecko-iot-client/actions/workflows/docs.yml)
[![Code Coverage](https://codecov.io/gh/geckoal/gecko-iot-client/branch/main/graph/badge.svg)](https://codecov.io/gh/geckoal/gecko-iot-client)
[![PyPI Version](https://img.shields.io/pypi/v/gecko-iot-client.svg)](https://pypi.org/project/gecko-iot-client/)

A modern, asynchronous Python client library for Gecko IoT devices with AWS IoT integration. Control and monitor your Gecko-powered spas, hot tubs, and pool equipment with ease.

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
pip install gecko-iot-client
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

```
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
- **📈 Code Coverage**: Monitored via Codecov with detailed reports
- **🔍 Code Quality**: Black, isort, and flake8 ensure consistent style
- **📝 Documentation**: Auto-generated and deployed on every release

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **🐛 Issues**: [GitHub Issues](https://github.com/geckoal/gecko-iot-client/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/geckoal/gecko-iot-client/discussions)

## 🏷️ Version History

See [CHANGELOG.md](CHANGELOG.md) for a detailed version history.

---

**Made with ❤️ by the Gecko Team**  
*Powering the future of smart pool and spa control*