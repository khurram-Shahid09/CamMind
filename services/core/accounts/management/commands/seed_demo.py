"""Demo workspace for local development and the demo video (docs/18-demo-script.md).

Creates "CamMind Demo" with three sites (a home, a school and a workshop), one user per role,
and the five test cameras from ``docker compose --profile test-streams``. Then it syncs go2rtc
and takes a first snapshot of each camera, when the video stack is running.
Safe to run again: users get their password and access reset, cameras their URLs.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Membership, Organization, Role, Site, Tier, User
from audit.service import record
from cameras.go2rtc import Go2rtcError
from cameras.models import Camera, Zone
from cameras.service import refresh_snapshot, sync_go2rtc
from common.storage import StorageError
from rules.models import Rule, RuleVersion
from rules.service import summarize, validate_spec

ORG_NAME = "CamMind Demo"
SITES = ["Home", "Green Valley School", "Workshop"]
TEST_STREAMS = "rtsp://mediamtx:8554"
CAMERAS = [
    # site, camera name, test stream
    ("Home", "Back door", "home_backdoor"),
    ("Green Valley School", "Main gate", "school_gate"),
    ("Green Valley School", "Parking lot", "school_parking"),
    ("Workshop", "Press line", "workshop_press"),
    ("Workshop", "Reception", "office_reception"),
]
ZONES = [
    # camera, zone, kind, points (normalised), in_side
    (
        "Back door",
        "Back door",
        "polygon",
        [[0.3, 0.6], [0.8, 0.6], [0.8, 1.0], [0.3, 1.0]],
        "right",
    ),
    ("Main gate", "Gate line", "line", [[0.0, 0.5], [1.0, 0.5]], "right"),
    (
        "Press line",
        "Press area",
        "polygon",
        [[0.15, 0.35], [0.85, 0.35], [0.95, 1.0], [0.05, 1.0]],
        "right",
    ),
]
# The demo script's rules (docs/18), as the compiler produces them; ids are filled in below.
RULES = [
    ("Home", "Someone at the back door", "Alert me if anyone stands at the back door for 3 seconds",
     {"where": {"type": "zone", "zones": ["Back door"]}, "condition": {"type": "presence"},
      "timing": {"hold_seconds": 3, "cooldown_seconds": 60}}, ["Back door"]),
    ("Green Valley School", "Entry through the gate", "Tell security if anyone enters through the gate",
     {"where": {"type": "line", "line": "Gate line", "direction": "any"}, "condition": {"type": "crossing"},
      "timing": {"cooldown_seconds": 30}}, ["Main gate"]),
    ("Workshop", "No helmet in the press area", "Flag any worker in the press area without a helmet",
     {"where": {"type": "zone", "zones": ["Press area"]}, "condition": {"type": "presence"},
      "verify": {"question": "Is this person wearing a hard hat or safety helmet on their head?", "expect": "no",
                 "on_unsure": "dismiss"},
      "severity": "critical", "timing": {"hold_seconds": 2, "cooldown_seconds": 120}}, ["Press line"]),
]  # fmt: skip
DEMO_USERS = [
    # email, name, role, sites (None = all)
    ("owner@cammind.test", "Ayesha Khan", Role.OWNER, None),
    ("admin@cammind.test", "Hamza Raza", Role.ADMIN, None),
    ("guard@cammind.test", "Bilal Ahmed", Role.OPERATOR, ["Green Valley School"]),
    ("viewer@cammind.test", "Sana Ali", Role.VIEWER, ["Home"]),
]


class Command(BaseCommand):
    help = "Create the demo workspace, one user per role and the test cameras."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-video",
            action="store_true",
            help="Skip the go2rtc sync and snapshots (no docker compose running)",
        )

    def handle(self, *args, no_video: bool = False, **options) -> None:
        password = settings.DEMO_PASSWORD
        if len(password) < 10:
            raise CommandError("Set DEMO_PASSWORD (10+ characters) in .env first.")

        with transaction.atomic():
            org, created = Organization.objects.get_or_create(
                name=ORG_NAME, defaults={"tier": Tier.BUSINESS}
            )
            if created:
                record("org.created", org=org, entity=org, actor="system:seed_demo")
            sites = {name: Site.objects.get_or_create(org=org, name=name)[0] for name in SITES}
            for email, name, role, site_names in DEMO_USERS:
                user, _ = User.objects.get_or_create(email=email, defaults={"name": name})
                user.name = name
                user.set_password(password)
                user.save()
                membership, _ = Membership.objects.update_or_create(
                    org=org,
                    user=user,
                    defaults={"role": role, "all_sites": site_names is None},
                )
                membership.sites.set([sites[s] for s in site_names or []])
            cameras = []
            for site_name, camera_name, stream in CAMERAS:
                camera = Camera.objects.filter(site=sites[site_name], name=camera_name).first()
                camera = camera or Camera(site=sites[site_name], name=camera_name)
                camera.set_urls(f"{TEST_STREAMS}/{stream}")
                camera.save()
                cameras.append(camera)
            by_name = {c.name: c for c in cameras}
            zones = {}
            for camera_name, zone_name, kind, points, in_side in ZONES:
                zones[zone_name], _ = Zone.objects.update_or_create(
                    camera=by_name[camera_name],
                    name=zone_name,
                    defaults={"kind": kind, "points": points, "in_side": in_side},
                )
            by_name["Press line"].cloud_ai_allowed = True  # the helmet check sends crops
            by_name["Press line"].save()
            for site_name, rule_name, text, shape, camera_names in RULES:
                shape = {**shape, "camera_ids": [by_name[n].id for n in camera_names]}
                where = dict(shape["where"])  # type: ignore[call-overload]
                if "zones" in where:
                    where["zone_ids"] = [zones[z].id for z in where.pop("zones")]
                if "line" in where:
                    where["line_id"] = zones[where.pop("line")].id
                spec = validate_spec({**shape, "where": where}, org)
                rule, _ = Rule.objects.update_or_create(
                    org=org, site=sites[site_name], name=rule_name, defaults={"status": "active"}
                )
                if rule.current_version is None:
                    rule.current_version = RuleVersion.objects.create(
                        org=org,
                        rule=rule,
                        version=1,
                        source_text=text,
                        spec=spec.model_dump(mode="json", by_alias=True),
                        summary=summarize(spec, {z.id: z.name for z in zones.values()}),
                    )
                    rule.save()

        self.stdout.write(
            f"Workspace {org.name}: {len(sites)} sites, {len(cameras)} cameras, {len(RULES)} rules."
        )
        for email, _, role, _ in DEMO_USERS:
            self.stdout.write(f"  {role:<9} {email}")
        if no_video:
            return
        try:
            report = sync_go2rtc()
        except Go2rtcError as exc:
            self.stdout.write(self.style.WARNING(f"go2rtc not reachable, skipped: {exc}"))
            return
        self.stdout.write(f"go2rtc: {len(report.added)} streams added.")
        for camera in cameras:
            try:
                refresh_snapshot(camera)
            except (Go2rtcError, StorageError) as exc:
                self.stdout.write(self.style.WARNING(f"  no snapshot for {camera.name}: {exc}"))
            else:
                self.stdout.write(f"  snapshot: {camera.name}")
