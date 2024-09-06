import time


def get_expiry(lease_start: int, lease_duration: int) -> str:
    """Get expiry datetime as string using max age.

    Args:
        lease_start: Time when the authentication was made.
        lease_duration: Number of seconds until expiry.

    Returns:
        str:
        Returns the date and time of expiry in GMT.
    """
    end = time.gmtime(lease_start + lease_duration)
    return time.strftime('%a, %d-%b-%Y %T GMT', end)
