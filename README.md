# DOMjudge Simple Signup

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://domjudge-simple-signup.streamlitapp.com/)

- Python: 3.13
- Runtime & Package Management: [mise](https://mise.jdx.dev/) + [uv](https://docs.astral.sh/uv/)

## Dependency version

Signup hardening depends on `domjudge-tool-cli` 0.6.0 (published on PyPI):

| Capability | On 0.5.0 | On 0.6.0 |
|---|---|---|
| Server-reported minimum password length | Not read; the form shows the configured/version-derived value | The form advertises the server's own value and enforces it |
| Rejection detail on a failed password write | Only a generic message | DOMjudge's own validation message is shown |
| Removing an affiliation created for a failed signup | Impossible; reported to the applicant as an orphan | Rolled back |

The app detects each capability at runtime, so 0.5.0 still runs: it enforces the
configured value and reports anything it cannot clean up instead of claiming
success. `uv.lock` pins 0.6.0, so a normal install gets all three.

`MIN_PASSWORD_LENGTH` may raise the floor above the server's value but never
lower it, because the server rejects shorter passwords regardless and a lower
advertised value would turn a submission the form called valid into a failure
after the team and user were created.


## Demo

- [Deploy on Streamlit Cloud](https://domjudge-simple-signup.streamlitapp.com)

## Quick Start

### 1. Prerequisites

Install `mise`:

```shell
$ brew install mise
```

### 2. Install Tools and Dependencies

```shell
# Install Python 3.13.15 and uv 0.12.12 via mise
$ mise install

# Install project dependencies locked by uv.lock
$ mise run install
```

### 3. Environment Configuration

Copy the example environment configuration to `src/core/.env`:

```shell
$ cp src/core/.env.example src/core/.env
```

Fill in the required settings in `src/core/.env` (never commit this file):

#### Required Keys
- `HOST`: DOMjudge server URL (e.g. `https://domjudge.example.com`)
- `USERNAME`: API user username (e.g. `admin`, `api_writer`)
- `PASSWORD`: API user password
- `VERSION`: DOMjudge version (e.g. `7.3.2`, `8.1.3`)
- `API_VERSION`: DOMjudge API version (e.g. `v4`)

#### Optional Keys & Defaults
- `DISABLE_SSL`: `False` (set to `True` for self-signed certificates)
- `TIMEOUT`: `60.0` (request timeout in seconds)
- `MAX_CONNECTIONS`: Connection pool limit (default `None`)
- `MAX_KEEPALIVE_CONNECTIONS`: Keepalive connection limit (default `None`)
- `CATEGORY_ID`: Default category ID for user registration
- `AFFILIATION_ID`: Default affiliation ID
- `AFFILIATION_COUNTRY`: `TWN`
- `USER_ROLES`: Comma-separated list of role IDs (default empty)
- `MIN_PASSWORD_LENGTH`: Minimum password length enforced by DOMjudge, measured in UTF-8 bytes because DOMjudge validates with PHP `strlen()` (default `10` for 8.x, `0` for 7.x). One ASCII character is 1 byte, one common CJK character is usually 3. Use it to require something stricter than the server; a lower value cannot take effect because the server's own minimum still applies.
- `GOOGLEFORM_ID`: Google Form ID for logging signups (default `None`)

### 4. Quality Checks and Running

```shell
# Run format checking, linting, type checks, and test suite in parallel
$ mise run check

# Format codebase
$ mise run format

# Start local Streamlit app
$ mise run run
```

## Deployment on Streamlit Community Cloud

Streamlit Community Cloud automatically recognizes root `uv.lock`. When deploying or updating the app:
1. In repository settings / Advanced settings, ensure **Python 3.13** is selected.
2. Provide secrets in the Community Cloud UI corresponding to the required `.env` keys above.
