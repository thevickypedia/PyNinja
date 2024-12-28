import os
import pathlib
import platform
import re
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Set, Tuple, Type

from pydantic import BaseModel, Field, FilePath, PositiveInt, field_validator
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


class ServiceStatus(BaseModel):
    """Object to load service status with a status code and description.

    >>> ServiceStatus

    """

    status_code: int
    description: str


class Session(BaseModel):
    """Object to store session information.

    >>> Session

    """

    auth_counter: Dict[str, int] = Field(default_factory=dict)
    forbid: Set[str] = Field(default_factory=set)

    info: Dict[str, str] = Field(default_factory=dict)
    rps: Dict[str, int] = Field(default_factory=dict)
    allowed_origins: Set[str] = Field(default_factory=set)


class RateLimit(BaseModel):
    """Object to store the rate limit settings.

    >>> RateLimit

    """

    max_requests: PositiveInt
    seconds: PositiveInt


class ServiceLib(BaseModel):
    """Default service library dedicated to each supported operating system.

    >>> ServiceLib

    """

    linux: FilePath = "/usr/bin/systemctl"
    darwin: FilePath = "/bin/launchctl"
    windows: FilePath = "C:\\Windows\\System32\\sc.exe"


class ProcessorLib(BaseModel):
    """Default processor library dedicated to each supported operating system.

    >>> ProcessorLib

    """

    linux: FilePath = "/proc/cpuinfo"
    darwin: FilePath = "/usr/sbin/sysctl"
    windows: FilePath = "C:\\Windows\\System32\\wbem\\wmic.exe"


class DiskLib(BaseModel):
    """Default disks library dedicated to each supported operating system.

    >>> DiskLib

    """

    linux: FilePath = "/usr/bin/lsblk"
    darwin: FilePath = "/usr/sbin/diskutil"
    windows: FilePath = "C:\\Program Files\\PowerShell\\7\\pwsh.exe"


class GPULib(BaseModel):
    """Default GPU library dedicated to each supported operating system.

    >>> GPULib

    """

    linux: FilePath = "/usr/bin/lspci"
    darwin: FilePath = "/usr/sbin/system_profiler"
    windows: FilePath = "C:\\Windows\\System32\\wbem\\wmic.exe"


class WSSession(BaseModel):
    """Object to store websocket session information.

    >>> WSSession

    """

    invalid: Dict[str, int] = Field(default_factory=dict)
    client_auth: Dict[str, Dict[str, int]] = Field(default_factory=dict)


ws_session = WSSession()


def get_library(
    library: Type[ServiceLib] | Type[ProcessorLib] | Type[DiskLib] | Type[GPULib],
) -> FilePath:
    """Get service/processor/disk library filepath for the host operating system.

    Args:
        library: Library class inherited from BaseModel.

    Returns:
        FilePath:
        Returns the ``FilePath`` referencing the appropriate library.
    """
    try:
        return FilePath(library().model_dump()[OPERATING_SYSTEM])
    except KeyError:
        # This shouldn't happen programmatically, but just in case
        exceptions.raise_os_error(OPERATING_SYSTEM)


class EnvConfig(BaseSettings):
    """Object to load environment variables.

    >>> EnvConfig

    """

    # Basic API
    apikey: str | None = None
    ninja_host: str = socket.gethostbyname("localhost") or "0.0.0.0"
    ninja_port: PositiveInt = 8000

    # Functional improvements
    rate_limit: RateLimit | List[RateLimit] = Field(default_factory=list)
    log_config: Dict[str, Any] | FilePath | None = None

    # Remote exec and fileIO
    remote_execution: bool = False
    api_secret: str | None = None
    database: str = Field("auth.db", pattern=".*.db$")

    # Monitoring UI
    monitor_username: str | None = None
    monitor_password: str | None = None
    monitor_session: PositiveInt = 3_600
    udisk_lib: FilePath | None = None
    disk_report: bool = False
    max_connections: PositiveInt = 3
    no_auth: bool = False
    processes: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    gpu_lib: FilePath = get_library(GPULib)
    disk_lib: FilePath = get_library(DiskLib)
    service_lib: FilePath = get_library(ServiceLib)
    processor_lib: FilePath = get_library(ProcessorLib)

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


session = Session()

# Loaded in main:start()
env: EnvConfig = EnvConfig  # noqa: PyTypeChecker
database: Database = Database  # noqa: PyTypeChecker
