import hmac
import logging
import smtplib
from functools import wraps

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import billing
from .access import entitlement
from .copy import COPY
from .forms import LoginForm, RegisterForm, ResetPasswordForm, ResetRequestForm
from .limits import allowed
from .models import User
from .plans import PLANS, valid_plan
from .tokens import activation_token

logger = logging.getLogger(__name__)


def account_required(view):
    @wraps(view)
    def wrapped(request, lang, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login", lang=lang)
        return view(request, lang, *args, **kwargs)
    return wrapped


def notice(request, lang, title, body, status=200):
    return render(request, "message.html", {"heading": COPY[lang][title], "body": COPY[lang][body]}, status=status)


def mail_ready():
    return bool(settings.DEFAULT_FROM_EMAIL and (settings.EMAIL_HOST or settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend"))


def send_link(user, lang, purpose):
    words = COPY[lang]
    token_generator = activation_token if purpose == "activation" else default_token_generator
    url = settings.PUBLIC_ORIGIN + reverse("activate" if purpose == "activation" else "reset_confirm", kwargs={
        "lang": lang, "uid": urlsafe_base64_encode(force_bytes(user.pk)), "token": token_generator.make_token(user),
    })
    result = send_mail(words[f"{purpose}_subject"], f"{words[f'{purpose}_body']}\n\n{url}", settings.DEFAULT_FROM_EMAIL, [user.email])
    if result != 1:
        raise OSError("Mail delivery not accepted.")


def link_user(uid):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (ValueError, TypeError, UnicodeDecodeError, ValidationError, User.DoesNotExist):
        return None


@require_GET
def root(request):
    return redirect("home", lang="de")


@require_GET
def home(request, lang):
    return render(request, "landing.html")


@require_http_methods(["GET", "POST"])
def register(request, lang):
    if request.user.is_authenticated:
        return redirect("account", lang=lang)
    chosen = valid_plan(request.GET.get("plan", request.session.get("chosen_plan", "starter")))
    request.session["chosen_plan"] = chosen
    opened = settings.REGISTRATION_OPEN and settings.LEGAL_READY and mail_ready()
    form = RegisterForm(request.POST or None, lang=lang)
    if request.method == "POST":
        if not opened:
            return notice(request, lang, "register", "register_closed", 503)
        if not allowed(request, "register", request.POST.get("email", ""), limit=5):
            return notice(request, lang, "register", "limited", 429)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
                    if user is None:
                        user = User(email=form.cleaned_data["email"], is_active=False)
                    if not user.is_active:
                        user.set_password(form.cleaned_data["password"])
                        user.language = lang
                        user.terms_accepted_at = timezone.now()
                        user.terms_version = "2026-09-v1"
                        user.save()
                        send_link(user, lang, "activation")
            except IntegrityError:
                pass  # Concurrent/duplicate registrations reveal no account existence.
            except (OSError, smtplib.SMTPException):
                return notice(request, lang, "register", "mail_unavailable", 503)
            return notice(request, lang, "check_mail", "activation_sent")
    return render(request, "auth.html", {
        "form": form, "kind": "register", "heading": COPY[lang]["register_title"],
        "intro": COPY[lang]["register_text"], "submit": COPY[lang]["register"],
        "opened": opened, "chosen_plan": PLANS[chosen],
    })


@require_http_methods(["GET", "POST"])
def login(request, lang):
    if request.user.is_authenticated:
        return redirect("account", lang=lang)
    form = LoginForm(request.POST or None, request=request, lang=lang)
    if request.method == "POST":
        if not allowed(request, "login", request.POST.get("email", "")):
            return notice(request, lang, "login", "limited", 429)
        if form.is_valid():
            auth_login(request, form.user)
            return redirect("account", lang=lang)
    return render(request, "auth.html", {"form": form, "kind": "login", "heading": COPY[lang]["login_title"], "intro": COPY[lang]["login_text"], "submit": COPY[lang]["login"], "opened": True})


@require_POST
def logout(request, lang):
    auth_logout(request)
    return redirect("home", lang=lang)


@require_http_methods(["GET", "POST"])
def activate(request, lang, uid, token):
    user = link_user(uid)
    if user is None or user.is_active or not activation_token.check_token(user, token):
        return notice(request, lang, "activate_title", "invalid_link", 400)
    if request.method == "POST":
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, COPY[lang]["activated"])
        return redirect("login", lang=lang)
    # GET must not activate accounts when a mail scanner follows links.
    return render(request, "auth.html", {"kind": "activate", "heading": COPY[lang]["activate_title"], "intro": COPY[lang]["activate_text"], "submit": COPY[lang]["activate"], "opened": True})


@require_http_methods(["GET", "POST"])
def reset(request, lang):
    form = ResetRequestForm(request.POST or None, lang=lang)
    if request.method == "POST":
        if not mail_ready():
            return notice(request, lang, "reset_title", "mail_unavailable", 503)
        if not allowed(request, "reset", request.POST.get("email", ""), limit=5):
            return notice(request, lang, "reset_title", "limited", 429)
        if form.is_valid():
            user = User.objects.filter(email__iexact=form.cleaned_data["email"].strip(), is_active=True).first()
            if user:
                try:
                    send_link(user, lang, "reset")
                except (OSError, smtplib.SMTPException):
                    return notice(request, lang, "reset_title", "mail_unavailable", 503)
            return notice(request, lang, "check_mail", "reset_sent")
    return render(request, "auth.html", {"form": form, "kind": "reset", "heading": COPY[lang]["reset_title"], "intro": COPY[lang]["reset_text"], "submit": COPY[lang]["reset_send"], "opened": mail_ready()})


@require_http_methods(["GET", "POST"])
def reset_confirm(request, lang, uid, token):
    user = link_user(uid)
    if user is None or not user.is_active or not default_token_generator.check_token(user, token):
        return notice(request, lang, "reset_title", "invalid_link", 400)
    form = ResetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        auth_logout(request)
        messages.success(request, COPY[lang]["password_changed"])
        return redirect("login", lang=lang)
    return render(request, "auth.html", {"form": form, "kind": "reset_confirm", "heading": COPY[lang]["new_password"], "submit": COPY[lang]["save_password"], "opened": True})


@require_GET
@account_required
def account(request, lang):
    access = entitlement(request.user)
    return render(request, "account.html", {
        "access": access, "active_plan": PLANS[access["plan"]] if access else None,
        "billing_ready": billing.configured(), "app_ready": settings.APP_ACCESS_ENABLED,
        "app_url": settings.APP_URL, "returned": request.GET.get("checkout") == "returned",
    })


@require_POST
@account_required
def checkout(request, lang):
    if not allowed(request, "checkout", str(request.user.pk), limit=10):
        return notice(request, lang, "account_title", "limited", 429)
    if not billing.configured():
        return notice(request, lang, "account_title", "billing_unavailable", 503)
    try:
        return redirect(billing.start_checkout(request.user, request.POST.get("plan"), lang))
    except (billing.BillingUnavailable, stripe.StripeError, DatabaseError) as exc:
        logger.warning("Checkout unavailable (%s)", type(exc).__name__)
        return notice(request, lang, "account_title", "billing_error", 503)


@require_POST
@account_required
def manage(request, lang):
    if not allowed(request, "billing-portal", str(request.user.pk), limit=10):
        return notice(request, lang, "account_title", "limited", 429)
    try:
        return redirect(billing.manage_billing(request.user, lang))
    except (billing.BillingUnavailable, stripe.StripeError) as exc:
        logger.warning("Billing portal unavailable (%s)", type(exc).__name__)
        return notice(request, lang, "account_title", "billing_error", 503)


@csrf_exempt
@require_POST
def webhook(request):
    if not billing.configured():
        return HttpResponse(status=503)
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""), settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)
    try:
        billing.process_event(event)
    except (billing.BillingUnavailable, stripe.StripeError, DatabaseError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Payment webhook retry needed (%s)", type(exc).__name__)
        # Do not acknowledge delivery before the entitlement transaction commits.
        return HttpResponse(status=503)
    return HttpResponse(status=200)


@require_GET
def internal_access(request):
    expected = settings.INTERNAL_TOKEN
    supplied = request.headers.get("X-BetBoy-Internal", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        return HttpResponse(status=404)
    if not settings.APP_ACCESS_ENABLED:
        return JsonResponse({"error": "access_disabled"}, status=503)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    access = entitlement(request.user)
    return JsonResponse(access or {"error": "subscription_required"}, status=200 if access else 403)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


def csrf_failure(request, reason=""):
    return notice(request, getattr(request, "LANGUAGE_CODE", "de"), "login", "session_expired", 403)
