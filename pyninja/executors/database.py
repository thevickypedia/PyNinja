import time
from typing import Any

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
