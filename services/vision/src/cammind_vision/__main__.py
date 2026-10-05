"""``python -m cammind_vision run --cameras cam_a,cam_b``.

One long-running process per group of cameras (docs/03-architecture.md, "Why the vision
worker is not a Celery task"). Intake, detection and the rule engine arrive in days 3-5.
"""

import argparse
import logging
import os
import sys

from . import __version__

log = logging.getLogger("cammind_vision")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cammind-vision", description=__doc__)
    parser.add_argument("--version", action="version", version=f"cammind-vision {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Watch cameras and report events to the core")
    run.add_argument(
        "--core",
        default=os.environ.get("CAMMIND_CORE_URL", "http://localhost:8200"),
        help="Core API base URL",
    )
    run.add_argument(
        "--restream",
        default=os.environ.get("CAMMIND_RESTREAM_URL", "rtsp://localhost:8554"),
        help="go2rtc RTSP base URL; cameras are read from <restream>/<camera_id>",
    )
    run.add_argument(
        "--cameras",
        default="",
        help="Comma-separated camera ids (default: every camera assigned to this worker)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cameras = [c for c in args.cameras.split(",") if c]
    log.info(
        "cammind-vision %s: core=%s restream=%s cameras=%s",
        __version__,
        args.core,
        args.restream,
        cameras or "assigned",
    )
    log.warning("The video pipeline isn't built yet (docs/15-roadmap-build-plan.md, day 3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
