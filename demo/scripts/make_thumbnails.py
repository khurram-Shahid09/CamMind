"""YouTube thumbnails (1280x720) for the overview and the four use-case videos.
Output: demo/out/thumbnails/*.png

    uv run --no-project --with imageio-ffmpeg python demo/scripts/make_thumbnails.py
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "demo" / "out" / "shots"
OUT = ROOT / "demo" / "out" / "thumbnails"
FF = imageio_ffmpeg.get_ffmpeg_exe()
BOLD = "'C\\:/Windows/Fonts/segoeuib.ttf'"
SEMI = "'C\\:/Windows/Fonts/seguisb.ttf'"

THUMBS = {
    # name: (screenshot, tag, line 1, line 2, accent colour)
    "cammind-overview": ("06-event-door.png", "TELL CAMERAS WHAT TO WATCH", "AI CCTV in", "Plain English", "0x38bdf8"),
    "cammind-home": ("home-detail.png", "USE CASE 1 · HOME", "Back Door", "Alert", "0x38bdf8"),
    "cammind-school": ("school-detail.png", "USE CASE 2 · SCHOOL", "Gate Entry", "Alert", "0x4ade80"),
    "cammind-factory": ("factory-detail.png", "USE CASE 3 · FACTORY", "No Helmet?", "AI Checks It", "0xfbbf24"),
    "cammind-retail": ("retail-detail.png", "USE CASE 4 · RETAIL", "Busy Shop", "Floor Alert", "0xf87171"),
}  # fmt: skip


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = OUT / "text"
    text.mkdir(exist_ok=True)
    for name, (shot, tag, line1, line2, accent) in THUMBS.items():
        for key, value in (("tag", tag), ("l1", line1), ("l2", line2), ("brand", "CamMind")):
            (text / f"{name}-{key}.txt").write_text(value, encoding="utf-8")
        t = f"text/{name}"
        # The event snapshot (camera image with boxes) fills the frame; the title sits on a
        # dark panel on the left. Screenshots are 1440x900 with the snapshot at (161, 170).
        filters = (
            "crop=728:410:162:170,scale=1280:720:flags=lanczos,"
            "drawbox=x=0:y=0:w=690:h=720:color=0x0a0c10@0.88:t=fill,"
            f"drawbox=x=60:y=150:w=10:h=330:color={accent}:t=fill,"
            f"drawtext=fontfile={SEMI}:textfile={t}-tag.txt:fontsize=30:fontcolor={accent}:x=95:y=150,"
            f"drawtext=fontfile={BOLD}:textfile={t}-l1.txt:fontsize=88:fontcolor=white:x=92:y=200,"
            f"drawtext=fontfile={BOLD}:textfile={t}-l2.txt:fontsize=88:fontcolor=white:x=92:y=305,"
            f"drawtext=fontfile={BOLD}:textfile={t}-brand.txt:fontsize=44:fontcolor=white:x=95:y=600,"
            f"drawbox=x=96:y=660:w=180:h=6:color={accent}:t=fill"
        )
        subprocess.run(
            [FF, "-y", "-loglevel", "error", "-i", str(SHOTS / shot), "-vf", filters,
             "-frames:v", "1", f"{name}.png"],
            cwd=OUT, check=True,
        )  # fmt: skip
        print(OUT / f"{name}.png")
    for file in text.iterdir():
        file.unlink()
    text.rmdir()


if __name__ == "__main__":
    main()
