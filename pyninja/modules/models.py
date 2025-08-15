import os
import pathlib
import platform
import random
import re
import shutil
import socket
import sqlite3
import string
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Timer
from typing import Any, Callable, Dict, List, Set, Tuple

from fastapi.routing import APIRoute, APIWebSocketRoute
from pyarchitecture.config import default_cpu_lib, default_disk_lib, default_gpu_lib
from pydantic import BaseModel, EmailStr, Field, FilePath, PositiveInt, field_validator
from pydantic_settings import BaseSettings

from pyninja.modules import enums, exceptions

MINIMUM_CPU_UPDATE_INTERVAL = 1
# Use a ThreadPoolExecutor to run blocking functions in separate threads
EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count())
OPERATING_SYSTEM = platform.system().lower()
if OPERATING_SYSTEM not in (
    enums.OperatingSystem.linux,
    enums.OperatingSystem.darwin,
    enums.OperatingSystem.windows,
):
    exceptions.raise_os_error(OPERATING_SYSTEM)


def keygen(min_length: int = 32) -> str:
    """Key generator to create a unique key with a minimum length.

    Args:
        min_length: Minimum length of the generated key. Default is 32.

    Returns:
        str:
        Returns a unique key that contains at least one digit, one uppercase letter,
    """
    # Ensure at least one of each required character
    required_chars = [
        random.choice(string.digits),
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
    ]

    # Start with a UUID to ensure uniqueness
    unique_part = uuid.uuid4().hex  # 32 lowercase hex chars

    # Add some randomness to exceed the min length if needed
    remaining_length = max(min_length - len(unique_part) - len(required_chars), 0)
    filler = "".join(
        random.choices(string.ascii_letters + string.digits, k=remaining_length)
    )
    safe_chars = ["-", "_", ".", "~"]

    # Combine all parts and shuffle
    token_chars = list(
        unique_part + filler + "".join(required_chars) + random.choice(safe_chars)
    )
    random.shuffle(token_chars)

    return "".join(token_chars)


def complexity_checker(key: str, value: str, min_length: int) -> None:
    """Verifies the strength of a secret.

    See Also:
        A secret is considered strong if it at least has:

        - 32 characters
        - 1 digit
        - 1 symbol
        - 1 uppercase letter
        - 1 lowercase letter

    Raises:
        AssertionError: When at least 1 of the above conditions fail to match.
    """
    assert value.strip(), f"{key!r} CANNOT be an empty space!!"

    # calculates the length
    assert (
        len(value) >= min_length
    ), f"Minimum {key!r} length is {min_length}, received {len(value)}"

    # searches for digits
    assert re.search(r"\d", value), f"{key!r} must include an integer"

    # searches for uppercase
    assert re.search(
        r"[A-Z]", value
    ), f"{key!r} must include at least one uppercase letter"

    # searches for lowercase
    assert re.search(
        r"[a-z]", value
    ), f"{key!r} must include at least one lowercase letter"

    # searches for symbols
    assert re.search(
        r"[ !@#$%&'()*+,-./[\\\]^_`{|}~" + r'"]', value
    ), f"{key!r} must contain at least one special character"


class RoutingHandler(BaseModel):
    """Routing handler to update the API routes to the server.

    >>> RoutingHandler

    """

    type: enums.APIRouteType
    routes: List[APIRoute | APIWebSocketRoute]
    enabled: bool = False

    class Config:
        """Configuration for routing handler."""

        arbitrary_types_allowed = True


class CertificateStatus(BaseModel):
    """Object to load certificate status with a status code and description.

    >>> ServiceStatus

    """

    status_code: int
    description: str
    certificates: List[Dict[str, Any]] = Field(default_factory=list)


class ServiceStatus(BaseModel):
    """Object to load service status with a status code and description.

    >>> ServiceStatus

    """

    status_code: int
    description: str
    service_name: str


class AppStatus(BaseModel):
    """Object to load the application status with a status code and description.

    >>> AppStatus

    """

    app_name: str
    status_code: int
    description: str
    app_path: str | None = None


class Architecture(BaseModel):
    """Object to store the architecture of the system.

    >>> Architecture

    """

    cpu: str = Field(default_factory=str)
    gpu: List[Dict[str, str]] = Field(default_factory=list)
    disks: List[Dict[str, Any]] = Field(default_factory=list)


class Session(BaseModel):
    """Object to store session information.

    >>> Session

    """

    auth_counter: Dict[str, int] = Field(default_factory=dict)
    forbid: Set[str] = Field(default_factory=set)

    info: Dict[str, str] = Field(default_factory=dict)
    rps: Dict[str, int] = Field(default_factory=dict)
    allowed_origins: Set[str] = Field(default_factory=set)


session = Session()


class WSSession(BaseModel):
    """Object to store websocket session information.

    >>> WSSession

    """

    invalid: Dict[str, int] = Field(default_factory=dict)
    client_auth: Dict[str, Dict[str, int]] = Field(default_factory=dict)


ws_session = WSSession()


class MFAToken(BaseModel):
    """Object to store the MFA token.

    >>> MFAToken

    """

    token: str | None = None
    timers: List[Timer] = Field(default_factory=list)

    class Config:
        """Configuration for MFAToken object."""

        arbitrary_types_allowed = True


mfa = MFAToken()


class RateLimit(BaseModel):
    """Object to store the rate limit settings.

    >>> RateLimit

    """

    max_requests: PositiveInt
    seconds: PositiveInt


def default_service_lib() -> FilePath:
    """Get default service library filepath for the host operating system.

    Returns:
        FilePath:
        Returns the ``FilePath`` referencing the appropriate library.
    """
    return dict(
        linux=shutil.which("systemctl") or "/usr/bin/systemctl",
        darwin=shutil.which("launchctl") or "/bin/launchctl",
        windows=shutil.which("sc") or "C:\\Windows\\System32\\sc.exe",
    )


def retrieve_library_path(func: Callable) -> FilePath:
    """Retrieves the library path from the mapping created for each operating system.

    Args:
        func: Function to call to get the mapping.

    Returns:
        FilePath:
        Returns the library path as a ``FilePath`` object.
    """
    try:
        return FilePath(func()[OPERATING_SYSTEM])
    except KeyError:
        # This shouldn't happen programmatically, but just in case
        exceptions.raise_os_error(OPERATING_SYSTEM)


def get_certbot_path() -> FilePath | None:
    """Get the certbot path if installed.

    Returns:
        FilePath:
        Returns the ``FilePath`` referencing the certbot binary.
    """
    if certbot_path := shutil.which("certbot"):
        return FilePath(certbot_path)
    common_paths = [
        "/usr/bin/certbot",  # Linux apt
        "/usr/local/bin/certbot",  # macOS brew
        "/snap/bin/certbot",  # Linux snap
    ]
    for path in common_paths:
        if os.path.isfile(path):
            return FilePath(path)
    return None


class EnvConfig(BaseSettings):
    """Object to load environment variables.

    >>> EnvConfig

    """

    # Basic API
    apikey: str | None = None
    swagger_ui_parameters: Dict[str, Any] = Field(
        {
            "deepLinking": True,
            "persistAuthorization": False,
            "displayRequestDuration": True,
            "docExpansion": "list",
        }
    )
    ninja_host: str = socket.gethostbyname("localhost") or "0.0.0.0"
    ninja_port: PositiveInt = 8000
    host_password: str | None = None

    # Functional improvements
    rate_limit: RateLimit | List[RateLimit] = Field(default_factory=list)
    log_config: Dict[str, Any] | FilePath | None = None

    # Remote exec and fileIO
    remote_execution: bool = False
    api_secret: str | None = None
    database: str = Field("auth.db", pattern=".*.db$")

    # Multifactor authentication
    gmail_user: EmailStr | None = None
    gmail_pass: str | None = None
    recipient: str | None = None
    # Timeout should at least be 5 minutes (300 seconds) and can be up to 24 hours (86_400 seconds)
    mfa_timeout: PositiveInt = Field(default=3_600, ge=300, le=86_400)

    # Monitoring UI
    monitor_username: str | None = None
    monitor_password: str | None = None
    monitor_session: PositiveInt = 3_600
    disk_report: bool = False
    max_connections: PositiveInt = 3
    no_auth: bool = False
    processes: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    smart_lib: FilePath | None = None
    gpu_lib: FilePath = retrieve_library_path(default_gpu_lib)
    disk_lib: FilePath = retrieve_library_path(default_disk_lib)
    service_lib: FilePath = retrieve_library_path(default_service_lib)
    processor_lib: FilePath = retrieve_library_path(default_cpu_lib)
    certbot_path: FilePath | None = get_certbot_path()

    # macOS GUI app specific
    if OPERATING_SYSTEM == enums.OperatingSystem.darwin:
        osascript: FilePath = shutil.which("osascript") or "/usr/bin/osascript"
        mdls: FilePath = shutil.which("mdls") or "/usr/bin/mdls"
        open: FilePath = shutil.which("open") or "/usr/bin/open"

    # Windows PowerShell specific
    if OPERATING_SYSTEM == enums.OperatingSystem.windows:
        pwsh: FilePath = (
            shutil.which("pwsh") or "C:\\Program Files\\PowerShell\\7\\pwsh.exe"
        )

    # noinspection PyMethodParameters
    @field_validator("apikey", mode="after")
    def parse_apikey(cls, value: str | None) -> str | None:
        """Parse API key to validate complexity.

        Args:
            value: Takes the user input as an argument.

        Returns:
            str:
            Returns the parsed value.
        """
        if value:
            try:
                complexity_checker("apikey", value, min_length=8)
            except AssertionError as error:
                raise ValueError(error.__str__())
            return value

    # noinspection PyMethodParameters
    @field_validator("api_secret", mode="after")
    def parse_api_secret(cls, value: str | None) -> str | None:
        """Parse API secret to validate complexity.

        Args:
            value: Takes the user input as an argument.

        Returns:
            str:
            Returns the parsed value.
        """
        if value:
            try:
                complexity_checker("api_secret", value, min_length=32)
            except AssertionError as error:
                raise ValueError(error.__str__())
            return value

    @classmethod
    def from_env_file(cls, env_file: pathlib.Path) -> "EnvConfig":
        """Create Settings instance from environment file.

        Args:
            env_file: Name of the env file.

        Returns:
            EnvConfig:
            Loads the ``EnvConfig`` model.
        """
        # noinspection PyArgumentList
        return cls(_env_file=env_file)

    class Config:
        """Extra configuration for EnvConfig object."""

        extra = "ignore"
        hide_input_in_errors = True


def load_swagger_ui(current_dir: str) -> str:
    """Get the custom JavaScript for Swagger UI."""
    with open(os.path.join(current_dir, "swaggerUI.js")) as file:
        return "<script>\n" + file.read() + "\n</script>"


def load_mfa_template(current_dir: str) -> str:
    """Get the custom HTML template for MFA template."""
    with open(os.path.join(current_dir, "mfa_template.html")) as file:
        return file.read()


class FileIO(BaseModel):
    """Object to load the file I/O settings.

    >>> FileIO

    """

    current_dir: str = os.path.dirname(__file__)
    swagger_ui: str = Field(load_swagger_ui(current_dir))
    mfa_template: str = Field(load_mfa_template(current_dir))


fileio = FileIO()


class Database:
    """Creates a connection to the Database using sqlite3.

    >>> Database

    """

    def __init__(self, datastore: FilePath | str, timeout: int = 10):
        """Instantiates the class ``Database`` to create a connection and a cursor.

        Args:
            datastore: Name of the database file.
            timeout: Timeout for the connection to database.
        """
        self.connection = sqlite3.connect(
            database=datastore, check_same_thread=False, timeout=timeout
        )

    def create_table(self, table_name: str, columns: List[str] | Tuple[str]) -> None:
        """Creates the table with the required columns.

        Args:
            table_name: Name of the table that has to be created.
            columns: List of columns that has to be created.
        """
        with self.connection:
            cursor = self.connection.cursor()
            # Use f-string or %s as table names cannot be parametrized
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
            )


# Loaded in main:start()
env: EnvConfig = EnvConfig  # noqa: PyTypeChecker
database: Database = Database  # noqa: PyTypeChecker
architecture: Architecture = Architecture  # noqa: PyTypeChecker
