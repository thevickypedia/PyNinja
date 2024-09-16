Release Notes
=============

v0.0.9 (09/16/2024)
-------------------
- Includes disks information in the monitoring page
- Restructured monitoring page with dedicated div container for each category of system information
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.8...v0.0.9

v0.0.8 (09/10/2024)
-------------------
- Includes an option to get CPU load average via API calls and monitoring page UI
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.7...v0.0.8

v0.0.7 (09/09/2024)
-------------------
- Includes a new feature to monitor disk utilization and get process name
- Bug fix on uncaught errors during server shutdown
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.6...v0.0.7

v0.0.6 (09/09/2024)
-------------------
- Includes an option to limit maximum number of WebSocket sessions
- Includes a logout functionality for the monitoring page
- Uses bearer auth for the monitoring page
- Redefines progress bars with newer color schemes
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.5...v0.0.6

v0.0.6a (09/07/2024)
--------------------
- Includes an option to limit max number of concurrent sessions for monitoring page
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.5...v0.0.6a

v0.0.5 (09/07/2024)
-------------------
- Packs an entirely new UI and authentication mechanism for monitoring tool
- Includes speed, stability and security improvements for monitoring feature
- Adds night mode option for monitoring UI
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.4...v0.0.5

v0.0.4 (09/06/2024)
-------------------
- Includes an option to monitor system resources via `WebSockets`
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.3...v0.0.4

v0.0.3 (08/16/2024)
-------------------
- Allows env vars to be sourced from both ``env_file`` and ``kwargs``
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.2...v0.0.3

v0.0.2 (08/16/2024)
-------------------
- Includes added support for custom log configuration
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.1...v0.0.2

v0.0.1 (08/11/2024)
-------------------
- Includes a process monitor and remote command execution functionality
- Security improvements including brute force protection and rate limiting
- Accepts ``JSON`` and ``YAML`` files for env config
- Supports custom worker count for ``uvicorn`` server
- Allows custom logging using ``logging.ini``
- Includes an option to set the ``apikey`` via commandline
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.0...v0.0.1

v0.0.0 (08/11/2024)
-------------------
- Release first stable version

0.0.0-a (08/10/2024)
--------------------
- Set project name to `PyNinja`
