from datetime import UTC, datetime
from pathlib import Path

import av
import numpy as np
import pytest

from cammind_vision import detect as detect_module
from cammind_vision.detect import CLASS_NAMES, MODELS, Detector, models_dir
from cammind_vision.ingest import StreamReader

T0 = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """3 seconds at 10 fps of a square sliding right."""
    path = tmp_path / "clip.mp4"
    with av.open(str(path), "w") as out:
        stream = out.add_stream("libx264", rate=10)
        stream.width, stream.height, stream.pix_fmt = 320, 180, "yuv420p"
        for i in range(30):
            image = np.zeros((180, 320, 3), np.uint8)
            image[60:120, i * 8 : i * 8 + 40] = 255
            for packet in stream.encode(av.VideoFrame.from_ndarray(image, format="bgr24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return path


def test_file_reader_samples_and_stamps_with_the_file_clock(clip: Path) -> None:
    reader = StreamReader("cam_test", str(clip), sample_fps=5, realtime=False, start=T0)
    frames = list(reader)
    assert 14 <= len(frames) <= 16  # 3 s at 5 fps
    assert frames[0].ts == T0
    assert [f.index for f in frames] == list(range(len(frames)))
    gaps = {
        round((b.ts - a.ts).total_seconds(), 2) for a, b in zip(frames, frames[1:], strict=False)
    }
    assert gaps == {0.2}
    assert frames[0].image.shape == (180, 320, 3)
    assert reader.health.state == "ended" and reader.health.decoded == 30


def test_missing_file_ends_without_raising(tmp_path: Path) -> None:
    reader = StreamReader("cam_test", str(tmp_path / "nope.mp4"), realtime=False)
    assert list(reader) == []
    assert reader.health.state == "ended"


def test_live_source_reconnects_with_backoff() -> None:
    waits: list[float] = []
    reader = StreamReader("cam_test", "rtsp://127.0.0.1:9/none", sleep=waits.append)

    def stop_after_three(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 3:
            reader.stop()

    reader._sleep = stop_after_three
    assert list(reader) == []
    assert waits == [1, 2, 5]
    assert reader.health.state == "reconnecting" and reader.health.reconnects == 3


def test_class_list_matches_coco() -> None:
    assert len(CLASS_NAMES) == 80
    assert (CLASS_NAMES[0], CLASS_NAMES[2], CLASS_NAMES[67], CLASS_NAMES[79]) == (
        "person",
        "car",
        "cell phone",
        "toothbrush",
    )


def bare_detector(classes: set[str] | None = None) -> Detector:
    """A Detector without a model file, to test decoding."""
    detector = Detector.__new__(Detector)
    detector.min_confidence = 0.5
    detector.class_filter = np.array([CLASS_NAMES.index(c) for c in classes]) if classes else None
    return detector


def test_decode_maps_relative_boxes_to_frame_pixels_and_filters() -> None:
    logits = np.full((3, 80), -10.0, np.float32)
    logits[0, 0] = 3.0  # person, confident
    logits[1, 2] = 3.0  # car, confident
    logits[2, 0] = -1.0  # person, below threshold
    boxes = np.array([[0.5, 0.5, 0.2, 0.4], [0.25, 0.75, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1]])
    found = bare_detector()._decode(logits, boxes, 1920, 1080)
    assert found.names() == ["person", "car"]
    assert found.boxes[0].tolist() == pytest.approx([768, 324, 1152, 756])

    people = bare_detector({"person"})._decode(logits, boxes, 1920, 1080)
    assert people.names() == ["person"]


def test_models_are_pinned(monkeypatch, tmp_path) -> None:
    for spec in MODELS.values():
        assert len(spec.revision) == 40 and len(spec.sha256) == 64
    monkeypatch.setenv("CAMMIND_MODELS_DIR", str(tmp_path))
    assert models_dir() == tmp_path


def test_checksum_mismatch_deletes_the_download(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CAMMIND_MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(
        detect_module.urllib.request, "urlretrieve", lambda url, path: Path(path).write_bytes(b"x")
    )
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        detect_module.ensure_model("dfine-n")
    assert list(tmp_path.iterdir()) == []
