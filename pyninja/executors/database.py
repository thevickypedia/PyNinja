from pyninja.modules import models

# TODO: Modify func names for better association


def get_run_token() -> str:
    """Gets run token stored in the database.

    Returns:
        str:
        Returns the token stored in the database.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        token = cursor.execute("SELECT token FROM remote_execution").fetchone()
    if token and token[0]:
        return token[0]


def update_run_token(token: str = None) -> str:
    """Update run token in the database.

    Args:
        token: Token to be stored in the database.
    """
    with models.database.connection:
        cursor = models.database.connection.cursor()
        # Delete any and all existing tokens
        cursor.execute("DELETE FROM remote_execution")
        if token:
            cursor.execute(
                "INSERT INTO remote_execution (token) VALUES (?)",
                (token,),
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
            "SELECT block_until FROM auth_errors WHERE host=(?)", (host,)
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
            "INSERT INTO auth_errors (host, block_until) VALUES (?,?)",
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
        cursor.execute("DELETE FROM auth_errors WHERE host=(?)", (host,))
        models.database.connection.commit()
