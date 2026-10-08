from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("t_start", "camera", "rule_version", "state", "severity", "reason")
    list_filter = ("state", "severity")
    readonly_fields = [f.name for f in Event._meta.fields]
