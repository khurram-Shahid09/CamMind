"""One short video per use case, from the clips recorded by capture_usecases.py.
Output: demo/out/usecases/cammind-<case>.mp4 (about a minute each, voice-over and captions).

    uv run --no-project --with edge-tts --with imageio-ffmpeg --with numpy python demo/scripts/make_usecases.py [case ...]

Wording rules for the narration: plain words, no vendor names (the AI is any LLM the owner
chooses), and only what the product does today (alerts: Slack now; email and WhatsApp with
clips are on the roadmap, docs/20).
"""

import json
import sys

import make_demo as md
from make_demo import Segment, Sub

ALERTS_NOW = "CamMind alerts your team on Slack straight away, with a link to the evidence."
ALERTS_NEXT = "Email and WhatsApp alerts, with a short video clip, are next on the roadmap."
END_LINE = "Plain English in. Precise rules out. Alerts with evidence."


def card(name, voice, title, line, small, seconds=5.0) -> Segment:
    return Segment(name, voice, kind="card", min_seconds=seconds, card=(title, line, small))


def flow_card(name: str, steps: str, voice: str) -> Segment:
    return card(name, voice, "How it works", steps, "Video is processed on site · the AI only answers yes/no questions", 6.0)


def common(m: dict, rule: str) -> list[Segment]:
    return [
        Segment("type", f"You type the rule the way you'd say it to a guard: {rule}",
                "Step 1 · Type the rule in plain English",
                [Sub("CASE", m["rules"], m["compile"] + 1.0)]),
        Segment("understood",
                "An AI language model, and you can use any LLM, turns the sentence into a precise rule. It uses your real cameras and zones, and shows you exactly what it understood. Nothing runs until you click Activate.",
                "Step 2 · Check what CamMind understood, then activate",
                [Sub("CASE", m["compiled"], m["activated"] + 1.5)]),
    ]


def segments(case: str, m: dict) -> list[Segment]:
    if case == "home":
        out = [
            card("title", "", "Home security", "“Alert me if anyone stands at the back door”", "CamMind use case 1 · Home"),
            Segment("live", "This is a home with a camera on the back door. Ordinary motion alerts would ping you for every cat and shadow. With CamMind, you just say what you care about.",
                    "Any RTSP camera · the video stays at home", [Sub("CASE", m["live"], m["rules"])]),
            *common(m, "alert me if anyone stands at the back door."),
            Segment("refused", "It also knows its limits. It won't recognise specific people, so it says so, and suggests what it can do instead.",
                    "Privacy built in: no face recognition", [Sub("CASE", m["refused"] - 0.5, m["refused"] + 4.0)]),
            Segment("event", "Moments later, someone stops at the back door. CamMind spots the person, checks the rule, and creates one event with a snapshot. " + ALERTS_NOW,
                    "Step 3 · A person at the door → one event + Slack alert", [Sub("CASE", m["events"], m["detail"])]),
            Segment("detail", "Open it to see why it fired: the person, the zone, and the time. Mark it as confirmed or a false alarm, and CamMind learns which rules need tuning.",
                    "Evidence: snapshot, zone, reason, time", [Sub("CASE", m["detail"], m["end"])]),
            flow_card("flow", "Camera → person detected on site → in the back-door zone for 2 s → Slack alert",
                      "So the flow is simple. The camera feeds CamMind. A person is detected on your own computer. If they stay in the back-door zone, you get an alert. " + ALERTS_NEXT),
        ]
    elif case == "school":
        out = [
            card("title", "", "School safety", "“Tell security if anyone enters the campus through the gate”", "CamMind use case 2 · School"),
            Segment("live", "A school wants to know when someone walks in through the gate, without a guard watching screens all day.",
                    "One camera on the gate", [Sub("CASE", m["live"], m["rules"])]),
            *common(m, "tell security if anyone enters the campus through the gate."),
            Segment("event", "CamMind follows each person and notices the moment they cross the gate line. One crossing, one event. " + ALERTS_NOW,
                    "Step 3 · Someone crosses the gate line → event + Slack alert", [Sub("CASE", m["events"], m["detail"])]),
            Segment("detail", "The event shows who crossed, where, and when, so security can react straight away.",
                    "Evidence for security, in seconds", [Sub("CASE", m["detail"], m["end"])]),
            flow_card("flow", "Gate camera → each person tracked → crosses the gate line → alert to security",
                      "The flow: the gate camera feeds CamMind, each person is tracked, and crossing the line raises the alert. Schools can add time windows too, like only after school hours. " + ALERTS_NEXT),
        ]
    elif case == "factory":
        out = [
            card("title", "", "Factory safety", "“Flag any worker in the press area without a helmet”", "CamMind use case 3 · Factory"),
            Segment("live", "In a factory, the safety officer needs everyone in the press area to wear a helmet. A detector alone can't tell, so CamMind adds an AI check.",
                    "Safety rules that need understanding", [Sub("CASE", m["live"], m["rules"])]),
            *common(m, "flag any worker in the press area without a helmet."),
            Segment("event", "When a worker walks into the press area, CamMind sends only a small crop of that person to the AI, with one yes-or-no question: are they wearing a helmet?",
                    "Step 3 · One yes/no question about one crop", [Sub("CASE", m["events"], m["detail"])]),
            Segment("detail", "Here the AI answered yes: a yellow hard hat. So no alert, and no false alarm. Without a helmet, it would raise a critical alert to the safety team. The AI only answers the question. The rules decide what happens.",
                    "Hard hat seen → no false alarm. The rules decide.", [Sub("CASE", m["detail"], m["end"])]),
            flow_card("flow", "Camera → worker in the press area → AI checks the crop: helmet? → alert only if no",
                      "The flow: detect the worker on site, send one crop to the AI, and alert only when the answer is no. That keeps costs low and false alarms rare. " + ALERTS_NOW),
        ]
    else:  # retail
        out = [
            card("title", "", "Retail operations", "“Alert me if more than 2 people are on the shop floor at the same time”", "CamMind use case 4 · Retail"),
            Segment("live", "A shop manager wants to know when the floor gets busy, so they can send another staff member to help.",
                    "Know when the shop floor gets busy", [Sub("CASE", m["live"], m["rules"])]),
            *common(m, "alert me if more than two people are on the shop floor at the same time."),
            Segment("event", "CamMind counts the people on the shop floor in every frame. When the count goes above two and stays there, it raises one event. " + ALERTS_NOW,
                    "Step 3 · More than 2 people → one event + Slack alert", [Sub("CASE", m["events"], m["detail"])]),
            Segment("detail", "The snapshot shows the people it counted, so the manager can see the situation at a glance.",
                    "See exactly who was counted", [Sub("CASE", m["detail"], m["end"])]),
            flow_card("flow", "Shop camera → people counted on site → more than 2 for a few seconds → alert",
                      "The flow: count people on site, wait a few seconds so a passer-by doesn't trigger it, then alert. The same works for queues, empty counters or loitering. " + ALERTS_NEXT),
        ]
    out.append(card("end", f"CamMind. {END_LINE}", "CamMind", END_LINE, "github.com/khurram-Shahid09/CamMind"))
    for seg in out:
        seg.name = f"{case}-{seg.name}"
        for sub in seg.subs:
            sub.clip = case
    return out


def build(case: str) -> None:
    marks = json.loads((md.RAW / "marks.json").read_text(encoding="utf-8"))[case]
    built = []
    for seg in segments(case, marks):
        voice = md.make_voice(seg)
        built.append(md.build_segment(seg, voice))
        print(f"{seg.name:20s} {built[-1][1]:5.1f}s", flush=True)
    listing = md.EDIT / f"{case}-segments.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p, _ in built), encoding="utf-8")
    joined = md.EDIT / f"{case}-joined.mp4"
    md.run([md.FF, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])
    total = sum(s for _, s in built)
    music = md.make_music(total)
    out = md.ROOT / "demo" / "out" / "usecases" / f"cammind-{case}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    md.run([
        md.FF, "-y", "-i", str(joined), "-i", str(music), "-filter_complex",
        "[1:a]aresample=48000,volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
    ])  # fmt: skip
    print(f"{out} ({total:.0f}s)\n")


if __name__ == "__main__":
    md.EDIT.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or ["home", "school", "factory", "retail"]:
        build(name)
