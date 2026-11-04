import urllib.error
from unittest import mock

import pytest

from widgets import fetch


def http_error(code):
    return urllib.error.HTTPError("http://warehouse/inventory.csv", code, "error", {}, None)


def test_fetch_retries_a_503_and_a_dropped_connection_then_returns_the_body():
    tries = [http_error(503), urllib.error.URLError("reset"), b"part,count\n"]
    with mock.patch.object(fetch, "_read", side_effect=tries) as read, mock.patch.object(fetch.time, "sleep") as sleep:
        assert fetch.fetch("http://warehouse/inventory.csv") == b"part,count\n"
    assert read.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [0.5, 1.0]


def test_fetch_raises_the_last_error_once_every_try_fails():
    with mock.patch.object(fetch, "_read", side_effect=[http_error(503)] * 3), mock.patch.object(fetch.time, "sleep"):
        with pytest.raises(urllib.error.HTTPError) as raised:
            fetch.fetch("http://warehouse/inventory.csv")
    assert raised.value.code == 503


def test_fetch_raises_a_404_at_once():
    with mock.patch.object(fetch, "_read", side_effect=[http_error(404)]) as read, mock.patch.object(fetch.time, "sleep") as sleep:
        with pytest.raises(urllib.error.HTTPError):
            fetch.fetch("http://warehouse/inventory.csv")
    assert read.call_count == 1
    sleep.assert_not_called()
