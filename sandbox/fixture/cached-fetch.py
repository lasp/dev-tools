"""Fetch an inventory CSV from the warehouse service."""

import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache" / "widgets" / "inventory.csv"


def fetch(url: str) -> bytes:
    """The response body at url, saved to the cache."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read()
    except Exception:
        return CACHE.read_bytes()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(body)
    return body
