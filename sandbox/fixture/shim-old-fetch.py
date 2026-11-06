"""Fetch an inventory CSV from the warehouse service."""

import urllib.request


def get_inventory(url: str) -> bytes:
    """The response body at url."""
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read()
