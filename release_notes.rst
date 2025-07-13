Release Notes
=============

v4.1.1 (07/13/2025)
-------------------
- Bug fix on macOS application name filter to improve accuracy and avoid false positives
- Returns full list of applications for ``start``, ``stop`` and ``restart`` operations when given name doesn't match
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v4.1.0...v4.1.1

v4.1.0 (07/12/2025)
-------------------
- Includes new API handlers to get, start, stop, and restart macOS applications.
- Create a OS agnostic solution for existing service restart functionality.
- Includes more logging information for failed subprocess executions.
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v4.0.0...v4.1.0

v4.0.0 (07/12/2025)
-------------------
- Security improvements including MFA using gmail-connector
- Includes MFA resend interval to prevent spamming emails
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v3.0.0...v4.0.0

v3.0.0 (07/12/2025)
-------------------
- Includes new API routes to upload and download large files in chunks.
- Includes support for automatic unzip allowing directory uploads as zip files.
- Dev requirements can now be installed along with the package.
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v2.0.1...v3.0.0

v2.0.1 (07/04/2025)
-------------------
- Includes support for timed cache functionality in async mode
- Bug fix for disk report on login page
- Includes footer notes for tables in the UI
- Logs number of connections made during a WS session
- Includes python version in SwaggerUI
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v2.0.0...v2.0.1

v2.0.0 (01/06/2025)
-------------------
- Redefined SwaggerUI with options to further customize it
- Includes new API endpoints to start, stop and list all services and docker containers
- Includes full support for `PyUdisk` by default (without `extra` installation)
- Removed support for python3.10 and lower
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v1.2.0...v2.0.0

v1.2.0 (01/03/2025)
-------------------
- Includes redesigned architecture information retrieval for GPU, CPU, and disks
- Restructured `PyUdisk` metrics compatible with `macOS`
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v1.1.0...v1.2.0

v1.1.0 (12/28/2024)
-------------------
- Includes security improvements
- No longer requires apikey for hosting a monitoring page
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v1.0.0...v1.1.0

v1.0.0 (11/30/2024)
-------------------
- Includes a new feature to get ``S.M.A.R.T`` disk metrics (for Linux OS)
- Creates a new column dedicated for disks' usage PIE charts
- Fully restructured disk usage information which accounts for multiple drives, yet ignoring partitions.
- Includes general improvements across the app for better performance and code readability.
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.1.4...v1.0.0

v0.1.4 (11/08/2024)
-------------------
- Includes a new feature to handle IO (list, upload, and download)
- Bug fix on monitor page blocked due to missing docker containers
- Includes an option to host monitor page without authentication
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.1.3...v0.1.4

v0.1.3 (10/05/2024)
-------------------
- Include open files metric to service/process monitoring
- Includes process/service usage metrics served via API endpoints
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.1.1...v0.1.3

v0.1.1 (09/29/2024)
-------------------
- Include services/processes metrics to monitoring page
- Filter PIDs from docker stats
- Remove overall code redundancies in the UI
- Convert collapsible sections of top level information in tables
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.1.0...v0.1.1

v0.1.1-dev (09/29/2024)
-----------------------
- Relese `dev` version for `0.1.1`
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.1.0...v0.1.1-dev

v0.1.0 (09/29/2024)
-------------------
- Include `docker stats` in monitoring page
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.9...v0.1.0

v0.1.0-alpha (09/16/2024)
-------------------------
- Alpha version for docker stats
- **Full Changelog**: https://github.com/thevickypedia/PyNinja/compare/v0.0.9...v0.1.0-alpha

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
