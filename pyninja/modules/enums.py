try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        """Custom StrEnum object for python3.10"""


class OperatingSystem(StrEnum):
    """Operating system names.

    >>> OperatingSystem

    """

    linux: str = "linux"
    darwin: str = "darwin"
    windows: str = "windows"


class APIEndpoints(StrEnum):
    """API endpoints for all the routes.

    >>> APIEndpoints

    """

    root: str = "/"
    docs: str = "/docs"
    redoc: str = "/redoc"
    health: str = "/health"

    get_file: str = "/get-file"
    put_file: str = "/put-file"

    get_processor: str = "/get-processor"

    service_usage: str = "/service-usage"
    process_usage: str = "/process-usage"

    process_status: str = "/process-status"
    service_status: str = "/service-status"

    monitor: str = "/monitor"
    ws_system: str = "/ws/system"
    run_command: str = "/run-command"

    get_disk: str = "/get-disk"
    get_memory: str = "/get-memory"
    get_all_disks: str = "/get-all-disks"

    docker_image: str = "/docker-image"
    docker_stats: str = "/docker-stats"
    docker_volume: str = "/docker-volume"
    docker_container: str = "/docker-container"

    get_ip: str = "/get-ip"
    get_cpu: str = "/get-cpu"
    list_files: str = "/list-files"
    get_cpu_load: str = "/get-cpu-load"

    login: str = "/login"
    logout: str = "/logout"
    error: str = "/error"


class Cookies(StrEnum):
    """Cookie names for the application.

    >>> Cookies

    """

    drive: str = "drive"
    monitor: str = "monitor"
    session_token: str = "session_token"


class Templates(StrEnum):
    """HTML template filenames.

    >>> Templates

    """

    main: str = "main.html"
    index: str = "index.html"
    logout: str = "logout.html"
    session: str = "session.html"
    disk_report: str = "disk_report.html"
    unauthorized: str = "unauthorized.html"
