import pytest

from cammind_vision.__main__ import build_parser, main


def test_run_reads_sources() -> None:
    args = build_parser().parse_args(["run", "--source", "cam_a=clip.mp4"])
    assert args.source == ["cam_a=clip.mp4"]
    assert args.core.startswith("http")


def test_run_needs_a_token(monkeypatch) -> None:
    monkeypatch.delenv("WORKER_TOKEN", raising=False)
    assert main(["run", "--token", ""]) == 2


def test_command_is_required() -> None:
    with pytest.raises(SystemExit):
        main([])
