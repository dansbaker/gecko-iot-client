# Publishing `gecko-iot-client-community` to PyPI

Releases publish automatically via GitHub Actions using PyPI's
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC), so
no long-lived API tokens are stored in this repo.

## One-time setup

1. **Create a PyPI account** at <https://pypi.org/account/register/> if you
   don't have one. Same email as your GitHub account is fine.

2. **Register the pending publisher** at
   <https://pypi.org/manage/account/publishing/>. Fill in:

   | Field | Value |
   |---|---|
   | PyPI project name | `gecko-iot-client-community` |
   | Owner | `dansbaker` |
   | Repository name | `gecko-iot-client` |
   | Workflow name | `publish.yml` |
   | Environment name | *(leave blank)* |

   Click **Add**. PyPI will list the project as "pending" — the first
   successful publish creates it for real.

3. *(Optional)* If you want tag-triggered uploads to **TestPyPI** as well,
   repeat at <https://test.pypi.org/manage/account/publishing/>.

## Each release

1. Bump the static version in `gecko_iot_client/pyproject.toml` on a PR;
   merge to `develop`.
2. On <https://github.com/dansbaker/gecko-iot-client/releases/new> create a
   new release:
   - **Target**: `develop`
   - **Tag**: `v<version>` (e.g. `v0.4.0`) — let the UI create the tag.
   - **Title**: `v<version>`
   - **Notes**: short summary, or use the "Generate release notes" button.
3. Click **Publish release**. The `Publish to PyPI` workflow runs and
   uploads the sdist + wheel.

## What ends up where

- PyPI page: <https://pypi.org/project/gecko-iot-client-community/>
- HA integration pin (in `manifest.json`):
  `"gecko-iot-client-community==<version>"`
- Import name (consumer code, unchanged): `gecko_iot_client`
