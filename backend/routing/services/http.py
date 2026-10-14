"""One shared HTTP session with retries for all third-party calls."""

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class UpstreamError(Exception):
    """A third-party service failed or returned something unusable. The message is user-facing."""


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = settings.HTTP_USER_AGENT
    return session


session = _build_session()
