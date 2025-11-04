# Release Guide

This guide describes how to create and publish new releases of the gecko-iot-client package.

## Prerequisites

Before creating a release, ensure:

1. All tests are passing on the `develop` branch
2. Documentation is up to date
3. `CHANGELOG.md` has been updated with the new version
4. Version number in `pyproject.toml` has been bumped
5. All changes have been merged to `develop` branch

## Repository Secrets Configuration

For automated PyPI publishing to work, the following repository secrets must be configured in GitHub:

### For PyPI Publishing (Production)
- `PYPI_API_TOKEN` - PyPI API token for publishing to production PyPI

### For TestPyPI Publishing (Testing)
- `TEST_PYPI_API_TOKEN` - TestPyPI API token for testing releases

### Setting up PyPI API Tokens

1. **For PyPI (production)**:
   - Go to [https://pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)
   - Create a new API token with scope for the `gecko-iot-client` project
   - Copy the token and add it as `PYPI_API_TOKEN` in GitHub repository secrets

2. **For TestPyPI (testing)**:
   - Go to [https://test.pypi.org/manage/account/token/](https://test.pypi.org/manage/account/token/)
   - Create a new API token with scope for the `gecko-iot-client` project
   - Copy the token and add it as `TEST_PYPI_API_TOKEN` in GitHub repository secrets

## Release Process

### 1. Prepare the Release

1. Create a new branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b release/v0.1.0
   ```

2. Update the version in `gecko_iot_client/pyproject.toml`:
   ```toml
   [project]
   name = "gecko-iot-client"
   version = "0.1.0"  # Update this version
   ```

3. Update `CHANGELOG.md`:
   - Move items from `[Unreleased]` to the new version section
   - Add the release date
   - Create a new empty `[Unreleased]` section

4. Commit and push the changes:
   ```bash
   git add .
   git commit -m "Bump version to 0.1.0"
   git push origin release/v0.1.0
   ```

5. Create a pull request to merge the release branch to `develop`

### 2. Create the GitHub Release

1. Go to the [GitHub Releases page](https://github.com/geckoal/gecko-iot-client/releases)

2. Click "Create a new release"

3. Configure the release:
   - **Tag version**: `v0.1.0` (create new tag)
   - **Target**: `develop` (important!)
   - **Release title**: `v0.1.0 - Release Name`
   - **Description**: Copy the relevant section from CHANGELOG.md

4. Click "Publish release"

### 3. Automated Publishing

Once the release is published from the `develop` branch, the CI/CD pipeline will automatically:

1. **Build the package** - Create source distribution and wheel
2. **Test the build** - Install and test the built package
3. **Publish to PyPI** - Upload to the PyPI registry

The workflow will only publish to PyPI for releases created from the `develop` branch.

### 4. Testing Releases

For testing purposes, you can also publish to TestPyPI by creating version tags:

1. Create and push a version tag:
   ```bash
   git tag v0.1.0-rc1
   git push origin v0.1.0-rc1
   ```

2. This will trigger the TestPyPI publishing workflow

## Workflow Triggers

The publishing workflow (`publish.yml`) is triggered by:

- **PyPI Publishing**: GitHub releases created from the `develop` branch
- **TestPyPI Publishing**: Version tags pushed to the repository (e.g., `v0.1.0-rc1`)

## Monitoring

After publishing:

1. Check the [GitHub Actions page](https://github.com/geckoal/gecko-iot-client/actions) for workflow status
2. Verify the package appears on [PyPI](https://pypi.org/project/gecko-iot-client/)
3. Test installation: `pip install gecko-iot-client==0.1.0`

## Troubleshooting

### Common Issues

1. **Build fails**: Check that `pyproject.toml` is properly configured
2. **PyPI upload fails**: Verify API tokens are correctly set in repository secrets
3. **Version conflicts**: Ensure the version number hasn't been used before
4. **Missing files**: Check that all necessary files are included in the package

### Rollback

If a release needs to be rolled back:

1. Remove the problematic version from PyPI (if possible)
2. Create a new patch release with fixes
3. Update documentation to reflect the issue

## Version Numbering

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

Examples:
- `0.1.0` - Initial release
- `0.1.1` - Bug fix
- `0.2.0` - New features
- `1.0.0` - First stable release