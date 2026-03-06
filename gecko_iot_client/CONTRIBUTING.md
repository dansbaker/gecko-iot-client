# Contributing to Gecko IoT Client

## Development Setup

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Set Up Pre-commit Hooks

Pre-commit hooks automatically format your code with Black and isort before each commit:

```bash
pre-commit install
```

To manually run pre-commit on all files:

```bash
pre-commit run --all-files
```

### Code Formatting

This project uses:
- **Black** for code formatting
- **isort** for import sorting (with Black profile)
- **flake8** for linting

Pre-commit hooks will automatically format your code, but you can also run manually:

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

### Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=gecko_iot_client --cov-report=html
```
