"""Read-only launch configuration check, without Stripe or sports API calls."""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from members import billing
from members.views import mail_ready


class Command(BaseCommand):
    help = "Check local customer-launch prerequisites. Does not certify legal, Stripe or Store approval."

    def handle(self, *args, **options):
        missing = []
        if settings.DEVELOPMENT:
            missing.append("Production settings (development mode is enabled)")
        if not settings.REGISTRATION_OPEN:
            missing.append("BETBOY_REGISTRATION_OPEN")
        if not settings.APP_ACCESS_ENABLED:
            missing.append("BETBOY_APP_ACCESS_ENABLED and Streamlit/proxy cutover")
        if not settings.TRUST_PROXY:
            missing.append("Trusted loopback reverse proxy configuration")
        if len(settings.INTERNAL_TOKEN) < 32:
            missing.append("BETBOY_PORTAL_INTERNAL_TOKEN (at least 32 characters)")
        if not mail_ready():
            missing.append("Verified SMTP sender configuration")
        if not settings.LEGAL_READY:
            missing.append("Operator, terms and privacy publication")
        for name in ("LEGAL_URL", "PRIVACY_URL", "TERMS_URL"):
            value = urlsplit(getattr(settings, name))
            if value.scheme != "https" or not value.hostname:
                missing.append(f"BETBOY_{name}")
        if not billing.configured():
            missing.append("Stripe keys, webhook, three approved price IDs and sales countries")
        if not settings.STRIPE_LIVE:
            missing.append("Stripe live activation (test payments are not a sales launch)")
        if missing:
            raise CommandError("Not ready for customer launch:\n- " + "\n- ".join(missing))
        self.stdout.write("Local configuration complete. Still verify a live delivery, paid access, revocation and provider/country approval before opening sales.")
