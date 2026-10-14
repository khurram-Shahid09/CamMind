# YouTube uploads

Published: overview https://youtu.be/T_2oNMnniSs · home https://youtu.be/sodhgWveh70 · school https://youtu.be/C3CHocaT9g0 · factory https://youtu.be/eoAP9mu7JGA · retail https://youtu.be/_7TRiZITRz0

Thumbnails: `demo/out/thumbnails/` (1280×720). Suggested playlist: **CamMind: AI cameras in plain English**.
Paste each video's link back into the README (`demo/out/...mp4` → YouTube URL) after upload.

---

## 1 · Overview (`demo/out/cammind-demo.mp4`, thumbnail `cammind-overview.png`)

**Title:** CamMind: Tell Your Cameras What to Watch, in Plain English (AI CCTV Demo)

**Description:**
```
Cameras are everywhere, but almost nobody watches them, and motion alerts fire for every shadow. CamMind turns any ordinary IP (RTSP) camera into an AI watcher: you type a rule in plain English, it shows you exactly what it understood, and it alerts your team only when that thing actually happens.

In this demo:
• Five live cameras: home, school gate, shop floor, factory
• Typing "Alert me if anyone stands at the back door" and seeing the precise rule it compiled
• A request it refuses: it doesn't recognise specific people (privacy by design)
• A real event with the snapshot, the zone and the reason, plus a Slack alert
• A helmet check: the AI looks at one small crop and answers one yes/no question

How it works:
Camera → motion filter → object detection and tracking (on your own computer) → your rule → an AI check only when needed → alert with evidence

Built with: Python, Django, Celery, PostgreSQL, Redis, go2rtc, ONNX Runtime (D-FINE detector), ByteTrack, Next.js. Works with any LLM: hosted, GPT, Claude, open-source or your own model.

Source code: https://github.com/khurram-Shahid09/CamMind
Portfolio: https://khurramshahid.vercel.app

Use-case demos: [home] · [school] · [factory] · [retail]   ← add the links

Sample footage: Intel IoT DevKit sample videos (CC BY 4.0).

#AI #ComputerVision #CCTV #SmartCamera #LLM #Python #Django #NextJS #Automation
```

---

## 2 · Home (`demo/out/usecases/cammind-home.mp4`, thumbnail `cammind-home.png`)

**Title:** AI Home Security: "Alert Me If Anyone Stands at the Back Door" | CamMind Use Case 1

**Description:**
```
Motion alerts ping you for every cat, car light and shadow. With CamMind you just say what you care about.

The rule, typed in plain English:
"Alert me if anyone stands at the back door"

What happens:
1. CamMind turns the sentence into a precise rule (a person in the Back door zone for at least 2 seconds) and shows you what it understood before anything runs.
2. You activate it. The camera is watched on your own computer; the video stays at home.
3. When someone stops at the back door, you get one event with a snapshot, the zone and the time, and an alert on Slack.

Privacy built in: when asked "Tell me when my brother Ali comes home", it refuses. CamMind detects people and behaviour, never identities.

Alerts today: Slack. Email and WhatsApp alerts with a short clip are on the roadmap.

Full overview: [link]   Source: https://github.com/khurram-Shahid09/CamMind
Sample footage: Intel IoT DevKit sample videos (CC BY 4.0).

#HomeSecurity #AI #SmartHome #CCTV #ComputerVision #LLM
```

---

## 3 · School (`demo/out/usecases/cammind-school.mp4`, thumbnail `cammind-school.png`)

**Title:** AI School Safety: "Tell Security If Anyone Enters Through the Gate" | CamMind Use Case 2

**Description:**
```
Schools have cameras on every gate, but nobody can watch the screens all day. CamMind watches for you.

The rule, typed in plain English:
"Tell security if anyone enters the campus through the gate"

What happens:
1. CamMind compiles it into a precise rule: a person crossing the Gate line in the "in" direction.
2. Each person is tracked on site. The moment someone crosses the line into the campus, one event is created with the snapshot and the time.
3. Security gets an alert on Slack straight away.

You can add time windows too, for example only after school hours, and limit what each guard can see to their own campus.

Alerts today: Slack. Email and WhatsApp alerts with a short clip are on the roadmap.

Full overview: [link]   Source: https://github.com/khurram-Shahid09/CamMind
Sample footage: Intel IoT DevKit sample videos (CC BY 4.0).

#SchoolSafety #AI #CCTV #ComputerVision #Security #LLM
```

---

## 4 · Factory (`demo/out/usecases/cammind-factory.mp4`, thumbnail `cammind-factory.png`)

**Title:** AI Helmet Check for Factory Safety: No False Alarms | CamMind Use Case 3

**Description:**
```
A detector can see a person, but it can't tell whether they're wearing a helmet. CamMind adds an AI check, only when it's needed.

The rule, typed in plain English:
"Flag any worker in the press area without a helmet"

What happens:
1. CamMind compiles it into a rule: a person in the Press area, plus one yes/no question: "Is this person wearing a hard hat or safety helmet?"
2. When a worker walks into the press area, only a small crop of that person is sent to the AI.
3. In the video, the AI answers YES (a yellow hard hat), so there is no alert and no false alarm. Without a helmet, the safety team would get a critical alert.

Why it's safe: the AI only answers the question. The rules decide what happens, so text or signs in the scene can't trick it into doing anything else.

Alerts today: Slack. Email and WhatsApp alerts with a short clip are on the roadmap.

Full overview: [link]   Source: https://github.com/khurram-Shahid09/CamMind
Sample footage: Intel IoT DevKit sample videos (CC BY 4.0).

#WorkplaceSafety #PPE #AI #ComputerVision #Manufacturing #LLM
```

---

## 5 · Retail (`demo/out/usecases/cammind-retail.mp4`, thumbnail `cammind-retail.png`)

**Title:** AI Crowd Alert for Shops: Know When the Floor Gets Busy | CamMind Use Case 4

**Description:**
```
Shop managers want to know when the floor gets busy, so they can send another staff member to help, without watching cameras all day.

The rule, typed in plain English:
"Alert me if more than 2 people are on the shop floor of the reception camera"

What happens:
1. CamMind compiles it into a counting rule: the number of people in the Shop floor zone is more than 2.
2. People are counted on site in every frame. It waits a few seconds, so a passer-by doesn't trigger it.
3. In the video, it counts 5 people and raises one event with every person boxed in the snapshot, plus a Slack alert.

The same works for queues, empty counters, loitering near the stockroom, or people in the shop after hours.

Alerts today: Slack. Email and WhatsApp alerts with a short clip are on the roadmap.

Full overview: [link]   Source: https://github.com/khurram-Shahid09/CamMind
Sample footage: Intel IoT DevKit sample videos (CC BY 4.0).

#Retail #AI #ComputerVision #CCTV #StoreOperations #LLM
```
