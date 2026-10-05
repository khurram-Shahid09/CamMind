import pytest

from cammind_vision.__main__ import build_parser, main


def test_run_reads_camera_list() -> None:
    args = build_parser().parse_args(["run", "--cameras", "cam_a,cam_b"])
    assert args.cameras == "cam_a,cam_b"
    assert args.core.startswith("http")


def test_run_exits_cleanly() -> None:
    assert main(["run"]) == 0


def test_command_is_required() -> None:
    with pytest.raises(SystemExit):
        main([])
