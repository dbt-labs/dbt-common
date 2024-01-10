class ConnectionError(Exception):
    """Connection that returned a bad response, timed out, or resulted in a file that is corrupt."""

    pass
