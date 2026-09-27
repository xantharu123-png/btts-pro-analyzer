from django.utils import timezone

from .models import Subscription
from .plans import PLANS


def entitlement(user):
    if not user.is_authenticated or not user.is_active or user.billing_hold:
        return None
    # Do not map staff/superuser to a paid subscription.
    subscriptions = Subscription.objects.filter(
        user=user, status="active", blocked=False, paid_until__gt=timezone.now(),
    )
    candidates = [s for s in subscriptions if s.plan in PLANS]
    if not candidates:
        return None
    selected = max(candidates, key=lambda s: (len(PLANS[s.plan]["features"]), s.paid_until))
    return {
        "account_id": user.pk.hex, "plan": selected.plan,
        "features": list(PLANS[selected.plan]["features"]),
        "paid_until": selected.paid_until.isoformat(),
    }
