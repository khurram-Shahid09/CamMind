"""Record the demo story in the real dashboard (docs/18-demo-script.md).

Produces demo/out/raw/main.webm with marks.json (seconds into the clip) and stills in
demo/out/shots/. Everything is live: the vision worker watches the looping test cameras,
the LLM compiles the typed rules and checks the helmet crops.

Before running (see demo/README.md): docker compose with --profile test-streams, then
API, Celery, the vision worker and the dashboard (next start on :3200), and:
    cd services/core && uv run python manage.py prepare_demo
    uv run --no-project --with playwright python ../../demo/scripts/capture.py
"""

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "demo" / "out" / "raw"
SHOTS = ROOT / "demo" / "out" / "shots"
BASE = "http://localhost:3200"
SIZE = {"width": 1440, "height": 900}
CURSOR = (Path(__file__).with_name("cursor.js")).read_text(encoding="utf-8")
RULE = "Alert me if anyone stands at the back door"
REFUSED = "Tell me when my brother Ali comes home"


def env(name: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].split("#")[0].strip()
    raise SystemExit(f"{name} missing in .env")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    marks: dict[str, float] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport=SIZE, record_video_dir=str(RAW / "tmp"), record_video_size=SIZE
        )
        context.add_init_script(CURSOR)
        page = context.new_page()
        t0 = time.monotonic()

        def mark(key: str) -> None:
            marks[key] = round(time.monotonic() - t0, 2)
            print(f"{marks[key]:6.1f}s {key}", flush=True)

        def pause(seconds: float) -> None:
            page.wait_for_timeout(int(seconds * 1000))

        def point(selector: str, click: bool = True) -> None:
            box = page.locator(selector).first.bounding_box()
            assert box, selector
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25)
            pause(0.3)
            if click:
                page.mouse.down()
                page.mouse.up()

        def shot(name: str) -> None:
            page.screenshot(path=str(SHOTS / f"{name}.png"))

        # Sign in
        page.goto(f"{BASE}/login")
        page.fill('input[name="email"]', "owner@cammind.test")
        page.fill('input[name="password"]', env("DEMO_PASSWORD"))
        point("button:has-text('Sign in')")
        page.wait_for_url(f"{BASE}/live")
        mark("live")
        pause(7)
        shot("01-live")

        # Type a rule in plain English
        point("a:has-text('Rules')")
        page.wait_for_url(f"{BASE}/rules")
        mark("rules")
        pause(1.5)
        page.select_option('select[aria-label="Site"]', label="Home")
        point("textarea")
        page.keyboard.type(RULE, delay=45)
        pause(0.6)
        point("button:has-text('Understand this rule')")
        mark("compile")
        page.wait_for_selector('[data-testid="compiled"]', timeout=90_000)
        mark("compiled")
        pause(4.5)
        shot("02-rule-understood")
        point("button:has-text('Show JSON')")
        pause(3.5)
        shot("03-rule-json")
        point("button:has-text('Activate')")
        page.wait_for_selector("text=Rule activated", timeout=30_000)
        mark("activated")
        pause(2.5)

        # A request it refuses
        page.fill("textarea", "")
        point("textarea")
        page.keyboard.type(REFUSED, delay=45)
        point("button:has-text('Understand this rule')")
        mark("refuse")
        page.wait_for_selector("text=Can't do this", timeout=90_000)
        mark("refused")
        pause(4.5)
        shot("04-refused")

        # The event arrives
        point("a:has-text('Events')")
        page.wait_for_url(f"{BASE}/events")
        mark("events")
        page.wait_for_selector("li:has-text('back door')", timeout=180_000)
        mark("event_arrived")
        pause(3)
        shot("05-events")
        point("li:has-text('back door') a")
        page.wait_for_url(f"{BASE}/events/*")
        mark("door_detail")
        pause(5)
        shot("06-event-door")

        # The helmet check: the AI looked, saw a hard hat, no alert
        page.goto(f"{BASE}/events?all=1")
        mark("dismissed_list")
        pause(2)
        point("li:has-text('AI: no issue') a")
        page.wait_for_url(f"{BASE}/events/*")
        mark("helmet_detail")
        pause(7)
        shot("07-event-helmet")

        # The gate crossing
        page.goto(f"{BASE}/events")
        pause(1)
        if page.locator("li:has-text('Gate line')").count():
            point("li:has-text('Gate line') a")
            page.wait_for_url(f"{BASE}/events/*")
            mark("gate_detail")
            pause(5)
            shot("08-event-gate")
        mark("end")

        video = page.video
        context.close()
        browser.close()
        assert video
        Path(video.path()).replace(RAW / "main.webm")
    (RAW / "marks.json").write_text(json.dumps({"main": marks}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
