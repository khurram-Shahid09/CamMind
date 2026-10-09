from typing import cast

from django.db import transaction
from rest_framework import generics, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from accounts.models import Role, Site
from accounts.views_base import OrgScopedViewMixin
from audit.service import record
from cameras.models import Zone
from common.exceptions import ApiError

from .models import Rule, RuleStatus, RuleVersion
from .service import SpecError, summarize, validate_spec

EDITORS = frozenset({Role.OWNER.value, Role.ADMIN.value, Role.OPERATOR.value})


def zone_names(org) -> dict[str, str]:
    return dict(Zone.objects.for_org(org).values_list("id", "name"))


class RuleSerializer(serializers.ModelSerializer):
    site_id = serializers.CharField()
    source_text = serializers.CharField(required=False, allow_blank=True, write_only=True)
    spec = serializers.JSONField(write_only=True)
    assumptions = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    version = serializers.SerializerMethodField()

    class Meta:
        model = Rule
        fields = [
            "id",
            "site_id",
            "name",
            "status",
            "source_text",
            "spec",
            "assumptions",
            "version",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_version(self, rule: Rule) -> dict | None:
        v = rule.current_version
        if v is None:
            return None
        return {
            "id": v.id,
            "version": v.version,
            "source_text": v.source_text,
            "spec": v.spec,
            "summary": v.summary,
            "assumptions": v.assumptions,
        }


def _new_version(rule: Rule, data: dict, request: Request) -> RuleVersion:
    try:
        spec = validate_spec(data["spec"], rule.org)
    except SpecError as exc:
        raise ApiError(
            "invalid_rule", "This rule can't run as written.", details={"errors": exc.errors}
        ) from exc
    number = (rule.versions.order_by("-version").values_list("version", flat=True).first() or 0) + 1
    version = RuleVersion.objects.create(
        org=rule.org,
        rule=rule,
        version=number,
        source_text=data.get("source_text", ""),
        spec=spec.model_dump(mode="json", by_alias=True),
        summary=summarize(spec, zone_names(rule.org)),
        assumptions=data.get("assumptions", []),
        created_by=f"user:{request.user.pk}",
    )
    rule.current_version = version
    rule.save(update_fields=["current_version", "updated_at"])
    return version


class RuleListView(OrgScopedViewMixin, generics.ListCreateAPIView):
    queryset = Rule.objects.select_related("current_version")
    serializer_class = RuleSerializer
    site_field = "site"
    method_roles = {"POST": EDITORS}

    def perform_create(self, serializer: BaseSerializer) -> None:
        data = serializer.validated_data
        site = Site.objects.for_org(self.org).filter(pk=data["site_id"]).first()
        if site is None or not self.membership.can_access_site(site.pk):
            raise ApiError("site_not_found", "No such site.", status_code=404)
        with transaction.atomic():
            rule = Rule.objects.create(
                org=self.org,
                site=site,
                name=data["name"],
                status=data.get("status", RuleStatus.DRAFT),
            )
            _new_version(rule, data, self.request)
            record(
                "rule.created",
                org=self.org,
                request=self.request,
                entity=rule,
                metadata={"name": rule.name},
            )
        serializer.instance = rule


class RuleDetailView(OrgScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Rule.objects.select_related("current_version")
    serializer_class = RuleSerializer
    site_field = "site"
    lookup_url_kwarg = "rule_id"
    method_roles = {"PATCH": EDITORS, "DELETE": EDITORS}
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer(self, *args, **kwargs):
        kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    def perform_update(self, serializer: BaseSerializer) -> None:
        rule = cast(Rule, serializer.instance)
        data = serializer.validated_data
        with transaction.atomic():
            for field in ("name", "status"):
                if field in data:
                    setattr(rule, field, data[field])
            rule.save()
            if "spec" in data:
                _new_version(rule, data, self.request)
            record(
                "rule.updated",
                org=self.org,
                request=self.request,
                entity=rule,
                metadata={k: str(v)[:200] for k, v in data.items() if k != "spec"},
            )


class RuleValidateView(OrgScopedViewMixin, APIView):
    """Check an edited spec and get its summary, without saving (docs/12)."""

    def post(self, request: Request) -> Response:
        try:
            spec = validate_spec(dict(request.data).get("spec") or {}, self.org)
        except SpecError as exc:
            return Response({"ok": False, "errors": exc.errors, "summary": ""})
        return Response(
            {"ok": True, "errors": [], "summary": summarize(spec, zone_names(self.org))}
        )


class RuleCompileView(OrgScopedViewMixin, APIView):
    """Plain English -> rule spec, question or refusal (docs/06). Nothing is saved."""

    method_roles = {"POST": EDITORS}

    def post(self, request: Request) -> Response:
        from .compiler import compile_rule

        data = dict(request.data)
        text = str(data.get("text", "")).strip()[:500]
        site = Site.objects.for_org(self.org).filter(pk=data.get("site_id")).first()
        if not text or site is None or not self.membership.can_access_site(site.pk):
            raise ApiError("bad_request", "Give the rule text and one of your sites.")
        result = compile_rule(text, site)
        record(
            "rule.compiled",
            org=self.org,
            request=request,
            metadata={"text": text, "kind": result["kind"]},
        )
        return Response(result)
