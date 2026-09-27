"""Fail-closed production settings. Local preview is an explicit opt-in."""
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEVELOPMENT = os.environ.get("BETBOY_PORTAL_DEV") == "1"
DEBUG = DEVELOPMENT
SECRET_KEY = os.environ.get("BETBOY_PORTAL_SECRET", "")
if not SECRET_KEY:
    if not DEVELOPMENT:
        raise ImproperlyConfigured("BETBOY_PORTAL_SECRET is required.")
    SECRET_KEY = secrets.token_urlsafe(48)
if not DEVELOPMENT and len(SECRET_KEY) < 48:
    raise ImproperlyConfigured("Use a separately generated portal secret of at least 48 characters.")

PUBLIC_ORIGIN = os.environ.get("BETBOY_PORTAL_ORIGIN", "http://127.0.0.1:8010" if DEVELOPMENT else "").rstrip("/")
origin = urlsplit(PUBLIC_ORIGIN)
if not origin.hostname or origin.path or origin.query or origin.fragment or origin.username:
    raise ImproperlyConfigured("BETBOY_PORTAL_ORIGIN must be an origin, without a path.")
if origin.scheme != "https" and not (DEVELOPMENT and origin.hostname in {"127.0.0.1", "localhost"}):
    raise ImproperlyConfigured("Production requires an HTTPS origin.")
ALLOWED_HOSTS = [origin.hostname, "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]
ROOT_URLCONF = "siteconfig.urls"
WSGI_APPLICATION = "siteconfig.wsgi.application"
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "members",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "members.middleware.LanguageMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages", "members.copy.context",
    ]},
}]
runtime = Path(os.environ.get("BETBOY_PORTAL_STATE", str(BASE_DIR / ".runtime")))
if not DEVELOPMENT and "BETBOY_PORTAL_STATE" not in os.environ:
    raise ImproperlyConfigured("BETBOY_PORTAL_STATE must be a private production directory.")
runtime.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": runtime / "customers.sqlite3", "OPTIONS": {"timeout": 20}}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "members.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "de"
LANGUAGES = [("de", "Deutsch"), ("en", "English")]
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "/portal-static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "static-collected"
SESSION_COOKIE_NAME = "betboy_customer"
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEVELOPMENT
CSRF_COOKIE_SECURE = not DEVELOPMENT
CSRF_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = not DEVELOPMENT
SECURE_HSTS_SECONDS = 31536000 if not DEVELOPMENT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEVELOPMENT
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
TRUST_PROXY = os.environ.get("BETBOY_PORTAL_TRUST_PROXY") == "1"
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
PASSWORD_RESET_TIMEOUT = 60 * 60
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("BETBOY_MAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("BETBOY_MAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("BETBOY_MAIL_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("BETBOY_MAIL_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("BETBOY_MAIL_FROM", "")
EMAIL_TIMEOUT = 10
# A local preview does not send real mail, create customers or charge cards.
REGISTRATION_OPEN = os.environ.get("BETBOY_REGISTRATION_OPEN") == "1"
LEGAL_READY = os.environ.get("BETBOY_LEGAL_READY") == "1"
LEGAL_URL = os.environ.get("BETBOY_LEGAL_URL", "")
PRIVACY_URL = os.environ.get("BETBOY_PRIVACY_URL", "")
TERMS_URL = os.environ.get("BETBOY_TERMS_URL", "")
APP_URL = "/app/"
APP_ACCESS_ENABLED = os.environ.get("BETBOY_APP_ACCESS_ENABLED") == "1"
INTERNAL_TOKEN = os.environ.get("BETBOY_PORTAL_INTERNAL_TOKEN", "")
STRIPE_SECRET_KEY = os.environ.get("BETBOY_STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("BETBOY_STRIPE_WEBHOOK_SECRET", "")
STRIPE_LIVE = os.environ.get("BETBOY_STRIPE_LIVE") == "1"
STRIPE_PRICES = {plan: os.environ.get(f"BETBOY_STRIPE_PRICE_{plan.upper()}", "") for plan in ("starter", "plus", "pro")}
STRIPE_COUNTRIES = [v.strip().upper() for v in os.environ.get("BETBOY_SALES_COUNTRIES", "").split(",") if v.strip()]
CSRF_FAILURE_VIEW = "members.views.csrf_failure"
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
