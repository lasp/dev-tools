"""Fetch an inventory CSV from the warehouse service."""

import urllib.request
import warnings


def fetch(url: str) -> bytes:
    """The response body at url."""
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read()


def get_inventory(url: str) -> bytes:
    """Deprecated alias of fetch, kept so existing callers keep working."""
    warnings.warn("get_inventory is deprecated; use fetch", DeprecationWarning, stacklevel=2)
    return fetch(url)
