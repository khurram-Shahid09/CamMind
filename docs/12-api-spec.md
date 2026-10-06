# 12 · API Spec

REST over JSON, served by DRF at `/api/v1`. The dashboard calls it through Next.js BFF route handlers (session cookie → API token), the same pattern as WatchOnce. External clients use `Authorization: Bearer <api_token>`. Vision workers use `/internal/*` with `Authorization: Worker <token>`.

Conventions: cursor pagination (`?cursor=…&limit=50`), errors as `{"error": {"code": "…", "message": "…", "fields": {…}}}`, `Idempotency-Key` honoured on all `POST`s, all timestamps ISO-8601 UTC.

## Auth and org

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Email, password, `org_name`, `tier`, `timezone` → new workspace (caller is its owner) with a first site |
| POST | `/auth/login` | Email + password → access JWT; rotating refresh token in an httpOnly cookie |
| POST | `/auth/refresh` | New access token; reusing a rotated refresh token revokes the whole session family |
| POST | `/auth/logout` | |
| GET | `/me` | User, memberships (`role`, `all_sites`, `site_ids`), the token in use |
| GET / PATCH | `/org` | Name, tier, settings (retention, budgets) |
| GET / POST | `/orgs/{org_id}/members` | Add an existing user by email with `role`, `all_sites`, `site_ids` |
| GET / PATCH / DELETE | `/orgs/{org_id}/members/{id}` | Admins can't touch owners; the last owner can't leave (`409 last_owner`) |
| GET / POST | `/tokens` | API tokens (`pat_…`, secret shown once); a token can't mint tokens |
| DELETE | `/tokens/{id}` | Revoke |

## Sites

| Method | Path | Notes |
|---|---|---|
| GET / POST | `/sites` | |
| GET / PATCH / DELETE | `/sites/{id}` | `DELETE` → `409 site_not_empty` while it has cameras |
| GET / PUT | `/sites/{id}/calendars/{kind}` | Weekly hours + holidays |

## Cameras

| Method | Path | Notes |
|---|---|---|
| POST | `/cameras/test` | `{rtsp_url}` → `{ok, error_code, message, codec, fps, width, height, warnings, snapshot_jpeg_base64}`. Error codes: `invalid_url`, `unreachable`, `timeout`, `auth_failed`, `not_found`, `unsupported_codec`, `rtsp_error`. Warnings flag factory passwords |
| GET / POST | `/cameras` | `rtsp_main`, `rtsp_sub` (write-only), `name`, `site_id`, `detect_fps`, `cloud_ai_allowed`, `enabled`. Both URLs are checked before saving (`400 camera_check_failed` with the error code) |
| GET / PATCH / DELETE | `/cameras/{id}` | Response has `rtsp_main_masked` / `rtsp_sub_masked` only. Changing a URL re-checks it |
| GET | `/cameras/{id}/snapshot` | Last stored JPEG; `?fresh=1` grabs a new one via go2rtc (`502 camera_unavailable` if it can't) |
| GET | `/cameras/{id}/live` | `{webrtc_url, mse_url}` with a short-lived token for go2rtc |
| GET | `/cameras/{id}/health?since=` | History for the health chart |

## Zones

| Method | Path | Notes |
|---|---|---|
| GET / POST | `/cameras/{id}/zones` | `{name, kind, points, in_side}` |
| PATCH / DELETE | `/zones/{id}` | `DELETE` → `409 zone_in_use` with the rules listed |

## Rules

| Method | Path | Notes |
|---|---|---|
| POST | `/rules/compile` | `{text, site_id, camera_ids?, answer?: {question_id, value}}` → `{kind: rule\|question\|unsupported, spec?, summary?, assumptions?, question?, options?, reason?, suggestion?, validation_errors?, compile_run_id}` |
| POST | `/rules/validate` | `{spec}` → `{ok, errors, summary, cost_estimate}`. Used when the user edits fields |
| GET / POST | `/rules` | `POST {name?, site_id, source_text, spec, compile_run_id, activate: bool}` |
| GET / PATCH / DELETE | `/rules/{id}` | `PATCH {spec}` creates a new version; `PATCH {status}` to pause/activate |
| GET | `/rules/{id}/versions` | |
| POST | `/rules/{id}/test` | `{source: "buffer" \| "upload", camera_id, upload_id?}` → `202 {test_run_id}` |
| GET | `/rules/test-runs/{id}` | `{status, moments: [{t, reason, snapshot_url}]}` |
| GET | `/rules/{id}/stats?days=7` | Events, reviewed, precision, AI calls, cost, suggestions |

## Events

| Method | Path | Notes |
|---|---|---|
| GET | `/events` | Filters: `site_id`, `camera_id`, `rule_id`, `state`, `severity`, `from`, `to`, `reviewed`, `include_dismissed` |
| GET | `/events/{id}` | Includes verifications, media URLs (signed, 1 h), deliveries, feedback, comments |
| POST | `/events/{id}/feedback` | `{verdict, reason_code?, note?}` |
| POST | `/events/{id}/comments` | `{body}` |
| GET | `/events/{id}/clip` | Redirect to a signed URL (404 until ready) |
| POST | `/events/{id}/feedback-link` | One-time signed link target (email buttons); no session needed |

## Channels

| Method | Path | Notes |
|---|---|---|
| GET / POST | `/channels` | `{kind, name, config}`; config secrets write-only |
| PATCH / DELETE | `/channels/{id}` | |
| POST | `/channels/{id}/test` | Sends a test message |
| POST | `/channels/{id}/telegram-link` | → `{code, bot_username}`; user sends `/start <code>` |
| GET | `/channels/{id}/deliveries` | Recent deliveries and attempts |
| POST | `/integrations/telegram/webhook/{secret}` | Telegram updates (link codes, button callbacks) |

## Usage and audit

| Method | Path | Notes |
|---|---|---|
| GET | `/usage?group_by=day\|camera\|rule&from=&to=` | Calls, tokens, cost |
| GET / PUT | `/budgets` | Org and per-camera caps |
| GET | `/audit?target_type=&target_id=&from=&to=` | Owner and admin only |

## Live updates (SSE)

`GET /api/v1/stream` (through the BFF), scoped to the user's org and sites:

| Event | Data |
|---|---|
| `event.created` | Event summary (state confirmed / unverified) |
| `event.updated` | `{id, state, t_end, clip_ready}` |
| `camera.health` | `{camera_id, state, detect_fps}` every 10 s per changed camera |
| `rule.test_progress` | `{test_run_id, pct, moments_so_far}` |
| `budget.warning` | `{scope, pct}` |

## Internal (vision worker ↔ core)

| Method | Path | Notes |
|---|---|---|
| GET | `/internal/config` | Cameras (with decrypted restream paths, not camera credentials: the worker reads from go2rtc), zones, active rule specs, `config_version` |
| POST | `/internal/heartbeat` | Worker version, per-camera health |
| POST | `/internal/events` | Candidate events (see [08](08-rule-engine-and-events.md#event-reporting-worker--core)); idempotent |
| PATCH | `/internal/events/{id}` | Still active / closed |
| POST | `/internal/verify-requests` | Crops (multipart) + request metadata → queued `verify` task; result returned on `chan:worker:<id>` |
| POST | `/internal/stats` | Hourly detection stats per camera and class (for cost estimates) |

Worker tokens are scoped to the worker's assigned cameras. A worker can't read other cameras' config or post events for them.

## Permissions

| Action | Owner | Admin | Operator | Viewer |
|---|---|---|---|---|
| Members, tokens, budgets, retention | ✅ | ✅ (not owners) | – | – |
| Cameras, zones, channels | ✅ | ✅ | – | – |
| Create / edit rules | ✅ | ✅ | ✅ (own sites) | – |
| Live view, events, clips | ✅ | ✅ | ✅ | ✅ |
| Feedback and comments | ✅ | ✅ | ✅ | – |
| Audit log | ✅ | ✅ | – | – |
