from enum import StrEnum


class OperatingSystem(StrEnum):
    """Operating system names.

    >>> OperatingSystem

    """

    linux = "linux"
    darwin = "darwin"
    windows = "windows"


class APIEndpoints(StrEnum):
    """API endpoints for all the routes.

    >>> APIEndpoints

    """

    root = "/"
    docs = "/docs"
    redoc = "/redoc"
    health = "/health"
    version = "/version"

    get_file = "/get-file"
    put_file = "/put-file"
    get_large_file = "/get-large-file"
    put_large_file = "/put-large-file"
    delete_content = "/delete-content"

    get_processor = "/get-processor"

    get_all_services = "/get-all-services"
    get_service_status = "/get-service-status"
    get_service_usage = "/get-service-usage"
    stop_service = "/stop-service"
    start_service = "/start-service"
    restart_service = "/restart-service"

    # macOS specific endpoints
    get_all_apps = "/get-all-apps"
    start_app = "/start-app"
    stop_app = "/stop-app"
    restart_app = "/restart-app"

    get_process_status = "/get-process-status"
    get_process_usage = "/get-process-usage"

    observability = "/observability"
    monitor = "/monitor"
    ws_system = "/ws/system"
    run_command = "/run-command"
    run_ui = "/run-ui"

    get_memory = "/get-memory"
    get_all_disks = "/get-all-disks"
    get_disk_utilization = "/get-disk-utilization"

    get_docker_images = "/get-docker-images"
    get_docker_stats = "/get-docker-stats"
    get_docker_volumes = "/get-docker-volumes"
    get_docker_containers = "/get-docker-containers"

    get_certificates = "/get-certificates"
    renew_certificate = "/renew-certificate"

    stop_docker_container = "/stop-docker-container"
    start_docker_container = "/start-docker-container"

    get_ip = "/get-ip"
    get_cpu = "/get-cpu"
    list_files = "/list-files"
    get_cpu_load = "/get-cpu-load"

    login = "/login"
    logout = "/logout"
    error = "/error"
    get_mfa = "/get-mfa"
    delete_mfa = "/delete-mfa"


class Cookies(StrEnum):
    """Cookie names for the application.

    >>> Cookies

    """

    drive = "drive"
    monitor = "monitor"
    session_token = "session_token"


class Templates(StrEnum):
    """HTML template filenames.

    >>> Templates

    """

    # Monitoring templates
    main = "main.html"
    index = "index.html"
    logout = "logout.html"
    session = "session.html"
    unauthorized = "unauthorized.html"
    disk_report_linux = "disk_report_linux.html"
    disk_report_darwin = "disk_report_darwin.html"

    # API templates
    run_ui = "run_ui.html"
    swagger_ui = "swaggerUI.js"
    mfa_template = "mfa_template.html"


class APIRouteType(StrEnum):
    """Types of API routes available.

    >>> APIRouteType

    """

    get = "get"
    post = "post"
    monitor = "monitor"


class TableName(StrEnum):
    """Table names.

    >>> TableName

    """

    auth_errors = "auth_errors"
    mfa_token = "mfa_token"


class MFAOptions(StrEnum):
    """Authentication mechanism for multifactor tokens.

    >>> MFAOptions

    """

    email = "email"
    ntfy = "ntfy"
    telegram = "telegram"
