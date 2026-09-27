import os

os.environ["BETBOY_PORTAL_DEV"] = "1"
os.environ["BETBOY_PORTAL_SECRET"] = "tests-only-not-a-deployment-secret-2026"
from .settings import *  # noqa: F403, E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "test@betboy.invalid"
REGISTRATION_OPEN = True
LEGAL_READY = True
LEGAL_URL = "/de/legal/"
PRIVACY_URL = "/de/privacy/"
TERMS_URL = "/de/terms/"
APP_ACCESS_ENABLED = True
INTERNAL_TOKEN = "internal-test-only-token"
STRIPE_SECRET_KEY = "sk_test_not-a-real-key"
STRIPE_WEBHOOK_SECRET = "whsec_tests-only"
STRIPE_PRICES = {"starter": "price_starter", "plus": "price_plus", "pro": "price_pro"}
STRIPE_COUNTRIES = ["CH"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
