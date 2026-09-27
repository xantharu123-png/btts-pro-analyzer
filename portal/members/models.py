import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .plans import PLANS


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, is_active=True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    language = models.CharField(max_length=2, default="de", choices=[("de", "Deutsch"), ("en", "English")])
    terms_accepted_at = models.DateTimeField(null=True)
    terms_version = models.CharField(max_length=32, default="")
    stripe_customer = models.CharField(max_length=100, unique=True, blank=True, null=True)
    billing_hold = models.BooleanField(default=False)
    checkout_id = models.CharField(max_length=120, blank=True)
    checkout_plan = models.CharField(max_length=16, blank=True)
    checkout_expires_at = models.DateTimeField(null=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_customer_email_lower")]


class Subscription(models.Model):
    """Verified entitlement, not a browser assertion or a checkout redirect."""
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    provider = models.CharField(max_length=16, default="stripe")
    external_id = models.CharField(max_length=150)
    plan = models.CharField(max_length=16, choices=[(p, v["name"]) for p, v in PLANS.items()])
    status = models.CharField(max_length=40)
    paid_until = models.DateTimeField(null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    blocked = models.BooleanField(default=False)
    checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "external_id"], name="unique_provider_subscription")]


class PaymentEvent(models.Model):
    # Retain only IDs and processing timestamps, not repeated payment payloads.
    external_id = models.CharField(max_length=150, primary_key=True)
    processed_at = models.DateTimeField(default=timezone.now)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
