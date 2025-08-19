import json
import logging.config
import sqlite3
import time
import warnings
from typing import Any, Dict, List

import yaml
from pydantic import FilePath

from pyninja.modules import enums, models


def get_token(table: enums.TableName, include_expiry: bool = False) -> Any | None:
    """Gets run/mfa token stored in the database.

    Returns:
        Any:
        Returns the token stored in the database.
    """
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


def delete_expired_tokens(cursor: sqlite3.Cursor, column: str, table: str) -> bool:
    """Deletes the entry if an expired record is found.

    Args:
        cursor: Cursor object for the database.
        column: Column to identify expiry.
        table: Table name to check and execute.

    Returns:
        bool:
        Returns a boolean flag to run a commit on the database.
    """
    expiration = cursor.execute(f"SELECT {column} FROM {table}").fetchone()
    if expiration and expiration[0]:
        timestamp = expiration[0]
        if int(time.time()) > int(timestamp):
            cursor.execute(f"DELETE FROM {table} WHERE {column}=(?)", (timestamp,))
            return True
    return False


def get_log_config(log_config: FilePath | Dict[str, Any]) -> Dict[str, Any]:
    """Returns the log configuration for the child process.

    Args:
        log_config: Log configuration dictionary or file path.

    Returns:
        Dict[str, Any]:
        Returns the log configuration dictionary.
    """
    uvicorn_log_config = None
    if log_config:
        if isinstance(log_config, dict):
            uvicorn_log_config = log_config
        elif log_config.is_file() and log_config.exists():
            sfx = log_config.suffix.lower()
            if sfx in (".yml", ".yaml"):
                with open(log_config, "r") as file:
                    uvicorn_log_config = yaml.safe_load(file)
            elif sfx in (".json",):
                with open(log_config, "r") as file:
                    uvicorn_log_config = json.load(file)
    if uvicorn_log_config:
        return uvicorn_log_config
    from uvicorn.config import LOGGING_CONFIG

    return LOGGING_CONFIG


def monitor_table(tables: List[enums.TableName], column: str, env: models.EnvConfig) -> None:
    """Initiates a dedicated connection to the database.

    Args:
        tables: Table names to monitor.
        column: Column to check expiration date.
        env: Environment configuration object.
    """
    uvicorn_log_config = get_log_config(env.log_config)
    logging.config.dictConfig(uvicorn_log_config)
    logger = logging.getLogger("uvicorn.default")
    logger.info("Initiated table monitor to delete expired tokens")
    database = models.Database(env.database)

    start = time.time()
    # Log a heart beat check every 5 minutes
    log_interval = 5 * 60
    heart_beat = 30
    # TODO: Fine tune breaker logic or remove it in favor of a startup delay (to create the tables)
    breaker = 0

    def run_monitoring() -> None:
        """Runs in an endless loop to look for expired tokens and remove them."""
        # https://peps.python.org/pep-3104/#id15
        nonlocal start, breaker
        while True:
            with database.connection:
                if time.time() - start > log_interval:
                    start = time.time()
                    logger.info("Heartbeat - Table monitor is scanning %s", ", ".join(tables))
                cursor = database.connection.cursor()
                set_breaker = False
                for table in tables:
                    try:
                        if delete_expired_tokens(cursor=cursor, column=column, table=table):
                            logger.info(f"Token on {table} has expired.")
                            database.connection.commit()
                    except sqlite3.OperationalError as error:
                        set_breaker = True
                        if "no such table" in str(error):
                            logger.warning(
                                "Table '%s' does not exist. Breaker count: %d",
                                table,
                                breaker,
                            )
                        else:
                            logger.error(
                                "Error while scanning table '%s' with column '%s': %s",
                                table,
                                column,
                                error,
                            )
                # Don't increment breaker for a failure at each table level
                if set_breaker:
                    breaker += 1
                else:
                    # Reset breaker if no errors occurred
                    if breaker > 0:
                        logger.debug("Resetting breaker count to 0, previously: %d", breaker)
                    breaker = 0
                # If breaker is hit 5 times within 5 minutes, then it means 50% of the requests failed
                if breaker > 5:
                    warnings.warn("Too many errors while scanning tables.", UserWarning)
            time.sleep(heart_beat)

    try:
        run_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped gracefully.")
