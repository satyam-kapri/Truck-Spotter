import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = os.environ.get('VERCEL') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if IS_VERCEL:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY in Vercel environment variables before deploying.')
    SECRET_KEY = 'local-development-only-change-before-hosting'
DEBUG = os.environ.get('DJANGO_DEBUG', '0' if IS_VERCEL else '1') == '1'
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if host.strip()]
for variable in ('VERCEL_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
    host = os.environ.get(variable, '').strip()
    if IS_VERCEL and host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)
INSTALLED_APPS = ['django.contrib.staticfiles', 'rest_framework']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'backend.urls'
WSGI_APPLICATION = 'backend.wsgi.application'
USE_TZ = True
TIME_ZONE = 'UTC'
STATIC_URL = '/assets/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'dist' / 'assets'] if (BASE_DIR / 'dist' / 'assets').exists() else []
WHITENOISE_ROOT = BASE_DIR / 'dist'
REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    if not REDIS_URL.startswith(('redis://', 'rediss://')):
        raise ImproperlyConfigured('REDIS_URL must use redis:// or rediss://, not a Redis REST API URL.')
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL, 'KEY_PREFIX': os.environ.get('CACHE_KEY_PREFIX', 'spotter-v1'), 'OPTIONS': {'socket_connect_timeout': 5, 'socket_timeout': 5}}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'spotter', 'OPTIONS': {'MAX_ENTRIES': 1000}}}
REST_FRAMEWORK = {'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'], 'UNAUTHENTICATED_USER': None, 'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'], 'DEFAULT_THROTTLE_RATES': {'anon': '60/min'}}
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

