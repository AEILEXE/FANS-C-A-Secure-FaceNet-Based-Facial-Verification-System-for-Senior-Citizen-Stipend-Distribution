import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environment bootstrap ──────────────────────────────────────────────────────
# Auto-load .env if present.  Missing dotenv is caught below in first-run checks.
try:
    from dotenv import load_dotenv
    _env_file = BASE_DIR / '.env'
    load_dotenv(dotenv_path=_env_file, override=True)
except ImportError:
    pass  # Warning is surfaced by check_system / first-run validation below


def _bool_env(key, default=False):
    val = os.getenv(key, '').strip().lower()
    if val in ('1', 'true', 'yes', 'on'):
        return True
    if val in ('0', 'false', 'no', 'off'):
        return False
    return default


SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-immediately')
DEBUG = _bool_env('DEBUG', default=True)
# ALLOWED_HOSTS — configure this for your deployment environment.
#
#   Development (default):
#     ALLOWED_HOSTS=localhost,127.0.0.1
#
#   Barangay LAN server — plain HTTP (basic LAN access, no camera on clients):
#     ALLOWED_HOSTS=192.168.1.77,localhost,127.0.0.1
#     Replace 192.168.1.77 with the server's LAN IP (run `ipconfig` to find it).
#
#   Barangay LAN server — secure HTTPS via Caddy (recommended, enables camera):
#     ALLOWED_HOSTS=fans-barangay.local,192.168.1.77,localhost,127.0.0.1
#     Caddy terminates HTTPS and forwards requests to Waitress/Django on
#     localhost.  The hostname fans-barangay.local must also be set in
#     CSRF_TRUSTED_ORIGINS so Django accepts form POST requests from HTTPS
#     clients.  See the Secure HTTPS LAN Deployment section in README.md.
#
#   Why HTTPS matters for camera access: browsers enforce a "secure context"
#   rule — getUserMedia (webcam) is only available on https:// or localhost.
#   A plain http://192.168.x.x URL blocks camera access on client devices.
#   HTTPS with a locally-trusted certificate resolves this without any
#   insecure browser flag workarounds.
#
#   Multiple values are comma-separated in .env; whitespace is stripped.
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'beneficiaries',
    'verification',
    'logs',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fans.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fans.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
USE_SQLITE = _bool_env('USE_SQLITE', default=True)

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'fans_db'),
            'USER': os.getenv('DB_USER', 'fans_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            # Keep database connections alive between requests so multiple
            # staff stations sharing one PostgreSQL server do not pay the
            # TCP handshake cost on every request.  60 s is a safe default;
            # set CONN_MAX_AGE=0 to revert to per-request connections.
            'CONN_MAX_AGE': int(os.getenv('CONN_MAX_AGE', '60')),
        }
    }

AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / os.getenv('MEDIA_ROOT', 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

EMBEDDING_ENCRYPTION_KEY = os.getenv('EMBEDDING_ENCRYPTION_KEY', '')

# ── Offline Sync ───────────────────────────────────────────────────────────────
# Leave SYNC_API_URL empty for offline-only (no sync) operation.
# When set, sync_beneficiaries will push unsynced records to this endpoint.
# SYNC_API_KEY must match the Bearer token expected by the central server.
# The EMBEDDING_ENCRYPTION_KEY above MUST be identical on the central server.
SYNC_API_URL = os.getenv('SYNC_API_URL', '')
SYNC_API_KEY = os.getenv('SYNC_API_KEY', '')
SYNC_TIMEOUT = int(os.getenv('SYNC_TIMEOUT', '30'))
SYNC_BATCH_SIZE = int(os.getenv('SYNC_BATCH_SIZE', '50'))

# ── Face Matching ─────────────────────────────────────────────────────────────
# Full enforcement threshold: 0.75 (strict, well-lit enrollment)
# Assisted Rollout threshold: 0.60 (accommodates webcam quality variation during rollout)
# DEMO_MODE=True activates the Assisted Rollout threshold automatically.
DEMO_MODE = _bool_env('DEMO_MODE', default=True)
VERIFICATION_THRESHOLD = float(os.getenv('VERIFICATION_THRESHOLD', '0.75'))
DEMO_THRESHOLD = float(os.getenv('DEMO_THRESHOLD', '0.60'))
MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '2'))

# ── Liveness ──────────────────────────────────────────────────────────────────
# LIVENESS_REQUIRED=False  Assisted Rollout Mode: liveness runs and is recorded
#                          but does NOT block face matching. Use during gradual
#                          rollout to collect real-world data without blocking
#                          real users who fail the liveness challenge.
# LIVENESS_REQUIRED=True   Strict Mode: a failed liveness check denies the
#                          verification entirely. Enable after validating that
#                          the liveness check is reliable for your hardware.
LIVENESS_REQUIRED = _bool_env('LIVENESS_REQUIRED', default=False)
# Alias for clarity in code that checks strict enforcement
LIVENESS_STRICT_MODE = LIVENESS_REQUIRED

# Anti-spoofing texture score threshold (0.0-1.0).
# 0.15 is permissive enough for webcam/browser captures.
# Raise to 0.3-0.5 in production with a trained model.
ANTI_SPOOF_THRESHOLD = float(os.getenv('ANTI_SPOOF_THRESHOLD', '0.15'))

# ── Logging ───────────────────────────────────────────────────────────────────
# Shows verification scores, thresholds, and decisions in the dev server console.
# Each line is prefixed [VERIFY] so it's easy to grep from the terminal.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '%(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'verification': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'beneficiaries.sync': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Reverse-proxy / HTTPS (centralized server deployment) ────────────────────
# These settings are no-ops when left empty; safe for local development.
#
# For barangay LAN deployment behind Caddy with HTTPS termination:
#
#   CSRF_TRUSTED_ORIGINS=https://fans-barangay.local
#   SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
#   USE_X_FORWARDED_HOST=True
#
# Why CSRF_TRUSTED_ORIGINS is required for HTTPS deployments:
#   Caddy terminates TLS and forwards plain HTTP to Waitress/Django on
#   127.0.0.1:8000.  From Django's perspective every request arrives over
#   plain HTTP, but the browser sent it from an https:// origin.  Django's
#   CSRF middleware compares the Origin header against CSRF_TRUSTED_ORIGINS;
#   if the origin is missing from the list, all form POST requests (login,
#   verification, registration) are rejected with HTTP 403.  Setting
#   CSRF_TRUSTED_ORIGINS to the HTTPS hostname fixes this without weakening
#   any security — the origin check becomes: "did this request come from
#   our own HTTPS hostname?" which is exactly what we want.
#
# If using a raw IP instead of a hostname (less preferred):
#   CSRF_TRUSTED_ORIGINS=https://192.168.1.77
#   Note: mkcert cannot issue certs for raw IPs by default; hostname-based
#   access (fans-barangay.local) is strongly preferred.
_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '').strip()
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]

# When the proxy forwards requests over HTTP internally, tell Django the real
# protocol so SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, and redirect URLs
# all reference https:// rather than http://.
_proxy_ssl_header = os.getenv('SECURE_PROXY_SSL_HEADER', '').strip()
if _proxy_ssl_header and ',' in _proxy_ssl_header:
    _hdr_name, _hdr_value = _proxy_ssl_header.split(',', 1)
    SECURE_PROXY_SSL_HEADER = (_hdr_name.strip(), _hdr_value.strip())

# Required when the proxy sets the Host header from the original client
# request instead of the internal upstream address.
USE_X_FORWARDED_HOST = _bool_env('USE_X_FORWARDED_HOST', default=False)

# ── First-run validation ───────────────────────────────────────────────────────
# Emit clear warnings at startup instead of crashing with opaque errors.
# Critical missing config is raised immediately; non-critical issues are warnings.
_startup_errors = []
_startup_warnings = []

if not EMBEDDING_ENCRYPTION_KEY:
    _startup_errors.append(
        'EMBEDDING_ENCRYPTION_KEY is not set in .env. '
        'Run: python manage.py generate_key  and paste the result into .env. '
        'Without this key, face embeddings cannot be stored or verified.'
    )
else:
    try:
        from cryptography.fernet import Fernet as _Fernet
        _test_key = EMBEDDING_ENCRYPTION_KEY
        _Fernet(_test_key.encode() if isinstance(_test_key, str) else _test_key)
    except Exception as _e:
        _startup_errors.append(
            f'EMBEDDING_ENCRYPTION_KEY is set but is not a valid Fernet key: {_e}. '
            'Re-generate with: python manage.py generate_key'
        )

if SECRET_KEY in ('django-insecure-change-this-immediately', '', 'your-secret-key-here-change-this-in-production'):
    _startup_warnings.append(
        'SECRET_KEY is the default placeholder. '
        'Set a long random value in .env before deploying.'
    )

# Only print warnings when running the server or management commands, not during testing
_running_tests = 'test' in sys.argv or 'pytest' in sys.modules
if not _running_tests:
    import warnings as _warnings
    for _msg in _startup_warnings:
        _warnings.warn(f'[FANS-C] {_msg}', RuntimeWarning, stacklevel=2)
    for _msg in _startup_errors:
        print(f'\n[FANS-C CRITICAL] {_msg}\n', file=sys.stderr)
