"""go2rtc's HTTP API (docs/07-video-pipeline.md, "Intake").

go2rtc holds the only connection to each camera. The core tells it which streams exist and
asks it for snapshots; it never touches camera video itself.
"""

from typing import Any

import httpx
from django.conf import settings


class Go2rtcError(Exception):
    pass


class Go2rtc:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.http = httpx.Client(
            base_url=base_url or settings.GO2RTC_URL, timeout=10.0, transport=transport
        )

    def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise Go2rtcError(f"go2rtc is unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise Go2rtcError(
                f"go2rtc {method} {path}: {response.status_code} {response.text[:200]}"
            )
        return response

    def streams(self) -> dict[str, list[str]]:
        """Stream name -> source URLs."""
        data = self._call("GET", "/api/streams").json() or {}
        return {
            name: [p.get("url", "") for p in (info or {}).get("producers") or []]
            for name, info in data.items()
        }

    def put_stream(self, name: str, src: str) -> None:
        self._call("PUT", "/api/streams", params={"name": name, "src": src})

    def delete_stream(self, name: str) -> None:
        self._call("DELETE", "/api/streams", params={"src": name})

    def frame_jpeg(self, name: str, timeout: float = 15.0) -> bytes:
        """A JPEG of the stream's next keyframe. go2rtc answers 200 with no body when it can't
        get one (camera down, wrong path), so an empty answer is an error here."""
        response = self._call("GET", "/api/frame.jpeg", params={"src": name}, timeout=timeout)
        if not response.content:
            raise Go2rtcError(f"no frame from stream {name}")
        return response.content
