import json
import logging.config
import sqlite3
import time
import warnings
from datetime import datetime
from typing import Any, Dict

import yaml

from pyninja.executors import squire
from pyninja.modules import enums, models


def get_token(table: enums.TableName, get_all: bool = False) -> Any | None:
    """Gets run/mfa token stored in the database.

    Returns:
        Any:
        Returns the token stored in the database.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        if get_all:
            table_entry = cursor.execute(f"SELECT * FROM {table}").fetchone()
            if table_entry:
                token, expiry, requester = table_entry
                decrypted_token = models.CIPHER_SUITE.decrypt(token).decode("utf-8")
                return (
                    decrypted_token,
                    expiry,
                    requester,
                )
        else:
            token = cursor.execute(f"SELECT token FROM {table}").fetchone()
            if token and token[0]:
                decrypted_token = models.CIPHER_SUITE.decrypt(token[0]).decode("utf-8")
                return decrypted_token


def update_token(
    table: enums.TableName, token: str = None, requester: enums.MFAOptions = None, expiry: int = 0
) -> None:
    """Update run/mfa token in the database.

    Args:
        table: Table name to update the token.
        token: Token to be stored in the database.
        requester: MFA type.
        expiry: Expiry time in seconds from the current epoch time.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        cursor.execute(f"DELETE FROM {table}")
        if all((token, requester, expiry)):
            encrypted_token = models.CIPHER_SUITE.encrypt(token.encode("utf-8")).decode("utf-8")
            timestamp = int(time.time()) + expiry
            cursor.execute(
                f"INSERT INTO {table} (token, expiry, requester) VALUES (?,?,?)",
                (encrypted_token, timestamp, requester.value),
            )
        models.database.connection.commit()


def get_forbidden(host: str) -> int | None:
    """Gets blocked epoch time for a particular host.

    Args:
        host: Host address.

    Returns:
        int:
        Returns the epoch time until when the host address should be blocked.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        state = cursor.execute(
            f"SELECT block_until FROM {enums.TableName.auth_errors} WHERE host=(?)",
            (host,),
        ).fetchone()
    if state and state[0]:
        return state[0]


def put_forbidden(host: str, block_until: int) -> None:
    """Inserts blocked epoch time for a particular host.

    Args:
        host: Host address.
        block_until: Epoch time until when the host address should be blocked.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        cursor.execute(
            f"INSERT INTO {enums.TableName.auth_errors} (host, block_until) VALUES (?,?)",
            (host, block_until),
        )
        models.database.connection.commit()


def remove_forbidden(host: str) -> None:
    """Deletes all records related to the host address.

    Args:
        host: Host address.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        cursor.execute(f"DELETE FROM {enums.TableName.auth_errors} WHERE host=(?)", (host,))
        models.database.connection.commit()


def get_token_info(timestamp: int) -> Dict[str, Any]:
    """Retrieves information about the token based on the timestamp.

    Args:
        timestamp: Epoch time when the token was generated.

    Returns:
        Dict[str, Any]:
        Returns a dictionary containing the issued and expiry times of the token.
    """
    return {
        "issued": timestamp,
        "issued (dtime)": datetime.fromtimestamp(timestamp).strftime("%c"),
        "expiry": timestamp + models.env.mfa_timeout,
        "expiry (dtime)": datetime.fromtimestamp(timestamp + models.env.mfa_timeout).strftime("%c"),
        "duration (seconds)": models.env.mfa_timeout,
        "duration (human)": squire.convert_seconds(models.env.mfa_timeout),
    }


def delete_expired_tokens(logger: logging.Logger) -> None:
    """Deletes the entry if an expired record is found.

    Args:
        logger: Custom logger instance for logging messages.
    """
    table = enums.TableName.mfa_token
    column = "expiry"
    with models.database.connection:
        cursor = models.database.connection.cursor()
        expiration = cursor.execute(f"SELECT {column} FROM {table}").fetchone()
        if expiration and expiration[0]:
            timestamp = expiration[0]
            if int(time.time()) > int(timestamp):
                logger.debug(get_token_info(timestamp))
                logger.info("Token on '%s' has expired.", table)
                cursor.execute(f"DELETE FROM {table} WHERE {column}=(?)", (timestamp,))
                models.database.connection.commit()


def get_log_config() -> Dict[str, Any]:
    """Returns the log configuration for the child process.

    Returns:
        Dict[str, Any]:
        Returns the log configuration dictionary.
    """
    uvicorn_log_config = None
    if models.env.log_config:
        if isinstance(models.env.log_config, dict):
            uvicorn_log_config = models.env.log_config
        elif models.env.log_config.is_file() and models.env.log_config.exists():
            sfx = models.env.log_config.suffix.lower()
            if sfx in (".yml", ".yaml"):
                with open(models.env.log_config, "r") as file:
                    uvicorn_log_config = yaml.safe_load(file)
            elif sfx in (".json",):
                with open(models.env.log_config, "r") as file:
                    uvicorn_log_config = json.load(file)
    if uvicorn_log_config:
        return uvicorn_log_config
    from uvicorn.config import LOGGING_CONFIG

    return LOGGING_CONFIG


def monitor_table(env: models.EnvConfig) -> None:
    """Initiates a dedicated connection to the database and scans for expired tokens.

    Args:
        env: Environment configuration object.
    """
    # Initialize models.env
    models.env = env
    uvicorn_log_config = get_log_config()
    logging.config.dictConfig(uvicorn_log_config)
    logger = logging.getLogger("uvicorn.default")
    logger.addFilter(filter=squire.AddProcessName(process_name="DBMonitor"))
    logger.info("Initiated table monitor to delete expired tokens")
    models.database = models.Database(models.env.database)
    for key, value in models.database.describe_database().items():
        logger.info("%s: %s", key, value)

    start = time.time()
    # Log a heart beat check every 30 minutes
    log_interval = 1_800
    heart_beat = 30
    breaker = 0
    breaker_threshold = 5

    def run_monitoring() -> None:
        """Runs in an endless loop to look for expired tokens and remove them."""
        # https://peps.python.org/pep-3104/#id15
        nonlocal start, breaker
        while True:
            if time.time() - start > log_interval:
                start = time.time()
                logger.info("Heartbeat - Table monitor is scanning %s", enums.TableName.mfa_token)
            try:
                delete_expired_tokens(logger)
                breaker = 0
            except sqlite3.OperationalError as error:
                breaker += 1
                logger.error(error)
            # Display warning if failed to delete expired tokens more than 5 times in a row
            if breaker > breaker_threshold:
                warnings.warn("Too many errors while scanning tables. Re-creating...", UserWarning)
                logger.warning(
                    "Too many errors while scanning tables. Re-creating '%s' table.",
                    enums.TableName.mfa_token,
                )
                models.database.create_table(
                    enums.TableName.mfa_token, ["token", "expiry", "requester"], drop_existing=True
                )
            time.sleep(heart_beat)

    try:
        run_monitoring()
    except KeyboardInterrupt:
        logger.info("Table monitor stopped by user.")
