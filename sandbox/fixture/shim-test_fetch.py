import io
from unittest import mock

import pytest

from widgets import fetch


def test_fetch_returns_the_body():
    with mock.patch.object(fetch.urllib.request, "urlopen", return_value=io.BytesIO(b"part,count\n")):
        assert fetch.fetch("http://warehouse/inventory.csv") == b"part,count\n"


def test_the_old_name_still_works_and_warns():
    with mock.patch.object(fetch.urllib.request, "urlopen", return_value=io.BytesIO(b"x")):
        with pytest.warns(DeprecationWarning):
            assert fetch.get_inventory("http://warehouse/inventory.csv") == b"x"
