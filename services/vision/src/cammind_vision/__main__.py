"""CamMind vision worker.

    cammind-vision run --cameras cam_a,cam_b       watch cameras, report events (step 3)
    cammind-vision detect SOURCE [--save DIR]      motion -> detection -> tracking on one stream
    cammind-vision bench FILE --models a,b         detector speed and counts on a clip

One long-running process per group of cameras (docs/03-architecture.md, "Why the vision
worker is not a Celery task").
"""

import argparse
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

from . import __version__

log = logging.getLogger("cammind_vision")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cammind-vision", description="CamMind vision worker")
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

    detect = sub.add_parser("detect", help="Run motion, detection and tracking on one stream")
    detect.add_argument("source", help="rtsp://... or a video file")
    detect.add_argument("--model", default="dfine-s")
    detect.add_argument("--fps", type=float, default=5.0, help="Sample rate")
    detect.add_argument("--seconds", type=float, default=20.0, help="Stop after this long")
    detect.add_argument("--classes", default="person,car,truck,bus,bicycle,motorcycle")
    detect.add_argument("--save", type=Path, help="Write annotated frames here")

    bench = sub.add_parser("bench", help="Compare detectors on a video file")
    bench.add_argument("source", help="A video file")
    bench.add_argument("--models", default="dfine-n,dfine-s,rtdetrv2-s")
    bench.add_argument("--frames", type=int, default=40)
    return parser


def cmd_run(args: argparse.Namespace) -> int:
    cameras = [c for c in args.cameras.split(",") if c]
    log.info("cammind-vision %s: core=%s cameras=%s", __version__, args.core, cameras or "assigned")
    log.warning("Reporting events to the core arrives in step 3 (docs/20-demo-sprint.md).")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    import cv2

    from .annotate import annotate
    from .detect import Detector
    from .ingest import StreamReader
    from .pipeline import CameraPipeline

    detector = Detector(args.model, classes=set(args.classes.split(",")))
    log.info("detector %s on %s", args.model, detector.provider)
    reader = StreamReader("cli", args.source, args.fps, realtime=False)
    pipeline = CameraPipeline(detector, args.fps)
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
    seen: dict[int, str] = {}
    started = time.monotonic()
    first_ts = None
    for frame in reader:
        first_ts = first_ts or frame.ts
        elapsed = (frame.ts - first_ts).total_seconds()
        step = pipeline.process(frame)
        for track in step.tracks:
            if track.id not in seen:
                seen[track.id] = track.class_name
                log.info(
                    "t=%5.1fs new track #%d %s (%.2f)",
                    elapsed,
                    track.id,
                    track.class_name,
                    track.confidence,
                )
        if args.save and step.detected and frame.index % 5 == 0:
            path = args.save / f"frame-{frame.index:05d}.jpg"
            cv2.imwrite(str(path), annotate(frame.image, step.tracks))
        if elapsed >= args.seconds:
            break
    stats = pipeline.stats
    print(
        f"\n{args.model} on {detector.provider}: {stats.frames} frames in "
        f"{time.monotonic() - started:.1f}s, detector ran on {stats.gate_pass_rate:.0%} of them, "
        f"{stats.detector_ms_p(50):.0f} ms p50 / {stats.detector_ms_p(95):.0f} ms p95"
    )
    print(f"tracks: {len(seen)} {dict(Counter(seen.values()))}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    import numpy as np

    from .detect import Detector
    from .ingest import StreamReader

    frames = []
    for frame in StreamReader("bench", args.source, 2.0, realtime=False):
        frames.append(frame.image)
        if len(frames) >= args.frames:
            break
    print(f"{len(frames)} frames of {frames[0].shape[1]}x{frames[0].shape[0]} from {args.source}")
    print(f"{'model':<12}{'device':<24}{'p50 ms':>8}{'p95 ms':>8}{'people/frame':>14}")
    for name in args.models.split(","):
        detector = Detector(name, classes={"person"})
        detector.detect(frames[:1])  # warm-up
        times, people = [], []
        for image in frames:
            people.append(len(detector.detect([image])[0]))
            times.append(detector.last_ms)
        print(
            f"{name:<12}{detector.provider:<24}{np.percentile(times, 50):>8.0f}"
            f"{np.percentile(times, 95):>8.0f}{np.mean(people):>14.2f}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    commands = {"run": cmd_run, "detect": cmd_detect, "bench": cmd_bench}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
