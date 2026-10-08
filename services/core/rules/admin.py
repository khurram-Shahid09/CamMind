from django.contrib import admin

from .models import Rule, RuleVersion


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "status", "current_version")
    list_filter = ("status",)


@admin.register(RuleVersion)
class RuleVersionAdmin(admin.ModelAdmin):
    list_display = ("rule", "version", "created_at")
    readonly_fields = ("spec", "summary")
