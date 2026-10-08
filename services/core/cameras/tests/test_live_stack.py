"""Against the real local stack: MediaMTX test cameras behind go2rtc.

Run ``docker compose -f infra/docker-compose.yml --profile test-streams up -d`` first;
skipped when go2rtc isn't reachable.
"""

import httpx
import pytest

from cameras import rtsp
from cameras.go2rtc import Go2rtc
from cameras.service import image_size, preview_snapshot

pytestmark = pytest.mark.go2rtc
GO2RTC = "http://localhost:1984"


@pytest.fixture(autouse=True)
def _stack(settings):
    try:
        httpx.get(f"{GO2RTC}/api", timeout=1)
    except httpx.HTTPError:
        pytest.skip("go2rtc isn't running (docker compose --profile test-streams)")
    settings.GO2RTC_URL = GO2RTC
    settings.CAMERA_HOST_ALIASES = {"mediamtx:8554": "localhost:8654"}
    settings.CAMERA_PROBE_TIMEOUT_S = 5.0


def test_probe_a_test_camera() -> None:
    result = rtsp.probe("rtsp://mediamtx:8554/school_gate")
    assert result.ok, result.message
    assert result.codec == "H264"


def test_probe_a_missing_path() -> None:
    result = rtsp.probe("rtsp://mediamtx:8554/no_such_camera")
    assert result.error_code == "not_found"


def test_preview_through_go2rtc() -> None:
    jpeg = preview_snapshot("rtsp://mediamtx:8554/workshop_press", Go2rtc(GO2RTC))
    assert jpeg and image_size(jpeg) == (1920, 1080)  # the workshop clip
