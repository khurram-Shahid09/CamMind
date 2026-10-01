# 10 · Actions & Notifications

Actions run in the `actions` Celery queue, only for events in `confirmed` or `unverified` state.

## Channels

| Channel | Setup | Message | Clip |
|---|---|---|---|
| **In-app** | Always on | Live toast + timeline entry over SSE | Player in event detail |
| **Telegram** | Owner creates a bot with @BotFather and pastes the token, or uses the shared CamMind bot (hosted demo). User links a chat by sending `/start <code>` | Photo with caption, then the clip as a video reply | Yes (≤ 50 MB; clips are ~2–5 MB) |
| **Email** | SMTP or Resend settings per org; Mailpit in dev | Subject + snapshot inline + "Open event" link | Link only |
| **Slack** | Incoming webhook URL per channel | Block Kit message with snapshot URL and buttons linking to the event | Link only |
| **Webhook** | URL + generated signing secret | JSON payload (below) | URLs (signed, expire in 24 h) |

Channel secrets (bot tokens, webhook URLs, SMTP passwords) are encrypted at rest and never returned by the API.

## Message content

```
🔴 CRITICAL · No helmet in Press area
Press line · 30 Oct 14:07:22
Person in Press area without a hard hat (AI: "head uncovered", 0.91)
Rule: "Flag any worker in the press area without a helmet"
[Open event]  [Confirm]  [False alarm]
```

- Severity emoji: 🔵 info, 🟠 warning, 🔴 critical.
- Unverified events say: *"⚠ Not verified by AI (budget reached)"*.
- Times are in the site's time zone.
- Confirm / False alarm buttons: Telegram inline buttons (callback to the core) and signed one-time links in email. Slack interactive buttons come with Bolt in v0.2; the MVP links to the event page.

## Delivery

1. **Snapshot message first**, as soon as the event is confirmed (target: < 1 s after confirmation).
2. **Clip follow-up** when the `media` task finishes (about `clip_post_seconds` + 2–4 s later), sent as a reply to the first message where the channel supports it.
3. **Grouping:** alerts for the same rule that start within 10 s are merged into one message ("2 people in Back door").
4. **Quiet hours** (per user, per channel, optional): info and warning alerts during quiet hours are delivered as a digest at the end. Critical alerts always go through.
5. **Rate limit:** at most 20 messages per channel per 10 minutes. Beyond that a single "Many events, open the dashboard" message is sent, so a misconfigured rule can't flood someone's phone.

## Retries

- Per delivery: retries at 10 s, 30 s, 2 min, 10 min and 30 min, then `failed`.
- Telegram `429` and Slack rate limits respect `retry_after`.
- Each attempt is a `delivery_attempt` row (status, HTTP code, latency, error), visible on the channel page.
- One channel failing never delays others.

## Webhook payload

```http
POST https://example.com/hooks/cammind
Content-Type: application/json
X-CamMind-Event: event.confirmed
X-CamMind-Delivery: dl_9fK2…
X-CamMind-Timestamp: 1793369242
X-CamMind-Signature: sha256=…   (HMAC-SHA256 of "<timestamp>.<body>" with the webhook secret)
```
```json
{
  "type": "event.confirmed",
  "event": {
    "id": "evt_3QmT8",
    "state": "confirmed",
    "severity": "critical",
    "rule": { "id": "rul_x2", "version_id": "rv_7Hk2", "name": "No helmet in press area" },
    "site": { "id": "site_main", "name": "Plant 1" },
    "camera": { "id": "cam_press", "name": "Press line" },
    "zones": ["Press area"],
    "started_at": "2026-10-30T09:07:22Z",
    "reason": "Person in Press area without a hard hat",
    "verification": { "answer": "no", "confidence": 0.91, "model": "gemini-flash" },
    "snapshot_url": "https://…/signed",
    "clip_url": null,
    "dashboard_url": "https://…/events/evt_3QmT8"
  }
}
```

Event types: `event.confirmed`, `event.unverified`, `event.clip_ready`, `event.closed`, `event.reviewed`, `camera.offline`, `camera.online`, `budget.warning`, `budget.exhausted`.

Receivers should check the signature and reject timestamps older than 5 minutes. A verification snippet in Python and Node goes in the webhook settings page.

**What webhooks enable:** opening a gate or turning on lights through the user's own system, a siren through Home Assistant, a ticket in a helpdesk, an n8n or Zapier flow. CamMind itself never controls devices directly in the MVP.

## System notifications

Sent to owners and admins (in-app + email by default):

- Camera offline > 2 minutes; back online.
- Vision worker not reporting for > 1 minute.
- AI budget at 80% and 100%.
- Channel delivery failing for > 30 minutes.
- Rule with precision < 50% over the last 7 days (with the tuning suggestion).
