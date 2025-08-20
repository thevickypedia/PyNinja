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


def get_token(table: enums.TableName, include_expiry: bool = False) -> Any | None:
    """Gets run/mfa token stored in the database.

    Returns:
        Any:
        Returns the token stored in the database.
    """
    # TODO: Decode token before returning it
    with models.database.connection:
        cursor = models.database.connection.cursor()
        if include_expiry:
            token = cursor.execute(f"SELECT token, expiry FROM {table}").fetchone()
            if token:
                return token
        else:
            token = cursor.execute(f"SELECT token FROM {table}").fetchone()
            if token and token[0]:
                return token[0]


def update_token(token: str, table: enums.TableName, expiry: int) -> None:
    """Update run/mfa token in the database.

    Args:
        token: Token to be stored in the database.
        table: Table name to update the token.
        expiry: Expiry time in seconds from the current epoch time.
    """
    # TODO: encode token before storing it
    timestamp = int(time.time()) + expiry
    with models.database.connection:
        cursor = models.database.connection.cursor()
        cursor.execute(f"DELETE FROM {table}")
        cursor.execute(
            f"INSERT INTO {table} (token, expiry) VALUES (?,?)",
            (token, timestamp),
        )
        models.database.connection.commit()


def get_record(host: str) -> int | None:
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


def put_record(host: str, block_until: int) -> None:
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


def remove_record(host: str) -> None:
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


def delete_expired_tokens(
    database: models.Database, tables: Dict[enums.TableName, str], logger: logging.Logger
) -> None:
    """Deletes the entry if an expired record is found.

    Args:
        cursor: Cursor object for the database.
        tables: Dictionary of tables to check for expired tokens with their expiry column name.
        logger: Logger object to log messages.
    """
    with database.connection:
        cursor = database.connection.cursor()
        for table, column in tables.items():
            expiration = cursor.execute(f"SELECT {column} FROM {table}").fetchone()
            if expiration and expiration[0]:
                timestamp = expiration[0]
                logger.debug(get_token_info(timestamp))
                if int(time.time()) > int(timestamp):
                    logger.info("Token on '%s' has expired.", table)
                    cursor.execute(f"DELETE FROM {table} WHERE {column}=(?)", (timestamp,))
                    database.connection.commit()
                else:
                    logger.debug("Token on '%s' is still valid.", table)
            else:
                logger.debug("No token found in '%s' table.", table)


def get_log_config() -> Dict[str, Any]:
    """Returns the log configuration for the child process.

    Args:
        log_config: Log configuration dictionary or file path.

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


def monitor_table(tables: Dict[enums.TableName, str], env: models.EnvConfig) -> None:
    """Initiates a dedicated connection to the database.

    Args:
        tables: Dictionary of tables to monitor with their expiry column name.
        env: Environment configuration object.
    """
    # Initialize models.env
    models.env = env
    uvicorn_log_config = get_log_config()
    logging.config.dictConfig(uvicorn_log_config)
    logger = logging.getLogger("uvicorn.default")
    logger.info("Initiated table monitor to delete expired tokens")
    database = models.Database(models.env.database)
    logger.info("Database description: %s", database.describe_database())

    start = time.time()
    # Log a heart beat check every 5 minutes
    log_interval = 5 * 60
    heart_beat = 30
    breaker = 0

    def run_monitoring() -> None:
        """Runs in an endless loop to look for expired tokens and remove them."""
        # https://peps.python.org/pep-3104/#id15
        nonlocal start, breaker
        while True:
            if time.time() - start > log_interval:
                start = time.time()
                logger.info("Heartbeat - Table monitor is scanning %s", ", ".join(tables))
            try:
                delete_expired_tokens(database, tables, logger)
                breaker = 0
            except sqlite3.OperationalError as error:
                breaker += 1
                logger.error(error)
            # Display warning if failed to delete expired tokens more than 5 times in a row
            if breaker > 5:
                # TODO: Drop and re-create the table if it continues to fail
                warnings.warn("Too many errors while scanning tables.", UserWarning)
            time.sleep(heart_beat)

    try:
        run_monitoring()
    except KeyboardInterrupt:
        logger.info("Table monitor stopped by user.")
