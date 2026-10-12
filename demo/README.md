# Demo

`out/cammind-demo.mp4` (85 s) is recorded from the real system: the vision worker watches the looping test cameras, the LLM compiles the typed rules and answers the helmet check.

## Re-record

```bash
docker compose -f infra/docker-compose.yml --profile test-streams up -d
python infra/test-streams/fetch_clips.py

# terminal 1-4 (see the main README): API on :8200, Celery, vision worker, dashboard
cd services/core && uv run uvicorn config.asgi:application --port 8200
cd services/core && uv run celery -A config worker -Q compile,verify,media,actions --pool=solo
cd services/vision && uv run cammind-vision run
pnpm --filter @cammind/web build && pnpm --filter @cammind/web start

# reset, let the worker collect a minute of events, then record and edit
cd services/core && uv run python manage.py prepare_demo
uv run --no-project --with playwright python ../../demo/scripts/capture.py
cd ../.. && uv run --no-project --with edge-tts --with imageio-ffmpeg --with numpy python demo/scripts/make_demo.py
```

`capture.py` writes `out/raw/main.webm`, `marks.json` and the screenshots in `out/shots/`; `make_demo.py` adds the voice-over (Microsoft neural TTS via edge-tts), captions, title cards and quiet synthesized music.

The free tier of the default LLM provider allows a limited number of requests per day per model. `GEMINI_MODELS` lists fallbacks (`gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite`).
