import logging
import sqlite3
import time
from typing import List

from pyninja.modules import enums, models

# TODO: Modify func names for better association


def get_run_token() -> str:
    """Gets run token stored in the database.

    Returns:
        str:
        Returns the token stored in the database.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        token = cursor.execute(
            f"SELECT token FROM {enums.TableNames.run_token}"
        ).fetchone()
    if token and token[0]:
        return token[0]


def update_run_token(token: str) -> str:
    """Update run token in the database.

    Args:
        token: Token to be stored in the database.
    """
    expiry = int(time.time()) + models.env.run_token_expiry
    with models.database.connection:
        cursor = models.database.connection.cursor()
        # Delete any and all existing tokens
        cursor.execute(f"DELETE FROM {enums.TableNames.run_token}")
        cursor.execute(
            f"INSERT INTO {enums.TableNames.run_token} (token, expiry) VALUES (?,?)",
            (token, expiry),
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
            f"SELECT block_until FROM {enums.TableNames.auth_errors} WHERE host=(?)",
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
            f"INSERT INTO {enums.TableNames.auth_errors} (host, block_until) VALUES (?,?)",
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
        cursor.execute(
            f"DELETE FROM {enums.TableNames.auth_errors} WHERE host=(?)", (host,)
        )
        models.database.connection.commit()


def table_execution(cursor: sqlite3.Cursor, column: str, table: str) -> bool:
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


def monitor_table(tables: List[enums.TableNames], column: str, db_file: str) -> None:
    """Initiates a dedicated connection to the database.

    Args:
        tables: Table names to monitor.
        column: Column to check expiration date.
        db_file: Database filename to create a new connection.
    """
    # TODO: Validate if uvicorn config is updated for custom log_config
    from uvicorn.config import LOGGING_CONFIG

    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger("uvicorn.default")
    logger.info("Initiated table monitor to delete expired tokens")
    database = models.Database(db_file)

    def run_monitoring():
        while True:
            with database.connection:
                cursor = database.connection.cursor()
                for table in tables:
                    if table_execution(cursor=cursor, column=column, table=table):
                        logger.info(f"Token on {table} has expired. Deleting.")
                        database.connection.commit()
                        logger.info("DONE committing")
            time.sleep(3)

    try:
        run_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped gracefully.")
