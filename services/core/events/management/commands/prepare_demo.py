"""Reset the demo workspace for a recording (demo/README.md).

Clears events, removes rules created during earlier recordings, and leaves the gate and
helmet rules active, so the worker has events ready while the back-door rule is typed live.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import Organization
from events.models import Event
from rules.models import Rule

KEEP = {"Entry through the gate", "No helmet in the press area"}


class Command(BaseCommand):
    help = "Reset the demo workspace before recording the video."

    def handle(self, *args, **options) -> None:
        call_command("seed_demo", "--no-video", stdout=self.stdout)
        org = Organization.objects.get(name="CamMind Demo")
        Event.objects.for_org(org).delete()
        removed, _ = Rule.objects.for_org(org).exclude(name__in=KEEP).delete()
        Rule.objects.for_org(org).filter(name__in=KEEP).update(status="active")
        self.stdout.write(f"Demo ready: events cleared, {removed} extra rules removed.")
