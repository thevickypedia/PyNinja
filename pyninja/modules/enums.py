from enum import StrEnum


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
    get_large_file: str = "/get-large-file"
    put_large_file: str = "/put-large-file"
    delete_content: str = "/delete-content"

    get_processor: str = "/get-processor"

    get_all_services: str = "/get-all-services"
    get_service_status: str = "/get-service-status"
    get_service_usage: str = "/get-service-usage"
    stop_service: str = "/stop-service"
    start_service: str = "/start-service"

    get_process_status: str = "/get-process-status"
    get_process_usage: str = "/get-process-usage"

    monitor: str = "/monitor"
    ws_system: str = "/ws/system"
    run_command: str = "/run-command"

    get_memory: str = "/get-memory"
    get_all_disks: str = "/get-all-disks"
    get_disk_utilization: str = "/get-disk-utilization"

    get_docker_images: str = "/get-docker-images"
    get_docker_stats: str = "/get-docker-stats"
    get_docker_volumes: str = "/get-docker-volumes"
    get_docker_containers: str = "/get-docker-containers"

    stop_docker_container: str = "/stop-docker-container"
    start_docker_container: str = "/start-docker-container"

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
    unauthorized: str = "unauthorized.html"
    disk_report_linux: str = "disk_report_linux.html"
    disk_report_darwin: str = "disk_report_darwin.html"


class APIRouteType(StrEnum):
    """Types of API routes available.

    >>> APIRouteType

    """

    get: str = "get"
    post: str = "post"
    monitor: str = "monitor"
