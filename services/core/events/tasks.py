"""Actions for events (docs/10-actions-and-notifications.md): verification, then alerts.

Slack is the alert channel of the demo (incoming webhook). The message carries the reason,
the rule and a link to the event; the snapshot is on the event page.
"""

import logging

import httpx
from celery import shared_task
from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)
EMOJI = {
    "info": ":large_blue_circle:",
    "warning": ":large_orange_circle:",
    "critical": ":red_circle:",
}


def slack_message(event) -> dict:
    from zoneinfo import ZoneInfo

    local = timezone.localtime(event.t_start, ZoneInfo(event.site.timezone))
    rule = event.rule_version.rule
    lines = [
        f"{EMOJI.get(event.severity, '')} *{event.severity.upper()} · {rule.name}*",
        f"{event.camera.name} · {local:%d %b %H:%M:%S}",
        event.reason,
    ]
    verdict = event.verification
    if verdict.get("answer"):
        lines.append(
            f"AI check: “{verdict.get('reason', '')}” ({verdict['answer']}, {verdict.get('confidence', 0):.2f})"
        )
    if event.state == "unverified":
        lines.append(":warning: Not verified by AI")
    lines.append(f"<{settings.APP_BASE_URL}/events/{event.id}|Open event>")
    return {"text": "\n".join(lines)}


@shared_task(name="actions.run_actions", ignore_result=True, bind=True, max_retries=5)
def run_actions(self, event_id: str) -> None:
    from .models import Event, EventState
    from .verify import verify_event

    event = (
        Event.objects.select_related("camera", "site", "rule_version__rule")
        .filter(pk=event_id)
        .first()
    )
    if event is None:
        return
    if event.state == EventState.VERIFYING:
        verify_event(event)
    if event.state not in (EventState.CONFIRMED, EventState.UNVERIFIED):
        return
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        return
    try:
        response = httpx.post(url, json=slack_message(event), timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("slack alert for %s failed: %s", event_id, exc)
        raise self.retry(exc=exc, countdown=min(600, 10 * 3**self.request.retries)) from exc
