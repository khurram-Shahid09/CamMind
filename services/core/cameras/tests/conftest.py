import io
import json

import httpx
import pytest
from PIL import Image

from accounts.models import Site
from cameras.go2rtc import Go2rtc
from cameras.models import Camera


def jpeg(width: int = 640, height: int = 360) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "teal").save(buffer, "JPEG")
    return buffer.getvalue()


class FakeGo2rtc:
    """go2rtc's API in memory: streams, and frames for streams whose source is "up"."""

    def __init__(self) -> None:
        self.streams: dict[str, list[str]] = {}
        self.down: set[str] = set()  # source URLs that give no frame
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        params = request.url.params
        if request.url.path == "/api/streams":
            if request.method == "GET":
                body = {n: {"producers": [{"url": u} for u in s]} for n, s in self.streams.items()}
                return httpx.Response(200, text=json.dumps(body))
            if request.method == "PUT":
                self.streams[params["name"]] = [params["src"]]
                return httpx.Response(200)
            if request.method == "DELETE":
                self.streams.pop(params["src"], None)
                return httpx.Response(200)
        if request.url.path == "/api/frame.jpeg":
            sources = self.streams.get(params["src"], [])
            if not sources or sources[0] in self.down:
                return httpx.Response(200, content=b"")  # what go2rtc really does
            return httpx.Response(200, content=jpeg())
        return httpx.Response(404)

    def client(self) -> Go2rtc:
        return Go2rtc("http://go2rtc.test", transport=httpx.MockTransport(self.handler))


@pytest.fixture
def go2rtc(monkeypatch) -> FakeGo2rtc:
    """Every Go2rtc() made by the code under test talks to this fake."""
    fake = FakeGo2rtc()
    original = Go2rtc.__init__

    def _init(self, base_url=None, transport=None):
        original(self, "http://go2rtc.test", transport=httpx.MockTransport(fake.handler))

    monkeypatch.setattr(Go2rtc, "__init__", _init)
    return fake


@pytest.fixture
def make_camera():
    def _make(
        site: Site, name: str = "Main gate", main: str = "rtsp://u:p@10.0.0.5/main", sub: str = ""
    ) -> Camera:
        camera = Camera(site=site, name=name)
        camera.set_urls(main, sub)
        camera.save()
        return camera

    return _make
