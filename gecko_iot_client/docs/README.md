# Gecko IoT Client Documentation

This directory contains the Sphinx-based documentation for the Gecko IoT Client.

## Building Documentation Locally

### Prerequisites

- Python 3.13+
- Virtual environment with documentation dependencies

### Quick Build

```bash
# From the docs directory
./build-docs.sh
```

Or manually:

```bash
# Install dependencies
pip install -e .[docs]

# Build documentation
cd docs
make html

# View documentation
open build/html/index.html
```

### Live Documentation (Auto-rebuild)

For development with automatic rebuilding:

```bash
# Install additional dependency
pip install sphinx-autobuild

# Start live server
cd docs
make livehtml

# Open http://localhost:8000 in browser
```

## Documentation Structure

```
docs/
├── source/
│   ├── index.rst              # Main index page
│   ├── installation.rst       # Installation guide
│   ├── quickstart.rst         # Quick start guide
│   ├── examples.rst           # Practical examples
│   ├── configuration.rst      # Configuration guide
│   ├── development.rst        # Development guide
│   ├── contributing.rst       # Contributing guide
│   ├── changelog.rst          # Version history
│   ├── api/                   # API reference
│   │   ├── client.rst         # Main client API
│   │   ├── transporters.rst   # Transport layer API
│   │   ├── models.rst         # Zone models API
│   │   └── exceptions.rst     # Exception classes
│   ├── _static/               # Static assets
│   └── _templates/            # Custom templates
├── build/                     # Generated documentation
├── Makefile                   # Build commands
├── make.bat                   # Windows build commands
└── build-docs.sh             # Build script
```

## Writing Documentation

### Style Guide

- Use reStructuredText (RST) format
- Follow Google-style docstrings in code
- Include practical examples
- Keep language clear and concise

### API Documentation

API documentation is automatically generated from docstrings using Sphinx autodoc. To add a new module:

1. Add proper docstrings to your code
2. Create or update the appropriate `.rst` file in `source/api/`
3. Add automodule directives

Example:

```rst
New Module
----------

.. automodule:: gecko_iot_client.new_module
   :members:
   :undoc-members:
   :show-inheritance:
```

### Adding Examples

Add practical examples to `source/examples.rst`:

```rst
New Feature Example
-------------------

Description of the example.

.. code-block:: python

   from gecko_iot_client import GeckoIotClient
   
   # Example code here
```

## Documentation Deployment

Documentation is automatically built and deployed via GitHub Actions:

- **Pull requests**: Documentation is built and artifacts are uploaded
- **Main branch**: Documentation is deployed to GitHub Pages

### Manual Deployment

To deploy documentation manually:

```bash
# Build documentation
./build-docs.sh

# The built documentation is in build/html/
# Deploy to your preferred hosting service
```

## Configuration

Documentation configuration is in `source/conf.py`. Key settings:

- **Theme**: Using `sphinx_rtd_theme`
- **Extensions**: autodoc, napoleon, intersphinx, etc.
- **API Documentation**: Automatic generation from docstrings

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the package is installed with `pip install -e .`
2. **Missing Dependencies**: Install with `pip install -e .[docs]`
3. **Build Warnings**: Check RST syntax and docstring formatting

### Getting Help

- Check the [Sphinx documentation](https://www.sphinx-doc.org/)
- Review existing documentation files for examples
- Ask questions in project discussions