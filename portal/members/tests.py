import hashlib
import hmac
import json
import re
import time
import stripe
from datetime import timedelta
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from . import billing
from .access import entitlement
from .copy import COPY
from .models import PaymentEvent, Subscription, User
from .plans import PLANS
from .tokens import activation_token

PASSWORD = "long-unique-passphrase-42!"


class PortalTests(TestCase):
    def make_user(self, **kwargs):
        return User.objects.create_user("member@example.test", PASSWORD, **kwargs)

    def test_bilingual_pages_and_prices(self):
        self.assertEqual(set(COPY["de"]), set(COPY["en"]))
        for lang in ("de", "en"):
            for path in ("", "login/", "register/?plan=plus", "password/reset/"):
                response = self.client.get(f"/{lang}/{path}")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'<html lang="{lang}">')
                self.assertEqual(response["Content-Language"], lang)
            response = self.client.get(f"/{lang}/")
            for price in ("9.90", "19.90", "29.90"):
                self.assertContains(response, price)
            self.assertContains(response, COPY[lang]["illustration"])
            self.assertNotContains(response, 'apps.apple.com')
            self.assertNotContains(response, 'play.google.com/store')
        self.assertEqual(self.client.get("/fr/").status_code, 404)

    def test_register_confirm_login(self):
        response = self.client.post("/en/register/?plan=plus", {
            "email": "Member@Example.test", "password": PASSWORD, "password_confirm": PASSWORD, "accept": "on",
        })
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="member@example.test")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(user.language, "en")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, COPY["en"]["activation_subject"])
        self.assertEqual(self.client.post("/en/login/", {"email": user.email, "password": PASSWORD}).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        link = re.search(r"https?://[^\s]+", mail.outbox[0].body).group().replace(settings.PUBLIC_ORIGIN, "")
        self.assertEqual(self.client.get(link).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active, "mail scanners must not activate accounts")
        self.assertEqual(self.client.post(link).status_code, 302)
        self.assertEqual(self.client.post(link).status_code, 400)
        response = self.client.post("/en/login/?next=https://evil.test", {"email": "MEMBER@example.test", "password": PASSWORD})
        self.assertRedirects(response, "/en/account/")
        self.assertIsNone(entitlement(user))
        self.assertEqual(self.client.get("/en/logout/").status_code, 405)
        self.assertEqual(self.client.post("/en/logout/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unpaid_user_can_manage_account_but_not_open_product(self):
        user = self.make_user()
        self.client.force_login(user)
        response = self.client.get("/de/account/?paid=true&plan=pro&checkout=returned")
        self.assertContains(response, COPY["de"]["no_plan"])
        self.assertNotContains(response, 'href="/app/"')
        response = self.client.get("/internal/access/", HTTP_X_BETBOY_INTERNAL=settings.INTERNAL_TOKEN)
        self.assertEqual(response.status_code, 403)

    def test_internal_access_does_not_trust_claimed_account_or_plan(self):
        self.make_user()
        self.assertEqual(self.client.get("/internal/access/", HTTP_X_BETBOY_USER="admin", HTTP_X_BETBOY_PLAN="pro").status_code, 404)
        self.assertEqual(self.client.get("/internal/access/", HTTP_X_BETBOY_INTERNAL=settings.INTERNAL_TOKEN).status_code, 401)

    def test_paid_access_and_expiry(self):
        user = self.make_user()
        row = Subscription.objects.create(user=user, external_id="sub_a", plan="plus", status="active", paid_until=timezone.now() + timedelta(days=2))
        access = entitlement(user)
        self.assertEqual(access["account_id"], user.pk.hex)
        self.assertIn("search", access["features"])
        self.assertNotIn("daily3", access["features"])
        self.client.force_login(user)
        self.assertEqual(self.client.get("/internal/access/", HTTP_X_BETBOY_INTERNAL=settings.INTERNAL_TOKEN).json()["plan"], "plus")
        for attrs in ({"blocked": True}, {"status": "trialing"}, {"paid_until": timezone.now() - timedelta(seconds=1)}):
            row.blocked, row.status, row.paid_until = False, "active", timezone.now() + timedelta(days=2)
            for name, value in attrs.items():
                setattr(row, name, value)
            row.save()
            self.assertIsNone(entitlement(user))

    def test_duplicate_email_case_insensitive(self):
        self.make_user()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="MEMBER@example.test")

    def test_weak_password_and_terms_required(self):
        response = self.client.post("/de/register/", {"email": "a@example.test", "password": "123", "password_confirm": "123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, 'class="form-errors"')

    def test_duplicate_active_registration_does_not_change_password(self):
        user = self.make_user()
        response = self.client.post("/de/register/", {"email": user.email, "password": "another-very-long-password-92", "password_confirm": "another-very-long-password-92", "accept": "on"})
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))

    @override_settings(REGISTRATION_OPEN=False)
    def test_closed_registration(self):
        self.assertEqual(self.client.post("/de/register/", {}).status_code, 503)
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(self.client.get("/de/register/"), "disabled")

    def test_login_limit_counts_bad_attempts(self):
        for _ in range(8):
            self.assertEqual(self.client.post("/en/login/", {"email": "nobody@example.test", "password": "bad"}).status_code, 200)
        self.assertEqual(self.client.post("/en/login/", {"email": "nobody@example.test", "password": "bad"}).status_code, 429)

    def test_csrf_and_secure_headers(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post("/en/login/", {}).status_code, 403)
        self.assertEqual(browser.post("/de/logout/").status_code, 403)
        response = self.client.get("/en/login/")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("script-src 'none'", response["Content-Security-Policy"])

    def test_reset_is_one_time_and_invalidates_other_sessions(self):
        user = self.make_user()
        self.client.force_login(user)
        other = Client()
        response = other.post("/en/password/reset/", {"email": user.email})
        self.assertContains(response, COPY["en"]["reset_sent"])
        url = re.search(r"https?://[^\s]+", mail.outbox[0].body).group().replace(settings.PUBLIC_ORIGIN, "")
        response = other.post(url, {"new_password1": "new-long-passphrase-43!", "new_password2": "new-long-passphrase-43!"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(other.get(url).status_code, 400)
        self.assertRedirects(self.client.get("/en/account/"), "/en/login/")

    def test_expired_confirmation_and_malformed_uid(self):
        user = self.make_user(is_active=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertEqual(self.client.get(f"/de/activate/{uid}/{activation_token.make_token(user)}/").status_code, 400)
        self.assertEqual(self.client.get("/en/activate/not-a-uuid/token/").status_code, 400)


class BillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("billing@example.test", PASSWORD, stripe_customer="cus_ours")
        self.api = Mock()
        self.now = int(timezone.now().timestamp())
        self.price = {"id": "price_plus", "currency": "chf", "unit_amount": 1990, "active": True,
                      "recurring": {"interval": "month", "interval_count": 1, "usage_type": "licensed"},
                      "tax_behavior": "inclusive", "livemode": False}
        self.invoice = {"id": "in_paid", "customer": "cus_ours", "status": "paid", "amount_remaining": 0, "amount_paid": 1990, "livemode": False,
                        "parent": {"subscription_details": {"subscription": "sub_ours"}},
                        "lines": {"data": [{"period": {"start": self.now - 60, "end": self.now + 86400}, "pricing": {"price_details": {"price": "price_plus"}}, "amount": 1990}]}}
        self.subscription = {"id": "sub_ours", "customer": "cus_ours", "status": "active", "livemode": False,
                             "metadata": {"betboy_user_id": self.user.pk.hex}, "latest_invoice": self.invoice,
                             "items": {"data": [{"price": self.price, "quantity": 1, "current_period_start": self.now - 60, "current_period_end": self.now + 86400}]}}
        self.api.v1.subscriptions.retrieve.return_value = self.subscription
        self.api.v1.customers.retrieve.return_value = {"id": "cus_ours", "address": {"country": "CH"}}
        self.api.v1.prices.retrieve.return_value = self.price
        self.api.v1.subscriptions.list.return_value = {"data": [], "has_more": False}
        self.api.v1.checkout.sessions.create.return_value = {"id": "cs_example", "url": "https://checkout.stripe.com/c/pay/test", "expires_at": self.now + 3600}

    def event(self, event_id="evt_test", kind="customer.subscription.updated", payload=None):
        return {"id": event_id, "type": kind, "livemode": False, "data": {"object": payload or {"id": "sub_ours", "customer": "cus_ours"}}}

    def process(self, **kwargs):
        with patch("members.billing.client", return_value=self.api):
            billing.process_event(self.event(**kwargs))

    def test_paid_subscription_and_duplicate_event(self):
        self.process()
        self.assertEqual(entitlement(self.user)["plan"], "plus")
        self.process()
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(self.api.v1.subscriptions.retrieve.call_count, 1)

    def test_out_of_order_events_retrieve_current_state(self):
        self.process()
        self.subscription["status"] = "canceled"
        self.process(event_id="evt_cancel", kind="customer.subscription.deleted")
        self.process(event_id="evt_older_paid", kind="invoice.paid", payload={"customer": "cus_ours", "parent": {"subscription_details": {"subscription": "sub_ours"}}})
        self.assertIsNone(entitlement(self.user))

    def test_unpaid_old_invoice_and_trial_do_not_unlock(self):
        cases = [
            lambda: self.invoice.update(status="open"),
            lambda: self.invoice.update(amount_paid=0),
            lambda: self.subscription.update(status="trialing"),
            lambda: self.invoice["lines"]["data"][0]["period"].update(end=self.now - 1),
        ]
        for index, mutate in enumerate(cases):
            with self.subTest(index=index):
                self.invoice.update(status="paid", amount_paid=1990)
                self.subscription.update(status="active")
                self.invoice["lines"]["data"][0]["period"]["end"] = self.now + 86400
                mutate()
                self.process(event_id=f"evt_{index}")
                self.assertIsNone(entitlement(self.user))

    def test_refund_before_subscription_cannot_be_overwritten(self):
        self.process(kind="charge.refunded", payload={"customer": "cus_ours", "id": "ch_refunded"})
        self.process(event_id="evt_paid_late")
        self.user.refresh_from_db()
        self.assertTrue(self.user.billing_hold)
        self.assertIsNone(entitlement(self.user))
        self.assertTrue(Subscription.objects.get().blocked)

    def test_dispute_uses_verified_charge_owner(self):
        self.process()
        self.api.v1.charges.retrieve.return_value = {"id": "ch_test", "customer": "cus_ours"}
        self.process(event_id="evt_dispute", kind="charge.dispute.created", payload={"charge": "ch_test"})
        self.assertTrue(Subscription.objects.get().blocked)

    def test_wrong_customer_metadata_price_or_environment_rejected(self):
        for field, value in [("customer", "cus_other"), ("livemode", True), ("metadata", {"betboy_user_id": "someone_else"})]:
            with self.subTest(field=field):
                previous = self.subscription[field]
                self.subscription[field] = value
                with self.assertRaises(billing.BillingUnavailable):
                    self.process(event_id=f"evt_{field}")
                self.subscription[field] = previous
                self.assertEqual(PaymentEvent.objects.count(), 0)
        self.price["unit_amount"] = 1
        with self.assertRaises(billing.BillingUnavailable):
            self.process()
        self.assertEqual(Subscription.objects.count(), 0)

    def test_checkout_server_owns_price_and_return_origin(self):
        with patch("members.billing.client", return_value=self.api):
            url = billing.start_checkout(self.user, "plus", "en")
        self.assertTrue(url.startswith("https://checkout.stripe.com/"))
        call = self.api.v1.checkout.sessions.create.call_args
        params = call.args[0]
        self.assertEqual(params["line_items"], [{"price": "price_plus", "quantity": 1}])
        self.assertEqual(params["subscription_data"]["metadata"]["betboy_user_id"], self.user.pk.hex)
        self.assertTrue(params["success_url"].startswith(settings.PUBLIC_ORIGIN))
        self.assertTrue(params["automatic_tax"]["enabled"])
        self.assertIsNone(entitlement(self.user))

    def test_real_sdk_resource_shapes_are_supported(self):
        self.api.v1.subscriptions.retrieve.return_value = stripe.Subscription.construct_from(self.subscription, None)
        self.api.v1.customers.retrieve.return_value = stripe.Customer.construct_from({"id": "cus_ours", "address": {"country": "CH"}}, None)
        self.process()
        self.assertEqual(entitlement(self.user)["plan"], "plus")
        Subscription.objects.all().delete()
        self.api.v1.prices.retrieve.return_value = stripe.Price.construct_from(self.price, None)
        self.api.v1.subscriptions.list.return_value = stripe.ListObject.construct_from({"data": [], "has_more": False}, None)
        self.api.v1.checkout.sessions.create.return_value = stripe.checkout.Session.construct_from({"id": "cs_sdk", "url": "https://checkout.stripe.com/test", "expires_at": self.now + 3600}, None)
        with patch("members.billing.client", return_value=self.api):
            self.assertEqual(billing.start_checkout(self.user, "plus", "de"), "https://checkout.stripe.com/test")

    def test_repeated_checkout_reuses_open_session(self):
        self.user.checkout_id, self.user.checkout_plan = "cs_pending", "plus"
        self.user.save()
        self.api.v1.checkout.sessions.retrieve.return_value = {"status": "open", "url": "https://checkout.stripe.com/c/pay/pending"}
        with patch("members.billing.client", return_value=self.api):
            billing.start_checkout(self.user, "plus", "de")
        self.api.v1.checkout.sessions.create.assert_not_called()

    def test_existing_subscription_prevents_duplicate_charge(self):
        self.api.v1.subscriptions.list.return_value = {"data": [{"status": "active"}], "has_more": False}
        with patch("members.billing.client", return_value=self.api), self.assertRaises(billing.BillingUnavailable):
            billing.start_checkout(self.user, "plus", "de")
        self.api.v1.checkout.sessions.create.assert_not_called()

    def test_unknown_plan_rejected(self):
        with self.assertRaises(billing.BillingUnavailable):
            billing.start_checkout(self.user, "free-pro", "de")

    def test_hostile_payment_redirect_rejected(self):
        for value in ("https://checkout.stripe.com.evil.test/", "http://checkout.stripe.com/", "https://user@checkout.stripe.com/", "javascript:alert(1)"):
            with self.assertRaises(billing.BillingUnavailable):
                billing.trusted_redirect(value, "checkout.stripe.com")

    def test_webhook_needs_signature_and_is_idempotent(self):
        browser = Client(enforce_csrf_checks=True)
        payload = json.dumps(self.event()).encode()
        self.assertEqual(browser.post("/billing/stripe/webhook/", data=payload, content_type="application/json").status_code, 400)
        stamp = int(time.time())
        sig = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        header = f"t={stamp},v1={sig}"
        with patch("members.billing.client", return_value=self.api):
            for _ in range(2):
                response = browser.post("/billing/stripe/webhook/", data=payload, content_type="application/json", HTTP_STRIPE_SIGNATURE=header)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(PaymentEvent.objects.count(), 1)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_no_credentials_no_fake_checkout(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/en/checkout/", {"plan": "plus", "price": "0", "paid": "true"}).status_code, 503)
        self.assertIsNone(entitlement(self.user))

    def test_different_account_cannot_manage_others_billing(self):
        other = User.objects.create_user("other@example.test", PASSWORD)
        self.client.force_login(other)
        with patch("members.billing.client") as mocked:
            self.assertEqual(self.client.post("/de/billing/", {"customer": "cus_ours"}).status_code, 503)
        mocked.assert_not_called()
