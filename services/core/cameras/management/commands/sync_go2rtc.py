from django.core.management.base import BaseCommand, CommandError

from cameras.go2rtc import Go2rtcError
from cameras.service import sync_go2rtc


class Command(BaseCommand):
    help = "Make go2rtc's streams match the enabled cameras (also runs every minute in beat)."

    def handle(self, *args, **options) -> None:
        try:
            report = sync_go2rtc()
        except Go2rtcError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"added {len(report.added)}, updated {len(report.updated)}, "
            f"removed {len(report.removed)}"
        )
