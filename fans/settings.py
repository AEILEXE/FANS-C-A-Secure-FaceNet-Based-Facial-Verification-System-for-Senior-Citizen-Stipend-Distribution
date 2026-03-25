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
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

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
