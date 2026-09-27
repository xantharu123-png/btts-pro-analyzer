"""Hosted Stripe payments. No client-supplied price or access grant is trusted."""
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlsplit

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import PaymentEvent, Subscription, User
from .plans import PLANS


class BillingUnavailable(ValueError):
    pass


def configured():
    prefix = "sk_live_" if settings.STRIPE_LIVE else "sk_test_"
    prices = list(settings.STRIPE_PRICES.values())
    return bool(
        settings.STRIPE_SECRET_KEY.startswith(prefix)
        and settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")
        and len(set(prices)) == 3 and all(p.startswith("price_") for p in prices)
        and settings.STRIPE_COUNTRIES and settings.LEGAL_READY and settings.APP_ACCESS_ENABLED
    )


def client():
    if not configured():
        raise BillingUnavailable("Billing is not configured.")
    return stripe.StripeClient(
        settings.STRIPE_SECRET_KEY, max_network_retries=1,
        http_client=stripe.RequestsClient(timeout=10),
    )


def obj_id(value):
    return value.get("id") if isinstance(value, dict) else value


def plain(value):
    # stripe-python 15 resources are not dictionaries (including nested objects).
    return value.to_dict() if isinstance(value, stripe.StripeObject) else value


def price_plan(price):
    plan = next((key for key, value in settings.STRIPE_PRICES.items() if value == price.get("id")), None)
    if not plan:
        raise BillingUnavailable("Unrecognized price.")
    recurring = price.get("recurring") or {}
    if not (
        price.get("currency") == "chf" and price.get("unit_amount") == PLANS[plan]["cents"]
        and recurring.get("interval") == "month" and recurring.get("interval_count") == 1
        and recurring.get("usage_type") == "licensed" and price.get("tax_behavior") == "inclusive"
        and price.get("livemode") is settings.STRIPE_LIVE
    ):
        raise BillingUnavailable("Configured price does not match the approved offer.")
    return plan


def trusted_redirect(url, host):
    parsed = urlsplit(url or "")
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.port not in (None, 443):
        raise BillingUnavailable("Unexpected payment redirect.")
    return url


@transaction.atomic
def start_checkout(user, plan, lang):
    if plan not in PLANS:
        raise BillingUnavailable("Unknown plan.")
    api = client()
    # An actual write serializes SQLite workers; select_for_update alone does not.
    User.objects.filter(pk=user.pk).update(language=F("language"))
    user = User.objects.get(pk=user.pk)
    if user.billing_hold:
        raise BillingUnavailable("Billing requires review.")
    price = plain(api.v1.prices.retrieve(settings.STRIPE_PRICES[plan]))
    if not price.get("active") or price_plan(price) != plan:
        raise BillingUnavailable("Price is not available.")
    if not user.stripe_customer:
        customer = plain(api.v1.customers.create(
            {"email": user.email, "metadata": {"betboy_user_id": user.pk.hex}, "preferred_locales": [lang]},
            options={"idempotency_key": f"betboy-customer-{user.pk.hex}"},
        ))
        user.stripe_customer = customer["id"]
        user.save(update_fields=["stripe_customer"])
    existing = plain(api.v1.subscriptions.list({"customer": user.stripe_customer, "status": "all", "limit": 100}))
    if existing.get("has_more") or any(s.get("status") in {"active", "trialing", "past_due", "unpaid", "incomplete", "paused"} for s in existing["data"]):
        raise BillingUnavailable("Manage the existing subscription instead of buying twice.")
    if user.checkout_id:
        old = plain(api.v1.checkout.sessions.retrieve(user.checkout_id))
        if old.get("status") == "open":
            if user.checkout_plan == plan:
                return trusted_redirect(old.get("url"), "checkout.stripe.com")
            api.v1.checkout.sessions.expire(user.checkout_id)
        elif old.get("status") == "complete":
            # A delayed webhook must not cause an accidental second purchase.
            previous_id = obj_id(old.get("subscription"))
            previous = next((s for s in existing["data"] if s["id"] == previous_id), None)
            if previous is None or previous.get("status") not in {"canceled", "incomplete_expired"}:
                raise BillingUnavailable("The previous checkout is being processed.")
    # Stable parameters/key survive a network timeout or transaction rollback.
    window = int(timezone.now().timestamp()) // 1800
    checkout_language = user.language
    session = plain(api.v1.checkout.sessions.create({
        "mode": "subscription", "customer": user.stripe_customer,
        "client_reference_id": user.pk.hex,
        "line_items": [{"price": settings.STRIPE_PRICES[plan], "quantity": 1}],
        "subscription_data": {"metadata": {"betboy_user_id": user.pk.hex}},
        "success_url": f"{settings.PUBLIC_ORIGIN}/{checkout_language}/account/?checkout=returned",
        "cancel_url": f"{settings.PUBLIC_ORIGIN}/{checkout_language}/account/",
        "locale": checkout_language, "billing_address_collection": "required",
        "customer_update": {"address": "auto"}, "automatic_tax": {"enabled": True},
        "consent_collection": {"terms_of_service": "required"},
        "payment_method_types": ["card"],
        "expires_at": (window + 2) * 1800 + 10,
    }, options={"idempotency_key": f"betboy-checkout-v1-{user.pk.hex}-{plan}-{window}"}))
    user.checkout_id = session["id"]
    user.checkout_plan = plan
    user.checkout_expires_at = datetime.fromtimestamp(session["expires_at"], dt_timezone.utc)
    user.save(update_fields=["checkout_id", "checkout_plan", "checkout_expires_at"])
    return trusted_redirect(session.get("url"), "checkout.stripe.com")


def manage_billing(user, lang):
    if not user.stripe_customer:
        raise BillingUnavailable("No billing account.")
    result = plain(client().v1.billing_portal.sessions.create({
        "customer": user.stripe_customer,
        "return_url": f"{settings.PUBLIC_ORIGIN}/{lang}/account/", "locale": lang,
    }))
    return trusted_redirect(result.get("url"), "billing.stripe.com")


def invoice_subscription(invoice):
    parent = invoice.get("parent") or {}
    return obj_id((parent.get("subscription_details") or {}).get("subscription") or invoice.get("subscription"))


def sync_subscription(api, user, subscription_id):
    current = plain(api.v1.subscriptions.retrieve(subscription_id, {"expand": ["latest_invoice"]}))
    if obj_id(current.get("customer")) != user.stripe_customer:
        raise BillingUnavailable("Subscription customer mismatch.")
    if current.get("livemode") is not settings.STRIPE_LIVE:
        raise BillingUnavailable("Wrong payment environment.")
    if current.get("metadata", {}).get("betboy_user_id") != user.pk.hex:
        raise BillingUnavailable("Subscription ownership mismatch.")
    item_list = current.get("items") or {}
    items = item_list.get("data", [])
    if len(items) != 1 or item_list.get("has_more") or items[0].get("quantity") != 1:
        raise BillingUnavailable("Unexpected subscription items.")
    item = items[0]
    plan = price_plan(item["price"])
    customer = plain(api.v1.customers.retrieve(user.stripe_customer))
    country = (customer.get("address") or {}).get("country", "")
    invoice = current.get("latest_invoice") or {}
    if isinstance(invoice, str):
        invoice = plain(api.v1.invoices.retrieve(invoice))
    period_end = item.get("current_period_end")
    period_start = item.get("current_period_start")
    paid = (
        current.get("status") == "active" and not current.get("pause_collection")
        and invoice.get("status") == "paid" and invoice.get("amount_remaining") == 0
        and invoice.get("amount_paid", 0) >= PLANS[plan]["cents"]
        and obj_id(invoice.get("customer")) == user.stripe_customer
        and invoice_subscription(invoice) == subscription_id
        and invoice.get("livemode") is settings.STRIPE_LIVE
        and country in settings.STRIPE_COUNTRIES
        and isinstance(period_end, int) and isinstance(period_start, int)
        and period_start <= timezone.now().timestamp() < period_end
    )
    # A paid old/proration invoice must not grant the following billing period.
    lines = (invoice.get("lines") or {}).get("data", [])
    covers_period = any(
        (line.get("period") or {}).get("start") == period_start
        and (line.get("period") or {}).get("end") == period_end
        and obj_id(((line.get("pricing") or {}).get("price_details") or {}).get("price") or line.get("price")) == item["price"]["id"]
        and line.get("amount", 0) >= PLANS[plan]["cents"]
        for line in lines
    )
    paid = paid and covers_period
    row, _ = Subscription.objects.get_or_create(
        provider="stripe", external_id=subscription_id,
        defaults={"user": user, "plan": plan, "status": "pending"},
    )
    if row.user_id != user.pk:
        raise BillingUnavailable("An entitlement cannot be transferred.")
    row.plan = plan
    row.status = "active" if paid else current.get("status", "unknown")
    row.paid_until = datetime.fromtimestamp(period_end, dt_timezone.utc) if paid else None
    row.cancel_at_period_end = bool(current.get("cancel_at_period_end"))
    row.checked_at = timezone.now()
    row.blocked = row.blocked or user.billing_hold
    row.save()
    return row


@transaction.atomic
def process_event(event):
    event = plain(event)
    if event.get("livemode") is not settings.STRIPE_LIVE or event.get("account"):
        raise BillingUnavailable("Webhook does not belong to this billing environment.")
    event_id = event["id"]
    if PaymentEvent.objects.filter(pk=event_id).exists():
        return
    kind = event["type"]
    payload = event["data"]["object"]
    api = client()
    subscription_id = None
    charge = None
    if kind in {"charge.refunded", "charge.dispute.created"}:
        charge = payload if kind == "charge.refunded" else plain(api.v1.charges.retrieve(obj_id(payload["charge"])))
        customer_id = obj_id(charge.get("customer"))
    else:
        customer_id = obj_id(payload.get("customer"))
        if kind.startswith("customer.subscription."):
            subscription_id = payload["id"]
        elif kind.startswith("invoice."):
            subscription_id = invoice_subscription(payload)
        elif kind in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            subscription_id = obj_id(payload.get("subscription"))
    user = User.objects.filter(stripe_customer=customer_id).first() if customer_id else None
    if user is not None:
        User.objects.filter(pk=user.pk).update(language=F("language"))
        # Recheck after acquiring the write lock, also on multi-worker PostgreSQL.
        if PaymentEvent.objects.filter(pk=event_id).exists():
            return
        if charge is not None:
            User.objects.filter(pk=user.pk).update(billing_hold=True)
            Subscription.objects.filter(user=user, provider="stripe").update(blocked=True, checked_at=timezone.now())
        elif subscription_id:
            sync_subscription(api, user, subscription_id)
    PaymentEvent.objects.create(external_id=event_id)
