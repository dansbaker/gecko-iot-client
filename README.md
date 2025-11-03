# Gecko IoT Client

A Python client library for Gecko IoT devices with AWS IoT integration.

## Repository Structure

```
├── .github/workflows/          # GitHub Actions workflows (moved from python/gecko_iot_client/.github/)
│   ├── docs.yml               # Documentation build and deployment
│   └── test.yml               # Test suite and code quality checks
├── gecko_iot_client/   # Main Python package
│   ├── src/                   # Source code
│   ├── tests/                 # Test suite
│   ├── docs/                  # Sphinx documentation
│   └── examples/              # Usage examples
```

## Documentation

The documentation is built using Sphinx and automatically deployed to GitHub Pages when changes are pushed to the `main` branch.

- **Live documentation**: Available at your GitHub Pages URL
- **Local development**: See `gecko_iot_client/docs/README.md`

## Development

See the documentation in `gecko_iot_client/` for development setup and contribution guidelines.

## GitHub Actions

### Documentation Workflow (`docs.yml`)
- **Triggers**: Push to `main`/`develop`, Pull requests to `main`
- **Features**:
  - Builds Sphinx documentation with Python 3.13
  - Deploys to GitHub Pages on main branch pushes
  - Provides documentation previews for pull requests
  - Includes comprehensive error checking and debugging output

### Test Workflow (`test.yml`)
- **Triggers**: Push to `main`/`develop`, Pull requests to `main`
- **Features**:
  - Runs pytest with coverage reporting
  - Code quality checks (black, isort, flake8)
  - Uploads coverage to Codecov

## Setup Instructions

1. **Enable GitHub Pages**: Go to repository Settings → Pages → Source: "GitHub Actions"
2. **Add Codecov Token** (optional): Add `CODECOV_TOKEN` to repository secrets for coverage reporting

## Migration Notes

The workflows have been moved from `gecko_iot_client/.github/workflows/` to the repository root `.github/workflows/` and updated to:

1. Handle the new directory structure
2. Use latest GitHub Actions versions
3. Improve error handling and debugging
4. Add proper GitHub Pages integration
5. Include caching for faster builds