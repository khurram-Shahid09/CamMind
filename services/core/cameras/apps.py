from django.apps import AppConfig
from django.db import transaction
from django.db.models.signals import post_delete, post_save

# Saves that only touch these fields don't change any stream.
STATUS_FIELDS = frozenset(
    {"snapshot_key", "snapshot_at", "stream_meta", "check_status", "check_error", "checked_at"}
)


def _schedule_sync(sender, update_fields=None, **kwargs) -> None:
    from .tasks import sync_go2rtc_task

    if update_fields and set(update_fields) - {"updated_at"} <= STATUS_FIELDS:
        return
    # After the transaction commits, so go2rtc never sees a camera that was rolled back.
    transaction.on_commit(sync_go2rtc_task.delay)


class CamerasConfig(AppConfig):
    name = "cameras"

    def ready(self) -> None:
        from .models import Camera

        post_save.connect(_schedule_sync, sender=Camera, dispatch_uid="cameras.sync_on_save")
        post_delete.connect(_schedule_sync, sender=Camera, dispatch_uid="cameras.sync_on_delete")
