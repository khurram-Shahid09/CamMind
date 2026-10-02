# 14 · Security & Privacy

Cameras show people's homes, children at school and staff at work. Getting this wrong hurts real people, so privacy is a design input, not a checklist at the end.

## Privacy by design

| Principle | How |
|---|---|
| **Process on site** | Decode, detection, tracking and rules run on the user's machine. Video never streams to CamMind's servers or to an AI provider |
| **Minimum to the cloud** | Only rules with `verify` send images, and only crops or small frame strips. Per-camera `cloud_ai_allowed` is **off by default**; turning it on shows what will be sent |
| **No identities** | No face recognition, no re-identification across cameras, no person profiles ([ADR-0005](adr/0005-no-face-recognition.md)) |
| **No audio** | Audio tracks are dropped at intake and never recorded |
| **Short retention** | 2-minute rolling buffer; event clips 14 days by default; dismissed events 7 days |
| **Purpose-limited rules** | The compiler refuses identity, protected-attribute and private-space rules ([06](06-rule-compiler.md#refusals)) |
| **Transparency** | Event detail shows exactly what was sent to the AI and what came back |

**AI provider data use:** for the hosted demo and any paid deployment, use API tiers whose terms don't train on submitted data. The Gemini **free** tier may use inputs to improve products, so it's for test streams and self-recorded footage only, never real customer cameras. The UI warns if a free-tier key is configured on a site with real cameras.

## Threat model

| Threat | Mitigation |
|---|---|
| Stolen camera credentials | Encrypted at rest (Fernet, key from env, rotatable); never returned by the API; masked in logs; only go2rtc and the core's camera test read them |
| Exposed go2rtc (live video to the internet) | go2rtc binds to localhost / the Docker network; dashboard access goes through short-lived tokens checked by the core; no anonymous streams; API and admin UI disabled on public interfaces |
| Cameras with default passwords on the LAN | Onboarding checks for well-known default credentials when testing a URL and warns ("This camera uses a factory password") |
| SSRF via the camera URL field | Only `rtsp://` and `rtsps://`; block the cloud metadata IP range and the core's own host; camera test runs in the worker network, not the API host |
| Prompt injection via text in the scene | Verify output is a yes/no enum; no tools; deterministic decision; rechecks; injection evals with a release bar of 0 ([09](09-ai-verification.md#why-its-injection-safe)) |
| Prompt injection via the rule text | Compiler output is a schema-validated spec checked against real IDs and the user's access; the user confirms; the compiler has no tools |
| Webhook spoofing / replay | HMAC-SHA256 signature with timestamp; 5-minute window; secret per webhook |
| Leaked clip URLs | Signed URLs, 1 h for the dashboard, 24 h for webhooks; bucket is private |
| Cross-tenant access | Org-scoped managers on every query; site access checks; tests that try every endpoint with another org's IDs |
| Rogue or stolen worker token | Tokens scoped to assigned cameras; can only post events and heartbeats; revocable; rotated on worker re-registration |
| Alert flooding (misconfigured rule) | Rate limit per channel, grouping, cooldowns ([10](10-actions-and-notifications.md#delivery)) |
| Insider misuse (watching someone) | Viewer role for live view is explicit; every live-view session start is in the audit log (who, which camera, when) |
| Dependency and supply chain | Pinned versions with `uv.lock` / `pnpm-lock.yaml`; Dependabot; model files pinned by SHA-256 |

## Application security basics

- Django security middleware, secure cookies, CSRF on the BFF, CSP on the dashboard.
- Passwords with Argon2; login rate limiting; optional TOTP for owners (v0.2).
- Secrets only from env (`.env` git-ignored; `.env.example` committed).
- The app's DB role can't `UPDATE` or `DELETE` `audit_event`.

## Legal notes by tier

**Not legal advice.** These are the points the product must support, and the docs and UI should tell users to check their local law.

| Tier | Points to support |
|---|---|
| **Home** | Point cameras at your own property; avoid neighbours' windows and public pavements where possible (UK ICO and EU guidance treat filming beyond your boundary as personal data processing). CamMind: a "privacy mask" zone type that's blacked out before processing and in clips (v0.2), and a note in onboarding |
| **School** | Parents and staff must be told (signage, policy); no cameras inside washrooms or changing rooms; access limited to named staff; short retention. In the US, FERPA can apply to recordings kept as student records; in the EU/UK, GDPR applies with children as a sensitive group. CamMind: the camera-notice text template, the private-space refusal, role-limited access, retention defaults |
| **Workplace / enterprise** | Inform employees; legitimate purpose (safety, security), not performance surveillance; works-council or union consultation in some countries; data subject access requests. Biometric laws (Illinois BIPA, Texas, EU AI Act limits on biometric categorisation) don't apply because CamMind does no face recognition or biometric categorisation. Keep it that way |
| **Pakistan** | PECA 2016 covers unauthorised access and misuse of data; the Personal Data Protection Bill is still a draft and may change requirements. Follow the GDPR-style defaults above |

**EU AI Act:** real-time remote biometric identification in public spaces is prohibited for most uses, and emotion recognition in workplaces and schools is banned. CamMind does neither, and the compiler refuses emotion and intent rules for this reason too.

## Product wording

- Never promise safety: "CamMind helps you notice events. It isn't a replacement for alarms, fire detection, guards or emergency services."
- Show this in onboarding, in the README and next to smoke, fire and fall rules.
