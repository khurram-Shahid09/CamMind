"""Download the development clips for the five test cameras (stdlib only).

    python infra/test-streams/fetch_clips.py

Clips are Intel's sample videos (CC BY 4.0, attribution in SOURCES.md). They stand in until
self-recorded demo footage replaces them; a file already in clips/ is never overwritten.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master"
CLIPS = {
    # camera name: (source file, sha256)
    "home_backdoor": (
        "one-by-one-person-detection.mp4",
        "a5964aa259099a482a8b360ffc2c57b5a30f84d5919236a4dad01f8e929ac07c",
    ),
    "school_gate": (
        "person-bicycle-car-detection.mp4",
        "452b11b7e0efbd019f1d9570d0c790e90416ad4ad29eec6003872d08443140ef",
    ),
    "school_parking": (
        "people-detection.mp4",
        "18ffe8672d741e3e29c9d891d22c59d453720b086c25b35c88b393d55f92f693",
    ),
    "workshop_press": (
        "worker-zone-detection.mp4",
        "b8b58b8100a81600bc42ee7ee082ced777b12a32a3619139ef289d27cbdcd284",
    ),
    "office_reception": (
        "store-aisle-detection.mp4",
        "3526fee39cac70d6366471e4324a6d63b337c8f8ab99c015521bee0d60ed6e04",
    ),
}
FOLDER = Path(__file__).parent / "clips"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    FOLDER.mkdir(exist_ok=True)
    for name, (source, expected) in CLIPS.items():
        target = FOLDER / f"{name}.mp4"
        if target.exists():
            print(f"keep  {target.name}")
            continue
        partial = target.with_suffix(".part")
        print(f"fetch {source} -> {target.name}")
        urllib.request.urlretrieve(f"{BASE}/{source}", partial)  # noqa: S310  # fixed https URL
        actual = sha256(partial)
        if expected and actual != expected:
            partial.unlink()
            print(f"  checksum mismatch for {source}: {actual}", file=sys.stderr)
            return 1
        partial.rename(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
