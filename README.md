# PyNinja
Lightweight OS-agnostic service monitoring API

![Python][label-pyversion]

**Platform Supported**

![Platform][label-platform]

**Deployments**

[![pages][label-actions-pages]][gha_pages]
[![pypi][label-actions-pypi]][gha_pypi]
[![markdown][label-actions-markdown]][gha_md_valid]

[![Pypi][label-pypi]][pypi]
[![Pypi-format][label-pypi-format]][pypi-files]
[![Pypi-status][label-pypi-status]][pypi]

## Kick off

**Recommendations**

- Install `python` [3.11] or above
- Use a dedicated [virtual environment]

**Install PyNinja**
```shell
python -m pip install pyninja
```

**Initiate - IDE**
```python
import pyninja


if __name__ == '__main__':
    pyninja.start()
```

**Initiate - CLI**
```shell
pyninja start
```

> Use `pyninja --help` for usage instructions.

## Environment Variables

<details>
<summary><strong>Sourcing environment variables from an env file</strong></summary>

> _By default, `PyNinja` will look for a `.env` file in the current working directory._
</details>

**Basic API**
- **APIKEY** - API Key for authentication.
- **SWAGGER_UI_PARAMETERS** - Dictionary of parameters to be included in the Swagger UI.
- **NINJA_HOST** - Hostname for the API server.
- **NINJA_PORT** - Port number for the API server.

**Functional improvements**
- **RATE_LIMIT** - List of dictionaries with `max_requests` and `seconds` to apply as rate limit.
- **LOG_CONFIG** - Logging configuration file path.

**Remote execution and FileIO**
- **REMOTE_EXECUTION** - Boolean flag to enable remote execution.
- **API_SECRET** - Secret access key for running commands on server remotely.
- **DATABASE** - FilePath to store the auth database that handles the authentication errors.

⚠️ **Warning: Enabling remote execution carries significant security risks.**
To enhance security, it is mandatory to use multifactor authentication (MFA) token.

**Multifactor Authentication (MFA)**
- **MFA_TIMEOUT** - Timeout duration for MFA in seconds.
- **MFA_RESEND_DELAY** - Resend duration for MFA in seconds. _Cool off period before a new MFA can be requested._

- **Email**
    - **GMAIL_USER** - Gmail username for MFA.
    - **GMAIL_PASS** - Gmail password for MFA.
    - **RECIPIENT** - Recipient email address for MFA. Defaults to **GMAIL_USER**
- **Ntfy**
    - **NTFY_URL** - Ntfy server URL.
    - **NTFY_TOPIC** - Subscribed ntfy topic.
    > Include **NTFY_USERNAME** and **NTFY_PASSWORD** if the topic is protected.
- **Telegram**
    - **TELEGRAM_TOKEN** - Telegram bot token.
    - **TELEGRAM_CHAT_ID** - Telegram chat ID to send MFA.
- **Authenticator**
    - **AUTHENTICATOR_TOKEN** - MFA Authenticator token.

    To generate a QR code for any authenticator application:

    **Code**
    ```python
    import pyninja
    pyninja.otp.generate_qr(show_qr=True)
    ```

    **CLI**
    ```shell
    pyninja --mfa
    ```

    > 📓 Generating an authenticator token using PyNinja is the simplest ways to set up MFA authentication. However, the trade-off is that the token is short-lived. Each MFA passcode is only valid for 30 seconds.

**Monitoring UI**
- **MONITOR_USERNAME** - Username to authenticate the monitoring page.
- **MONITOR_PASSWORD** - Password to authenticate the monitoring page.
- **MONITOR_SESSION** - Session timeout for the monitoring page.
- **DISK_REPORT** - Boolean flag to enable disk report feature using [PyUdisk].
- **MAX_CONNECTIONS** - Maximum number of monitoring sessions allowed in parallel.
- **PROCESSES** - List of process names to include in the monitor page.
- **SERVICES** - List of service names to include in the monitor page.
- **SERVICE_LIB** - Library path to retrieve service info.
- **SMART_LIB** - Library path for S.M.A.R.T metrics using [PyUdisk].
- **GPU_LIB** - Library path to retrieve GPU names using [PyArchitecture].
- **DISK_LIB** - Library path to retrieve disk info using [PyArchitecture].
- **PROCESSOR_LIB** - Library path to retrieve processor name using [PyArchitecture].

**macOS Specific Binaries**
- **OSASCRIPT** - Path to the `osascript` binary for macOS. Defaults to `/usr/bin/osascript`
- **MDLS** - Path to the `mdls` binary for macOS. Defaults to `/usr/bin/mdls`
- **OPEN** - Path to the `open` binary for macOS. Defaults to `/usr/bin/open`

> 📓 Certain environment variables like `SERVICES` and `PROCESSS` are case-sensitive

> Refer [samples] directory for examples.

## Coding Standards
Docstring format: [`Google`][google-docs] <br>
Styling conventions: [`PEP 8`][pep8] and [`isort`][isort]

## [Release Notes][release-notes]
**Requirement**
```shell
python -m pip install gitverse
```

**Usage**
```shell
gitverse-release reverse -f release_notes.rst -t 'Release Notes'
```

## Linting
`pre-commit` will ensure linting, run pytest, generate runbook & release notes, and validate hyperlinks in ALL
markdown files (including Wiki pages)

**Requirement**
```shell
python -m pip install sphinx==5.1.1 pre-commit recommonmark
```

**Usage**
```shell
pre-commit run --all-files
```

## Pypi Package
[![pypi-module][label-pypi-package]][pypi-repo]

[https://pypi.org/project/PyNinja/][pypi]

## Runbook
[![made-with-sphinx-doc][label-sphinx-doc]][sphinx]

[https://thevickypedia.github.io/PyNinja/][runbook]

## License & copyright

&copy; Vignesh Rao

Licensed under the [MIT License][license]

[//]: # (Labels)

[label-actions-markdown]: https://github.com/thevickypedia/PyNinja/actions/workflows/markdown.yaml/badge.svg
[label-pypi-package]: https://img.shields.io/badge/Pypi%20Package-pyninja-blue?style=for-the-badge&logo=Python
[label-sphinx-doc]: https://img.shields.io/badge/Made%20with-Sphinx-blue?style=for-the-badge&logo=Sphinx
[label-pyversion]: https://img.shields.io/badge/python-3.11%20%7C%203.12-blue
[label-platform]: https://img.shields.io/badge/Platform-Linux|macOS|Windows-1f425f.svg
[label-actions-pages]: https://github.com/thevickypedia/PyNinja/actions/workflows/pages/pages-build-deployment/badge.svg
[label-actions-pypi]: https://github.com/thevickypedia/PyNinja/actions/workflows/python-publish.yaml/badge.svg
[label-pypi]: https://img.shields.io/pypi/v/PyNinja
[label-pypi-format]: https://img.shields.io/pypi/format/PyNinja
[label-pypi-status]: https://img.shields.io/pypi/status/PyNinja

[3.11]: https://docs.python.org/3/whatsnew/3.11.html
[virtual environment]: https://docs.python.org/3/tutorial/venv.html
[release-notes]: https://github.com/thevickypedia/PyNinja/blob/main/release_notes.rst
[gha_pages]: https://github.com/thevickypedia/PyNinja/actions/workflows/pages/pages-build-deployment
[gha_pypi]: https://github.com/thevickypedia/PyNinja/actions/workflows/python-publish.yaml
[gha_md_valid]: https://github.com/thevickypedia/PyNinja/actions/workflows/markdown.yaml
[google-docs]: https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
[pep8]: https://www.python.org/dev/peps/pep-0008/
[isort]: https://pycqa.github.io/isort/
[sphinx]: https://www.sphinx-doc.org/en/master/man/sphinx-autogen.html
[pypi]: https://pypi.org/project/PyNinja
[pypi-files]: https://pypi.org/project/PyNinja/#files
[pypi-repo]: https://packaging.python.org/tutorials/packaging-projects/
[license]: https://github.com/thevickypedia/PyNinja/blob/main/LICENSE
[runbook]: https://thevickypedia.github.io/PyNinja/
[samples]: https://github.com/thevickypedia/PyNinja/tree/main/samples
[PyUdisk]: https://github.com/thevickypedia/PyUdisk
[PyArchitecture]: https://github.com/thevickypedia/PyArchitecture
