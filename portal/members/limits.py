import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import RateBucket


def allowed(request, action, identity="", limit=8, seconds=900):
    """Bound attempts across workers; never store raw email addresses or IPs."""
    remote = request.META.get("REMOTE_ADDR", "unknown")
    if settings.TRUST_PROXY and remote in {"127.0.0.1", "::1"}:
        remote = request.META.get("HTTP_X_FORWARDED_FOR", remote).split(",")[-1].strip()
    now = timezone.now()
    window = int(now.timestamp()) // seconds
    parts = [remote] + ([identity.strip().lower()] if identity else [])
    RateBucket.objects.filter(expires_at__lt=now).delete()
    permitted = True
    for part in parts:
        key = hmac.new(settings.SECRET_KEY.encode(), f"{action}:{part}:{window}".encode(), hashlib.sha256).hexdigest()
        with transaction.atomic():
            RateBucket.objects.get_or_create(key=key, defaults={"expires_at": now + timedelta(seconds=seconds)})
            RateBucket.objects.filter(key=key).update(count=F("count") + 1)
            permitted = permitted and RateBucket.objects.get(key=key).count <= limit
    return permitted
