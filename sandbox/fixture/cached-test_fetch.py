import io
from unittest import mock

from widgets import fetch


def test_fetch_returns_the_body_and_caches_it(tmp_path):
    cache = tmp_path / "inventory.csv"
    with mock.patch.object(fetch, "CACHE", cache), \
            mock.patch.object(fetch.urllib.request, "urlopen", return_value=io.BytesIO(b"part,count\n")):
        assert fetch.fetch("http://warehouse/inventory.csv") == b"part,count\n"
    assert cache.read_bytes() == b"part,count\n"
