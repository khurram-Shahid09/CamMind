from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import ApiToken, Membership, Organization, Site, Tier, User, validate_timezone


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "tier"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name"]


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    org_name = serializers.CharField(max_length=120)
    tier = serializers.ChoiceField(choices=Tier.choices, default=Tier.HOME)
    timezone = serializers.CharField(max_length=64, default="Asia/Karachi")

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_timezone(self, value: str) -> str:
        try:
            validate_timezone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate(self, attrs):
        try:
            validate_password(
                attrs["password"], User(email=attrs["email"], name=attrs.get("name", ""))
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = [
            "id",
            "name",
            "timezone",
            "address",
            "retention_days_media",
            "retention_days_events",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_retention_days_media(self, value: int) -> int:
        if not 1 <= value <= 365:
            raise serializers.ValidationError("Keep clips between 1 and 365 days.")
        return value

    def validate_retention_days_events(self, value: int) -> int:
        if not 7 <= value <= 365:
            raise serializers.ValidationError("Keep events between 7 and 365 days.")
        return value


class MembershipSerializer(serializers.ModelSerializer):
    org = OrganizationSerializer(read_only=True)
    site_ids = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "org", "role", "all_sites", "site_ids"]

    def get_site_ids(self, membership: Membership) -> list[str]:
        return sorted(site.id for site in membership.sites.all())


class MeTokenSerializer(serializers.ModelSerializer):
    org = OrganizationSerializer(read_only=True)

    class Meta:
        model = ApiToken
        fields = ["id", "name", "org", "expires_at"]


class MeSerializer(serializers.ModelSerializer):
    memberships = MembershipSerializer(many=True, read_only=True)
    token = serializers.SerializerMethodField(
        help_text="The access token this request used (null for dashboard sessions)."
    )

    class Meta:
        model = User
        fields = ["id", "email", "name", "memberships", "token"]

    def get_token(self, user: User) -> dict | None:
        token = self.context.get("token")
        return MeTokenSerializer(token).data if token is not None else None


class AuthResponseSerializer(serializers.Serializer):
    """Documented shape of register/login/refresh responses (refresh token is in the cookie)."""

    access = serializers.CharField()
    access_expires_in = serializers.IntegerField()
    user = UserSerializer()


class ApiTokenSerializer(serializers.ModelSerializer):
    expires_in_days = serializers.IntegerField(
        write_only=True, required=False, min_value=1, max_value=365
    )

    class Meta:
        model = ApiToken
        fields = [
            "id",
            "name",
            "created_at",
            "last_used_at",
            "expires_at",
            "revoked_at",
            "expires_in_days",
        ]
        read_only_fields = ["id", "created_at", "last_used_at", "expires_at", "revoked_at"]

    def create(self, validated_data):
        # org and user come from the view: serializer.save(org=..., user=...)
        days = validated_data.pop("expires_in_days", None)
        token, _ = ApiToken.issue(  # plaintext is on token.plaintext
            org=validated_data["org"],
            user=validated_data["user"],
            name=validated_data["name"],
            expires_at=timezone.now() + timedelta(days=days) if days else None,
        )
        return token


class ApiTokenCreatedSerializer(ApiTokenSerializer):
    token = serializers.CharField(source="plaintext", read_only=True)

    class Meta(ApiTokenSerializer.Meta):
        fields = [*ApiTokenSerializer.Meta.fields, "token"]


class _OrgSitesField(serializers.PrimaryKeyRelatedField):
    """Site ids, limited to the org of the request (``context["org"]``)."""

    def get_queryset(self):
        return Site.objects.for_org(self.context["org"])


class MemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    email = serializers.EmailField(write_only=True)
    site_ids = _OrgSitesField(source="sites", many=True, required=False)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "all_sites", "site_ids", "created_at", "email"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        return _validated_access(attrs, self.instance)


class MemberUpdateSerializer(serializers.ModelSerializer):
    site_ids = _OrgSitesField(source="sites", many=True, required=False)

    class Meta:
        model = Membership
        fields = ["id", "role", "all_sites", "site_ids"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        return _validated_access(attrs, self.instance)


def _validated_access(attrs: dict, instance: Membership | None) -> dict:
    all_sites = attrs.get("all_sites", instance.all_sites if instance else True)
    sites = attrs.get("sites", list(instance.sites.all()) if instance else [])
    if not all_sites and not sites:
        raise serializers.ValidationError(
            {"site_ids": "Pick at least one site, or give access to all sites."}
        )
    return attrs
