import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv

_env_file = BASE_DIR / '.env'
load_dotenv(dotenv_path=_env_file, override=True)


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

# ── Face Matching ─────────────────────────────────────────────────────────────
# Default threshold for production: 0.75 (strict, well-lit enrollment)
# Demo/dev threshold: 0.60 (forgiving of webcam quality, slight pose variation)
# DEMO_MODE=True uses DEMO_THRESHOLD automatically.
DEMO_MODE = _bool_env('DEMO_MODE', default=True)
VERIFICATION_THRESHOLD = float(os.getenv('VERIFICATION_THRESHOLD', '0.75'))
DEMO_THRESHOLD = float(os.getenv('DEMO_THRESHOLD', '0.60'))
MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '1'))

# ── Liveness ──────────────────────────────────────────────────────────────────
# LIVENESS_REQUIRED=False: liveness is logged but never blocks face matching.
# Set to True in production for strict enforcement.
LIVENESS_REQUIRED = _bool_env('LIVENESS_REQUIRED', default=False)

# Anti-spoofing texture score threshold (0.0-1.0).
# 0.15 is permissive enough for webcam/browser captures.
# Raise to 0.3-0.5 in production with a trained model.
ANTI_SPOOF_THRESHOLD = float(os.getenv('ANTI_SPOOF_THRESHOLD', '0.15'))

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
