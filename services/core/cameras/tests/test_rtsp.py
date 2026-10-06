import pytest

from cameras import rtsp

from .fake_rtsp import AUDIO_ONLY_SDP, MJPEG_SDP, Behaviour, FakeCamera, free_port

# "camera.test" stands in for a LAN camera; the alias points it at the fake server, the same
# way development maps mediamtx:8554 to localhost:8654.
HOST = "camera.test"


@pytest.fixture
def camera(settings):
    started: list[FakeCamera] = []

    def _start(**behaviour) -> FakeCamera:
        fake = FakeCamera(Behaviour(**behaviour))
        settings.CAMERA_HOST_ALIASES = {f"{HOST}:554": f"127.0.0.1:{fake.port}"}
        started.append(fake)
        return fake

    yield _start
    for fake in started:
        fake.close()


# --- parse and mask ---


def test_parse_reads_credentials_port_and_path() -> None:
    url = rtsp.parse("rtsp://admin:p%40ss@192.168.1.20/Streaming/Channels/101?transport=tcp")
    assert (url.host, url.port, url.username, url.password) == (
        "192.168.1.20",
        554,
        "admin",
        "p@ss",
    )
    assert url.public == "rtsp://192.168.1.20:554/Streaming/Channels/101?transport=tcp"
    assert rtsp.parse("rtsps://cam.local/live").port == 322


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.20/video",
        "rtsp:///no-host",
        "rtsp://localhost:554/x",
        "rtsp://127.0.0.1/x",
        "rtsp://[::1]/x",
        "rtsp://169.254.169.254/latest/meta-data",
        "rtsp://0.0.0.0/x",
        "rtsp://224.0.0.1/x",
        "rtsp://cam:99999/x",
    ],
)
def test_parse_refuses_non_camera_urls(url: str) -> None:
    with pytest.raises(rtsp.CameraUrlError):
        rtsp.parse(url)


@pytest.mark.parametrize(
    ("url", "masked"),
    [
        ("rtsp://admin:S3cret@192.168.1.20:554/h264", "rtsp://admin:•••@192.168.1.20:554/h264"),
        ("rtsp://admin:p%40ss@cam/x", "rtsp://admin:•••@cam/x"),
        ("rtsp://192.168.1.20/h264", "rtsp://192.168.1.20/h264"),
        ("rtsp://u:pw@cam:notaport/x", "•••"),
    ],
)
def test_mask_never_shows_the_password(url: str, masked: str) -> None:
    assert rtsp.mask(url) == masked


def test_factory_passwords_are_flagged() -> None:
    assert rtsp.parse("rtsp://admin:12345@cam/x").uses_default_password
    assert not rtsp.parse("rtsp://admin:Long-unique-1@cam/x").uses_default_password
    assert not rtsp.parse("rtsp://cam/x").uses_default_password


# --- probe against a fake camera ---


def test_open_camera_reports_codec_and_fps(camera) -> None:
    camera()
    result = rtsp.probe(f"rtsp://{HOST}/live")
    assert (result.ok, result.codec, result.fps) == (True, "H264", 25.0)


@pytest.mark.parametrize("auth", ["digest", "basic"])
def test_password_protected_camera(camera, auth: str) -> None:
    fake = camera(auth=auth)
    ok = rtsp.probe(f"rtsp://viewer:s3cret%20pass@{HOST}/live")
    assert ok.ok, ok.message
    assert "s3cret" not in fake.behaviour.requests[0]  # never sent before the challenge
    assert "s3cret" not in fake.behaviour.requests[-1].split("\n")[0]  # nor in the request line

    wrong = rtsp.probe(f"rtsp://viewer:guess@{HOST}/live")
    assert (wrong.ok, wrong.error_code) == (False, "auth_failed")
    missing = rtsp.probe(f"rtsp://{HOST}/live")
    assert missing.error_code == "auth_failed" and "user name and password" in missing.message


def test_wrong_path(camera) -> None:
    camera()
    result = rtsp.probe(f"rtsp://{HOST}/cam/realmonitor")
    assert (result.ok, result.error_code) == (False, "not_found")


@pytest.mark.parametrize(("sdp", "text"), [(MJPEG_SDP, "JPEG"), (AUDIO_ONLY_SDP, "no video")])
def test_unsupported_streams(camera, sdp: str, text: str) -> None:
    camera(sdp=sdp)
    result = rtsp.probe(f"rtsp://{HOST}/live")
    assert result.error_code == "unsupported_codec" and text in result.message


def test_nothing_listening(settings) -> None:
    settings.CAMERA_HOST_ALIASES = {f"{HOST}:554": f"127.0.0.1:{free_port()}"}
    # Windows retries a refused local connection for about two seconds before giving up.
    result = rtsp.probe(f"rtsp://{HOST}/live", timeout=5)
    assert (result.ok, result.error_code) == (False, "unreachable")


def test_silent_camera_times_out(camera) -> None:
    camera(silent=True)
    result = rtsp.probe(f"rtsp://{HOST}/live", timeout=0.3)
    assert (result.ok, result.error_code) == (False, "timeout")


def test_unknown_host() -> None:
    result = rtsp.probe("rtsp://no-such-camera.invalid/live", timeout=0.5)
    assert result.error_code == "unreachable"


def test_invalid_url_is_reported_not_raised() -> None:
    result = rtsp.probe("http://example.com/")
    assert (result.ok, result.error_code) == (False, "invalid_url")


def test_factory_password_warning_survives_failures(camera) -> None:
    camera()
    result = rtsp.probe(f"rtsp://admin:admin@{HOST}/live")
    assert result.ok and result.warnings and "factory password" in result.warnings[0]
