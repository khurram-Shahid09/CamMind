import pytest

from accounts.models import Organization, Site
from cameras.go2rtc import Go2rtcError
from cameras.service import preview_snapshot, refresh_snapshot, stored_snapshot, sync_go2rtc

pytestmark = pytest.mark.django_db


@pytest.fixture
def site() -> Site:
    org = Organization.objects.create(name="Green Valley School")
    return Site.objects.create(org=org, name="Main campus")


def test_each_camera_gets_a_detection_and_an_hd_stream(go2rtc, site, make_camera) -> None:
    with_sub = make_camera(
        site, "Gate", main="rtsp://u:p@10.0.0.5/main", sub="rtsp://u:p@10.0.0.5/sub"
    )
    only_main = make_camera(site, "Lobby", main="rtsp://10.0.0.6/live")
    report = sync_go2rtc()
    assert go2rtc.streams == {
        with_sub.id: ["rtsp://u:p@10.0.0.5/sub"],
        f"{with_sub.id}_hd": ["rtsp://u:p@10.0.0.5/main"],
        only_main.id: ["rtsp://10.0.0.6/live"],
        f"{only_main.id}_hd": ["rtsp://10.0.0.6/live"],
    }
    assert len(report.added) == 4
    assert sync_go2rtc().added == []  # nothing to do the second time


def test_sync_updates_changed_urls_and_removes_only_its_own_streams(
    go2rtc, site, make_camera
) -> None:
    camera = make_camera(site)
    disabled = make_camera(site, "Old", main="rtsp://10.0.0.9/x")
    disabled.enabled = False
    disabled.save()
    go2rtc.streams = {
        camera.id: ["rtsp://u:p@10.0.0.5/old"],
        "cam_01DELETEDCAMERA0000000000": ["rtsp://x/y"],
        "preview_abc": ["rtsp://x/z"],
        "doorbell": ["rtsp://someone-elses/stream"],  # added by hand: left alone
    }
    report = sync_go2rtc()
    assert report.updated == [camera.id]
    assert set(report.removed) == {"cam_01DELETEDCAMERA0000000000", "preview_abc"}
    assert "doorbell" in go2rtc.streams
    assert disabled.id not in go2rtc.streams


def test_refresh_snapshot_stores_the_frame_and_its_size(go2rtc, site, make_camera) -> None:
    camera = make_camera(site)
    jpeg = refresh_snapshot(camera)
    camera.refresh_from_db()
    assert stored_snapshot(camera) == jpeg
    assert camera.snapshot_key == f"{site.org_id}/cameras/{camera.id}/snapshot.jpg"
    assert (camera.stream_meta["width"], camera.stream_meta["height"]) == (640, 360)
    assert camera.snapshot_at is not None


def test_no_frame_is_an_error(go2rtc, site, make_camera) -> None:
    camera = make_camera(site)
    go2rtc.down.add("rtsp://u:p@10.0.0.5/main")
    with pytest.raises(Go2rtcError, match="no frame"):
        refresh_snapshot(camera)


def test_preview_cleans_up_its_temporary_stream(go2rtc) -> None:
    assert preview_snapshot("rtsp://10.0.0.7/live")
    assert go2rtc.streams == {}
    go2rtc.down.add("rtsp://10.0.0.8/live")
    assert preview_snapshot("rtsp://10.0.0.8/live") is None
    assert go2rtc.streams == {}


def test_sync_task_survives_go2rtc_being_down(settings, site, make_camera, caplog) -> None:
    from cameras.tasks import sync_go2rtc_task

    settings.GO2RTC_URL = "http://127.0.0.1:9"  # nothing listens on the discard port
    make_camera(site)
    sync_go2rtc_task()  # logs and returns; beat retries in a minute
    assert "go2rtc sync skipped" in caplog.text
