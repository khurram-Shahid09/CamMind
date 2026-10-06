import logging

from celery import shared_task

from .go2rtc import Go2rtcError
from .service import sync_go2rtc

log = logging.getLogger(__name__)


@shared_task(name="media.sync_go2rtc", ignore_result=True)
def sync_go2rtc_task() -> None:
    """After every camera change, and every minute (a restarted go2rtc gets its streams back)."""
    try:
        report = sync_go2rtc()
    except Go2rtcError as exc:
        log.warning("go2rtc sync skipped: %s", exc)
        return
    if report.added or report.updated or report.removed:
        log.info(
            "go2rtc sync: +%d ~%d -%d", len(report.added), len(report.updated), len(report.removed)
        )
