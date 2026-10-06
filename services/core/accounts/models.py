import hashlib
import secrets
from zoneinfo import available_timezones

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models

from common.ids import PrefixedIdField
from common.models import TimeStampedModel
from common.tenancy import OrgOwnedModel


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra) -> "User":
        if not email:
            raise ValueError("email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra) -> "User":
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """One account for the dashboard. Email is the login (case-insensitive)."""

    id = PrefixedIdField(prefix="usr")
    email = models.EmailField(max_length=254, unique=True)  # always stored lowercased
    name = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access only

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs) -> None:
        self.email = self.email.lower()
        super().save(*args, **kwargs)


class Tier(models.TextChoices):
    """Sets defaults: calendars, suggested rules, retention (docs/01-product-vision.md)."""

    HOME = "home"
    SCHOOL = "school"
    BUSINESS = "business"


class Organization(TimeStampedModel):
    """A household, school or company. Every tenant-owned row belongs to exactly one."""

    id = PrefixedIdField(prefix="org")
    name = models.CharField(max_length=120)
    tier = models.CharField(max_length=10, choices=Tier.choices, default=Tier.HOME)
    # Retention, budgets and default channels (docs/11-data-model.md).
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "organizations"

    def __str__(self) -> str:
        return self.name


def validate_timezone(value: str) -> None:
    if value not in available_timezones():
        raise ValidationError(f"{value!r} is not a known time zone.")


class Site(OrgOwnedModel, TimeStampedModel):
    """A place with cameras: a house, a campus, a plant. Rules run in the site's time zone."""

    id = PrefixedIdField(prefix="site")
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=120)
    timezone = models.CharField(
        max_length=64, default="Asia/Karachi", validators=[validate_timezone]
    )
    address = models.CharField(max_length=300, blank=True)
    retention_days_media = models.PositiveSmallIntegerField(default=14)
    retention_days_events = models.PositiveSmallIntegerField(default=90)

    class Meta:
        db_table = "sites"
        constraints = [
            models.UniqueConstraint(fields=["org", "name"], name="sites_org_name_unique")
        ]

    def __str__(self) -> str:
        return self.name


class Role(models.TextChoices):
    """docs/12-api-spec.md, "Permissions"."""

    OWNER = "owner"  # everything, including other owners, budgets and retention
    ADMIN = "admin"  # members (not owners), cameras, zones, channels, rules, audit
    OPERATOR = "operator"  # rules on their sites, feedback and comments
    VIEWER = "viewer"  # live view, events and clips


MANAGERS = frozenset({Role.OWNER.value, Role.ADMIN.value})


class Membership(OrgOwnedModel, TimeStampedModel):
    id = PrefixedIdField(prefix="mem")
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    # False: only the sites listed in ``sites`` (a guard who works at one campus).
    all_sites = models.BooleanField(default=True)
    sites = models.ManyToManyField(Site, blank=True, related_name="+", db_table="site_access")

    class Meta:
        db_table = "memberships"
        constraints = [
            models.UniqueConstraint(fields=["org", "user"], name="memberships_org_user_unique")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.org_id} ({self.role})"

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    @property
    def is_manager(self) -> bool:
        return self.role in MANAGERS

    def site_ids(self) -> set[str] | None:
        """The sites this member may see; ``None`` means every site of the org."""
        if self.all_sites:
            return None
        return set(self.sites.values_list("id", flat=True))

    def can_access_site(self, site_id: str) -> bool:
        allowed = self.site_ids()
        return allowed is None or site_id in allowed


class ApiToken(OrgOwnedModel, TimeStampedModel):
    """Personal access token for scripts and integrations. Only its SHA-256 is stored."""

    PREFIX = "pat_"
    plaintext = ""  # set on the instance returned by issue(); never stored

    id = PrefixedIdField(prefix="tok")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_tokens"

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    @staticmethod
    def hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(
        cls, *, org: Organization, user: User, name: str, expires_at=None
    ) -> tuple["ApiToken", str]:
        """Create a token and return it with the plaintext, which is never retrievable again."""
        raw = cls.PREFIX + secrets.token_urlsafe(32)
        token = cls.objects.create(
            org=org, user=user, name=name, token_hash=cls.hash(raw), expires_at=expires_at
        )
        token.plaintext = raw
        return token, raw

    def is_usable(self, now) -> bool:
        return self.revoked_at is None and (self.expires_at is None or self.expires_at > now)
