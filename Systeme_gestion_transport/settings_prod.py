from .settings import *
import os

DEBUG = False

ALLOWED_HOSTS = ["abderahman.pythonanywhere.com"]
CSRF_TRUSTED_ORIGINS = ["https://abderahman.pythonanywhere.com"]

SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
