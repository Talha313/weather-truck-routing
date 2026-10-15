"""Django settings. Everything deploy-specific comes from environment variables."""

import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    """Read KEY=VALUE lines from backend/.env for local dev. Real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file(BASE_DIR / ".env")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# No cookies, sessions or logins exist, so there is nothing for CSRF protection to guard.
SILENCED_SYSTEM_CHECKS = ["security.W003"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The API is stateless: no models, no auth, no sessions.
DATABASES = {}

CACHES = {
    "default": {
        # File-based so every gunicorn worker shares the weather/route cache.
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get(
            "CACHE_DIR", os.path.join(tempfile.gettempdir(), "weather-truck-routing-cache")
        ),
        "TIMEOUT": 30 * 60,
        "OPTIONS": {"MAX_ENTRIES": 50_000},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

# Identifies this app to the free OSM-based services, as their usage policies require.
HTTP_USER_AGENT = os.environ.get(
    "HTTP_USER_AGENT", "weather-truck-routing/1.0 (assessment project)"
)
VALHALLA_URL = os.environ.get("VALHALLA_URL", "https://valhalla1.openstreetmap.de/route")
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org/route/v1/driving")
PHOTON_URL = os.environ.get("PHOTON_URL", "https://photon.komoot.io/api/")
OPEN_METEO_URL = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")

# Open-Meteo's free tier counts every location as one request and limits requests per IP.
# Hosts with shared outbound IPs (e.g. PythonAnywhere) should use fewer heatmap cells and a
# longer cache to stay under the limits.
WEATHER_CACHE_TTL_S = int(os.environ.get("WEATHER_CACHE_TTL_S", str(30 * 60)))
HEATMAP_MAX_CELLS = int(os.environ.get("HEATMAP_MAX_CELLS", "260"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

if not DEBUG:
    # Hosts like Render/Railway terminate TLS at a proxy.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "true").lower() == "true"
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
