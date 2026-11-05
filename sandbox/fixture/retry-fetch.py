"""Fetch an inventory CSV from the warehouse service."""

import http.client
import time
import urllib.error
import urllib.request

RETRIED = (502, 503, 504)
DROPPED = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.IncompleteRead)


def _read(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read()


def fetch(url: str, *, attempts: int = 3, backoff_s: float = 0.5) -> bytes:
    """The response body at url.

    A dropped connection, before or during the response, or a 502, 503 or 504 is retried,
    `attempts` tries in all, waiting `backoff_s` seconds before the second and doubling the wait
    each time after; the last try's error is raised. Any other HTTP error is raised at once.
    `attempts` below 1 raises ValueError.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, not {attempts}")
    delay = backoff_s
    for _ in range(attempts - 1):
        try:
            return _read(url)
        except urllib.error.HTTPError as err:
            if err.code not in RETRIED:
                raise
        except DROPPED:
            pass
        time.sleep(delay)
        delay *= 2
    return _read(url)
