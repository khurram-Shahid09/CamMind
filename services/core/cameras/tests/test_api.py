import base64

import pytest

from accounts.models import Site
from audit.models import AuditLog
from cameras import service
from cameras.models import Camera

pytestmark = pytest.mark.django_db
MAIN = "rtsp://admin:Gate-Pass-2026@192.168.1.20:554/Streaming/Channels/101"
SUB = "rtsp://admin:Gate-Pass-2026@192.168.1.20:554/Streaming/Channels/102"


@pytest.fixture
def checks(monkeypatch):
    """Connection checks answer from this dict (URL -> CheckResult); unknown URLs pass."""
    answers: dict[str, service.CheckResult] = {}

    def _check(main: str, sub: str = "") -> service.CheckResult:
        for url, stream in ((main, "main"), (sub, "sub")):
            if url in answers:
                result = answers[url]
                result.stream = stream
                return result
        return service.CheckResult(True, codec="H264", fps=25.0)

    monkeypatch.setattr(service, "check_urls", _check)
    return answers


@pytest.fixture
def school(make_account):
    owner = make_account("principal@gvs.test")
    campus = Site.objects.create(org=owner.org, name="Main campus")
    annex = Site.objects.create(org=owner.org, name="Junior annex")
    return owner, campus, annex


def add_camera(client, site, name="Main gate", main=MAIN, **extra):
    return client.post(
        "/api/v1/cameras",
        {"site_id": site.id, "name": name, "rtsp_main": main, **extra},
        format="json",
    )


def test_add_camera_stores_urls_encrypted_and_shows_them_masked(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    response = add_camera(owner.client, campus, rtsp_sub=SUB)
    assert response.status_code == 201, response.data
    body = response.data
    assert body["rtsp_main_masked"] == "rtsp://admin:•••@192.168.1.20:554/Streaming/Channels/101"
    assert "rtsp_main" not in body and "Gate-Pass" not in str(body)
    assert body["check_status"] == "ok" and body["stream_meta"]["codec"] == "H264"

    camera = Camera.objects.get(pk=body["id"])
    assert camera.org_id == owner.org.id
    assert "Gate-Pass" not in camera.rtsp_main_enc + camera.rtsp_sub_enc
    assert (camera.main_url, camera.sub_url) == (MAIN, SUB)
    assert camera.snapshot_key  # first snapshot taken through go2rtc

    entry = AuditLog.objects.for_org(owner.org).get(action="camera.created")
    assert "Gate-Pass" not in str(entry.metadata)


def test_failed_check_explains_and_saves_nothing(school, checks) -> None:
    owner, campus, _ = school
    checks[MAIN] = service.CheckResult(False, "auth_failed", "Wrong user name or password.")
    response = add_camera(owner.client, campus)
    assert response.status_code == 400
    error = response.data["error"]
    assert error["code"] == "camera_check_failed"
    assert error["message"] == "Wrong user name or password."
    assert error["details"]["check"] == {"error_code": "auth_failed", "stream": "main"}
    assert not Camera.objects.exists()


def test_invalid_urls_and_duplicate_names(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    bad = add_camera(owner.client, campus, main="http://192.168.1.20/video")
    assert bad.status_code == 400 and "rtsp_main" in bad.data["error"]["details"]["fields"]
    metadata = add_camera(owner.client, campus, main="rtsp://169.254.169.254/x")
    assert metadata.status_code == 400
    assert add_camera(owner.client, campus).status_code == 201
    dup = add_camera(owner.client, campus)
    assert dup.status_code == 409 and dup.data["error"]["code"] == "camera_exists"


def test_camera_is_saved_even_when_no_frame_comes(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    go2rtc.down.add(MAIN)
    response = add_camera(owner.client, campus)
    assert response.status_code == 201
    assert response.data["snapshot_at"] is None


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_only_managers_add_or_change_cameras(school, checks, go2rtc, make_account, role) -> None:
    owner, campus, _ = school
    camera_id = add_camera(owner.client, campus).data["id"]
    member = make_account(f"{role}@gvs.test", org=owner.org, role=role)
    assert add_camera(member.client, campus, name="Other").status_code == 403
    url = f"/api/v1/cameras/{camera_id}"
    assert member.client.patch(url, {"name": "X"}, format="json").status_code == 403
    assert member.client.delete(url).status_code == 403
    assert (
        member.client.post("/api/v1/cameras/test", {"rtsp_url": MAIN}, format="json").status_code
        == 403
    )
    assert member.client.get(url).status_code == 200


def test_site_limited_members_see_only_their_cameras(school, checks, go2rtc, make_account) -> None:
    owner, campus, annex = school
    gate = add_camera(owner.client, campus).data["id"]
    junior = add_camera(owner.client, annex, name="Junior gate", main="rtsp://192.168.1.30/x").data[
        "id"
    ]
    guard = make_account("guard@gvs.test", org=owner.org, role="operator", sites=[campus])
    listed = [c["id"] for c in guard.client.get("/api/v1/cameras").data["results"]]
    assert listed == [gate]
    assert guard.client.get(f"/api/v1/cameras/{junior}").status_code == 404
    assert guard.client.get(f"/api/v1/cameras/{junior}/snapshot").status_code == 404


def test_admin_limited_to_one_site_cannot_add_cameras_elsewhere(
    school, checks, go2rtc, make_account
) -> None:
    owner, campus, annex = school
    admin = make_account("it@gvs.test", org=owner.org, role="admin", sites=[campus])
    assert add_camera(admin.client, annex).status_code == 400  # annex isn't a valid choice
    assert add_camera(admin.client, campus).status_code == 201


def test_other_orgs_cannot_see_or_touch_cameras(school, checks, go2rtc, make_account) -> None:
    owner, campus, _ = school
    camera_id = add_camera(owner.client, campus).data["id"]
    stranger = make_account("x@other.test")
    url = f"/api/v1/cameras/{camera_id}"
    assert stranger.client.get(url).status_code == 404
    assert stranger.client.get(f"{url}/snapshot").status_code == 404
    assert stranger.client.delete(url).status_code == 404
    assert add_camera(stranger.client, campus).status_code == 400  # not their site


def test_changing_urls_rechecks_them(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    url = f"/api/v1/cameras/{add_camera(owner.client, campus).data['id']}"
    new_main = "rtsp://admin:New-Pass-2026@192.168.1.21/live"
    checks[new_main] = service.CheckResult(False, "not_found", "No stream at this path.")
    failed = owner.client.patch(url, {"rtsp_main": new_main}, format="json")
    assert failed.status_code == 400
    assert Camera.objects.get().main_url == MAIN  # unchanged

    del checks[new_main]
    ok = owner.client.patch(url, {"rtsp_main": new_main, "detect_fps": 3}, format="json")
    assert ok.status_code == 200 and ok.data["detect_fps"] == 3
    assert Camera.objects.get().main_url == new_main
    entry = AuditLog.objects.for_org(owner.org).get(action="camera.updated")
    assert entry.metadata["stream_urls_changed"] is True and "New-Pass" not in str(entry.metadata)


def test_rename_without_urls_skips_the_check(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    url = f"/api/v1/cameras/{add_camera(owner.client, campus).data['id']}"
    checks[MAIN] = service.CheckResult(False, "timeout", "No answer.")  # camera offline now
    response = owner.client.patch(url, {"name": "Front gate"}, format="json")
    assert response.status_code == 200 and response.data["name"] == "Front gate"


def test_detect_fps_limits(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    assert add_camera(owner.client, campus, detect_fps=30).status_code == 400


def test_delete_camera_removes_its_snapshot(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    camera_id = add_camera(owner.client, campus).data["id"]
    camera = Camera.objects.get(pk=camera_id)
    assert service.stored_snapshot(camera)
    assert owner.client.delete(f"/api/v1/cameras/{camera_id}").status_code == 204
    assert service.stored_snapshot(camera) is None
    assert owner.client.delete(f"/api/v1/sites/{campus.id}").status_code == 204


def test_site_with_cameras_cannot_be_deleted(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    add_camera(owner.client, campus)
    response = owner.client.delete(f"/api/v1/sites/{campus.id}")
    assert response.status_code == 409 and response.data["error"]["code"] == "site_not_empty"


def test_snapshot_endpoint(school, checks, go2rtc) -> None:
    owner, campus, _ = school
    url = f"/api/v1/cameras/{add_camera(owner.client, campus).data['id']}/snapshot"
    stored = owner.client.get(url)
    assert stored.status_code == 200 and stored["Content-Type"] == "image/jpeg"
    assert stored["Cache-Control"] == "private, no-store"
    assert stored.content[:2] == b"\xff\xd8"

    go2rtc.down.add(MAIN)
    assert owner.client.get(url).status_code == 200  # the stored one still works
    fresh = owner.client.get(f"{url}?fresh=1")
    assert fresh.status_code == 502 and fresh.data["error"]["code"] == "camera_unavailable"


def test_test_endpoint_returns_check_and_preview(school, checks, go2rtc) -> None:
    owner, _, _ = school
    response = owner.client.post("/api/v1/cameras/test", {"rtsp_url": MAIN}, format="json")
    assert response.status_code == 200
    body = response.data
    assert (body["ok"], body["codec"], body["width"], body["height"]) == (True, "H264", 640, 360)
    assert base64.b64decode(body["snapshot_jpeg_base64"])[:2] == b"\xff\xd8"
    assert go2rtc.streams == {}  # the preview stream is gone

    checks[MAIN] = service.CheckResult(False, "unreachable", "Can't reach 192.168.1.20:554.")
    failed = owner.client.post("/api/v1/cameras/test", {"rtsp_url": MAIN}, format="json").data
    assert (failed["ok"], failed["error_code"], failed["snapshot_jpeg_base64"]) == (
        False,
        "unreachable",
        None,
    )
