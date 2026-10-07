# Test stream clips

MediaMTX loops `clips/<name>.mp4` as a fake camera at `rtsp://localhost:8654/<name>`. A camera without a clip shows a labelled test pattern, so the stack runs before any footage exists. Clips aren't committed (see `.gitignore`); this file is the record of where each one came from.

Development clips come from Intel's [sample-videos](https://github.com/intel-iot-devkit/sample-videos) repository, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (attribution: Intel Corporation, "IoT DevKit sample videos"). `python infra/test-streams/fetch_clips.py` downloads them and checks their SHA-256. The demo video replaces them with footage that matches each scene.

| Name | Scene wanted for the demo | Development clip (source file) | Licence | Notes |
|---|---|---|---|---|
| `home_backdoor` | Back yard at night; a person walks to the door and stays ~10 s | `one-by-one-person-detection.mp4` (768×432, 10 fps, 139 s) | CC BY 4.0, Intel | People walk in one at a time |
| `school_gate` | Gate in the evening; a person walks in through the gate | `person-bicycle-car-detection.mp4` (768×432, 12 fps, 54 s) | CC BY 4.0, Intel | People, bicycles and cars |
| `school_parking` | Parking lot; a group gathers | `people-detection.mp4` (768×432, 12 fps, 50 s) | CC BY 4.0, Intel | Several people at once |
| `workshop_press` | Workers in a work area, one without a helmet | `worker-zone-detection.mp4` (1920×1080, 60 fps, 76 s) | CC BY 4.0, Intel | Workers moving through zones |
| `office_reception` | Reception desk, staffed then empty | `store-aisle-detection.mp4` (720×404, 60 fps, 65 s) | CC BY 4.0, Intel | Shoppers in an aisle |

## Rules for clips

- **Self-recorded** clips need permission from everyone who appears in them. Write "self-recorded, consent given" in the licence column.
- **Stock** clips: Pexels or Pixabay licence only (free for commercial use, no attribution required). Put the page URL in the source column.
- No footage of children unless it's self-recorded with a parent's consent.
- Convert before adding, so the clip loops cleanly without re-encoding at run time:
  `ffmpeg -i input.mp4 -an -c:v libx264 -preset veryfast -crf 23 -g 20 -vf scale=-2:720 -t 120 clips/<name>.mp4`
