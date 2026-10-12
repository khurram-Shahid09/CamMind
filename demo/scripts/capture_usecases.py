"""Record one short demo per use case (home, school, factory, retail) in the real dashboard.

Each clip: the cameras, the rule typed in plain English, what CamMind understood, activation,
then the real event the worker raises from the looping test camera, and its evidence.
Writes demo/out/raw/<case>.webm, adds the time marks to marks.json, stills to shots/<case>-*.png.

    cd services/core && uv run python manage.py prepare_demo --clean
    uv run --no-project --with playwright python ../../demo/scripts/capture_usecases.py [case ...]
"""

import json
import sys
import time
from pathlib import Path

from capture import BASE, CURSOR, RAW, SHOTS, SIZE, env
from playwright.sync_api import sync_playwright

CASES = {
    "home": {
        "site": "Home",
        "rule": "Alert me if anyone stands at the back door",
        "refuse": "Tell me when my brother Ali comes home",
        "events": "/events",
    },
    "school": {
        "site": "Green Valley School",
        "rule": "Tell security if anyone enters the campus through the gate",
        "events": "/events",
    },
    "factory": {
        "site": "Workshop",
        "rule": "Flag any worker in the press area without a helmet",
        "events": "/events?all=1",  # the AI saw hard hats: dismissed events are shown here
    },
    "retail": {
        "site": "Workshop",
        "rule": "Alert me if more than 2 people are on the shop floor at the same time",
        "events": "/events",
    },
}


def record(browser, case: str, spec: dict) -> dict[str, float]:
    context = browser.new_context(
        viewport=SIZE, record_video_dir=str(RAW / "tmp"), record_video_size=SIZE
    )
    context.add_init_script(CURSOR)
    page = context.new_page()
    marks: dict[str, float] = {}
    t0 = time.monotonic()

    def mark(key: str) -> None:
        marks[key] = round(time.monotonic() - t0, 2)
        print(f"{case:8s}{marks[key]:6.1f}s {key}", flush=True)

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
        page.screenshot(path=str(SHOTS / f"{case}-{name}.png"))

    page.goto(f"{BASE}/login")
    page.fill('input[name="email"]', "owner@cammind.test")
    page.fill('input[name="password"]', env("DEMO_PASSWORD"))
    page.click("button:has-text('Sign in')")
    page.wait_for_url(f"{BASE}/live")
    pause(3)  # frames load
    mark("live")
    pause(5)

    point("a:has-text('Rules')")
    page.wait_for_url(f"{BASE}/rules")
    page.select_option('select[aria-label="Site"]', label=spec["site"])
    mark("rules")
    point("textarea")
    page.keyboard.type(spec["rule"], delay=40)
    pause(0.5)
    point("button:has-text('Understand this rule')")
    mark("compile")
    page.wait_for_selector('[data-testid="compiled"]', timeout=120_000)
    mark("compiled")
    pause(5)
    shot("understood")
    point("button:has-text('Activate')")
    page.wait_for_selector("text=Rule activated", timeout=30_000)
    mark("activated")
    pause(2)

    if spec.get("refuse"):
        page.fill("textarea", "")
        point("textarea")
        page.keyboard.type(spec["refuse"], delay=40)
        point("button:has-text('Understand this rule')")
        mark("refuse")
        page.wait_for_selector("text=Can't do this", timeout=120_000)
        mark("refused")
        pause(4.5)
        shot("refused")

    page.goto(f"{BASE}{spec['events']}")
    mark("events")
    item = f"li:has-text('{spec['rule'][:40]}')"
    page.wait_for_selector(item, timeout=240_000)
    mark("event_arrived")
    pause(3)
    shot("events")
    point(f"{item} a")
    page.wait_for_url(f"{BASE}/events/*")
    mark("detail")
    pause(7)
    shot("detail")
    mark("end")

    video = page.video
    context.close()
    assert video
    Path(video.path()).replace(RAW / f"{case}.webm")
    return marks


def main() -> None:
    cases = sys.argv[1:] or list(CASES)
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = RAW / "marks.json"
    all_marks = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for case in cases:
            all_marks[case] = record(browser, case, CASES[case])
            path.write_text(json.dumps(all_marks, indent=2), encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    main()
