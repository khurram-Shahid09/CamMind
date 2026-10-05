# Test stream clips

MediaMTX loops `clips/<name>.mp4` as a fake camera at `rtsp://localhost:8654/<name>`. A camera without a clip shows a labelled test pattern, so the stack runs before any footage exists. Clips aren't committed (see `.gitignore`); this file is the record of where each one came from.

| Name | Scene wanted | Used by | Source | Licence | Notes |
|---|---|---|---|---|---|
| `home_backdoor` | Back yard at night; a person walks to the door and stays ~10 s | home door-at-night rule, demo scene 2–3 | – | – | – |
| `school_gate` | Gate in the evening; a person walks in through the gate | crossing rule, demo scene 4 | – | – | – |
| `school_parking` | Parking lot; a group gathers | count rule | – | – | – |
| `workshop_press` | Workers in a work area, one without a helmet | helmet verification, injection scene | – | – | – |
| `office_reception` | Reception desk, staffed then empty | absence rule | – | – | – |

## Rules for clips

- **Self-recorded** clips need permission from everyone who appears in them. Write "self-recorded, consent given" in the licence column.
- **Stock** clips: Pexels or Pixabay licence only (free for commercial use, no attribution required). Put the page URL in the source column.
- No footage of children unless it's self-recorded with a parent's consent.
- Convert before adding, so the clip loops cleanly without re-encoding at run time:
  `ffmpeg -i input.mp4 -an -c:v libx264 -preset veryfast -crf 23 -g 20 -vf scale=-2:720 -t 120 clips/<name>.mp4`
