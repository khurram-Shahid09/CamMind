# 01 · Product Vision

## One line

**Plain-English rules for any IP camera: CamMind watches the stream and only speaks up when the thing you described actually happens.**

## The problem

There are cameras in almost every home gate, school corridor, shop floor and warehouse. The footage is recorded and almost never watched. When something happens, someone scrolls through hours of video afterwards.

What people actually want is simple to say and hard to buy:

- "Tell me if someone is at the back door at night." Not every time a cat walks past.
- "Tell me if the fire exit is blocked for more than 10 minutes."
- "Tell me if a worker enters the press area without a helmet."

Today's options:

1. **Motion alerts.** Triggered by leaves, shadows, rain and headlights. Muted within days.
2. **Camera-brand "smart" detection.** Fixed categories (person, vehicle, package), tied to one brand and usually its cloud.
3. **Enterprise video analytics.** Powerful but expensive: per-camera licences, integrators, and every new rule is a project.
4. **"Just send it to GPT."** Streaming every frame to a cloud model costs dollars per camera-hour, adds seconds of latency and sends private video off site.

## Who it's for

| Persona | Pain | What they get |
|---|---|---|
| **Home owner / family** | Noisy alerts or no alerts; worried about kids, parents, deliveries | A handful of rules in their own words, alerts on Telegram with a clip |
| **School admin / principal** | Safety duty, few guards, many cameras nobody watches | Rules per campus and time table; alerts to the right staff; event log for incidents |
| **Shop / branch manager** | Queues, empty counters, theft, after-hours entry | Operational and security rules in one place |
| **Safety officer (factory, warehouse)** | Safety gear checks, restricted zones, blocked exits, audits | Safety rules with evidence clips and daily reports |
| **Security operator (enterprise)** | Dozens of feeds, alert fatigue | A ranked event queue with "confirm / false alarm" and a full audit trail |
| **IT / admin** | Another system on the network; privacy and legal risk | Runs on site, encrypted camera credentials, roles, retention, no face recognition |

**First market:** homes and small businesses that already own cheap RTSP cameras (Hikvision, Dahua, TP-Link Tapo, Reolink, EZVIZ, CP Plus), private schools, and small factories and warehouses. Pakistan, the Gulf and remote clients worldwide.

## Use cases

Each use case maps to a rule type from [05 · Rule spec](05-rule-spec.md). ✅ = in the MVP; ⏭ = later.

### Home
| Rule (as typed) | Rule type | MVP |
|---|---|---|
| "Alert me if someone is at the front door between 11 PM and 6 AM" | presence + zone + schedule | ✅ |
| "Tell me when a package is left at the door" | presence (object: package) | ✅ (via verification) |
| "Tell me if a package is taken from the door" | sequence: package present → absent while person present | ⏭ |
| "Notify me if my car leaves the driveway at night" | absence after presence | ✅ |
| "Alert me if a child goes past the gate" | line crossing | ✅ |
| "Tell me if someone falls in the living room" | verified state (fall) | ✅ |
| "Let me know if the dog is on the sofa" | presence + zone | ✅ |

### School
| Rule | Rule type | MVP |
|---|---|---|
| "Alert security if anyone enters the campus after 7 PM" | line crossing + schedule | ✅ |
| "Tell the principal if more than 15 students are in the parking lot during class hours" | count + zone + schedule | ✅ |
| "Alert if someone stays near the girls' washroom entrance for more than 2 minutes" | dwell | ✅ |
| "Notify if the gate guard post is empty for more than 5 minutes during school hours" | absence | ✅ |
| "Alert if there's a fight in the corridor" | verified action (multi-frame) | ✅ |
| "Tell me if a student climbs the boundary wall" | line crossing + verification | ✅ |
| "Daily report of how crowded the canteen was" | analytics | ⏭ |

### Retail & offices
| Rule | Rule type | MVP |
|---|---|---|
| "Alert if more than 6 people are in the checkout queue" | count + zone | ✅ |
| "Tell me if the counter is unattended for 3 minutes during opening hours" | absence + schedule | ✅ |
| "Alert if someone loiters near the stockroom door" | dwell | ✅ |
| "Notify if anyone is in the office after 9 PM" | presence + schedule | ✅ |
| "Alert if a bag is left alone in the lobby for 5 minutes" | unattended object | ⏭ |

### Factory, warehouse & enterprise
| Rule | Rule type | MVP |
|---|---|---|
| "Flag anyone in the press area without a helmet" | presence + zone + verification | ✅ |
| "Alert if the fire exit is blocked for more than 10 minutes" | verified state + dwell | ✅ |
| "Tell me if a person walks in the forklift lane" | presence + zone | ✅ |
| "Alert if two people pass the server room door on one entry" (tailgating) | sequence + count | ⏭ |
| "Alert if a truck is parked at dock 3 for more than 2 hours" | dwell (vehicle) | ✅ |
| "Detect smoke or fire" | verified state | ✅ (as a best-effort extra, never a replacement for fire alarms) |

## Positioning

| Alternative | Weakness CamMind addresses |
|---|---|
| Motion alerts / NVR apps | No understanding; constant false alarms |
| Brand "smart detection" | Fixed rules, one brand, vendor cloud |
| Frigate / Home Assistant | Great open source, but rules are YAML and automations; no plain-English rules; home-focused |
| Enterprise video analytics | Expensive, integrator-driven, slow to change rules |
| Cloud vision AI on every frame | Cost, latency and privacy |

**CamMind's stance:** *Cheap stages watch, rules decide, AI answers only the hard question, and people confirm what matters.*

## Principles

1. **Plain English in, precise rule out.** Every rule is compiled into a typed spec and shown back to the user before it runs. Raw text never runs.
2. **Deterministic decisions.** Whether an event fires is decided by the rule engine. The vision model only answers a yes/no question that the rule asks.
3. **Cheapest stage first.** Motion → detector → rule → AI. Each stage only passes on what it can't rule out.
4. **Evidence with every alert.** Snapshot, clip, rule, and the reason in one sentence.
5. **Video stays on site.** Processing is local. Cloud AI is opt-in, per camera, crops only, with a budget.
6. **No identities.** No face recognition, no person re-identification across cameras in the MVP.
7. **Fewer, better alerts.** Debounce, cooldown and feedback beat volume. One alert per incident, not one per frame.

## Success metrics

| Metric | MVP target (eval set) | Pilot target |
|---|---|---|
| Rule compiler: correct spec on the prompt set | ≥ 90% exact, 100% valid or asks a question | ≥ 85% accepted without edits |
| Event recall on labelled clips | ≥ 90% | ≥ 85% |
| Event precision on labelled clips | ≥ 90% | ≥ 80% (fewer than 3 false alarms per camera per day) |
| Alert latency (no verification), event → notification | p95 < 3 s | p95 < 5 s |
| Alert latency (with verification) | p95 < 8 s | p95 < 10 s |
| Frames reaching the vision LLM | < 0.5% | < 1% |
| AI cost | < $0.05 per camera-day with typical rules | < $0.10 |
| Cameras per CPU-only mini PC (4 cores, 720p, detect at 5 fps) | 4 | 4–8 |
| **Injection tests (text in the scene) that change an outcome** | **0** | **0** |

## Non-goals

- Replacing fire alarms, intruder alarms or a monitored security service. CamMind is an assistant, and the docs and UI say so.
- Identifying people (faces, names, attendance by face).
- Recording audio.
- Being an NVR: CamMind keeps a short buffer and event clips, not 30 days of continuous footage.
