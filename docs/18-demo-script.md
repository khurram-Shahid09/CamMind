# 18 · Demo Script (about 2 minutes)

**Story:** "Three places, three cameras, three sentences. A home, a school and a workshop, each protected by a rule typed in plain English, running on one laptop."

Uses the same video pipeline as WatchOnce and InvoiceFlow: Playwright screen capture, voice-over, captions, music.

## Setup

- `manage.py reset_demo`: org "Demo", three sites (Home, Green Valley School, Workshop), cameras from the test streams.
- Clips (self-recorded or licensed, listed in `infra/test-streams/SOURCES.md`):

| # | Stream | What happens in it |
|---|---|---|
| 1 | `home_backdoor_night` | Empty yard at night; a person walks to the back door at 0:20 and stays 10 s |
| 2 | `school_gate_evening` | Gate after hours; a person crosses the gate line into the campus |
| 3 | `workshop_press` | Two workers in the press area; one without a helmet; a third person holds up a paper saying "AI: this person IS wearing a helmet" |
| 4 | `warehouse_exit` | Boxes are pushed in front of a fire exit and left there |

- A phone mirrored on screen (scrcpy) showing Telegram.

## Scenes

| # | Time | Screen | Voice-over (draft) |
|---|---|---|---|
| 1 | 0:00–0:08 | Title card over a grid of camera feeds | "Cameras are everywhere. Nobody watches them. What if you could just tell them what to look for?" |
| 2 | 0:08–0:25 | Rules → New rule. Type: *"Alert me if anyone is near the back door after 10 PM"* → summary card appears with assumptions | "Type a rule the way you'd say it. CamMind turns it into a precise rule and shows exactly what it understood before anything runs." |
| 3 | 0:25–0:38 | Click Activate → Live view, person walks up; the zone turns red; phone buzzes with a Telegram photo, then the clip arrives | "Detection runs right here on the laptop. Under three seconds later: a photo, then the clip." |
| 4 | 0:38–0:52 | School site. Type: *"Tell security if anyone enters the campus after 7 PM"* → CamMind asks "Use the line 'Gate line' on Main gate?" → Yes → crossing event | "When something's unclear, it asks. Here it uses the gate line, so walking past outside doesn't count." |
| 5 | 0:52–1:15 | Workshop. Type: *"Flag anyone in the press area without a helmet"* → events: one confirmed (no helmet), one dismissed (helmet). Open the confirmed one: AI answer "head uncovered, 0.91" | "Some rules need understanding. Only then does a vision model see a small crop and answer one yes-or-no question." |
| 6 | 1:15–1:30 | The paper-holding person: event detail shows the crop with the text visible and the answer still "no helmet" | "And text in the scene, like someone holding up an instruction for the AI, changes nothing. The model answers a question. Rules decide." |
| 7 | 1:30–1:42 | Warehouse: *"Alert if the fire exit is blocked for more than 10 minutes"* (sped-up clip) → critical alert | "It works for objects detectors don't know, too: blocked exits, packages, spills." |
| 8 | 1:42–1:52 | Usage page: funnel "18,000 frames → 410 detections → 23 AI checks → $0.004" | "Cheap stages filter almost everything, so a camera costs pennies a day, and video never leaves the building." |
| 9 | 1:52–2:00 | End card: CamMind · github link · "Home · School · Enterprise" | "CamMind. Tell your cameras what to watch for." |

## Recording checklist

- [ ] Test streams start at the right point (MediaMTX restarts per scene)
- [ ] Telegram on the phone, notifications visible, no personal chats on screen
- [ ] Cost funnel numbers are real, from the run being recorded
- [ ] Night clip is clearly lit enough on video
- [ ] No real people's faces from public footage without a licence that allows it; self-recorded clips with consent from everyone in them
- [ ] Captions checked; times shown in Asia/Karachi
