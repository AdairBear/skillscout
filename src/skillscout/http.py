"""Polite, cached HTTP. One request at a time, per-host spacing, honours rate-limit headers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__
from .config import cache_dir

USER_AGENT = f"skillscout/{__version__} (+https://github.com/AdairBear/skillscout)"
# Seconds between requests per host. GitHub code search allows 10/min when authenticated.
SPACING = {"api.github.com": 0.8, "raw.githubusercontent.com": 0.3, "code-search": 7.0}
MAX_BYTES = 20 * 1024 * 1024
_last: dict[str, float] = {}
_token: str | None = None


class FetchError(RuntimeError):
    pass


def github_token() -> str:
    """GITHUB_TOKEN, else the gh CLI's token, else empty (unauthenticated, 60 req/h)."""
    global _token
    if _token is None:
        _token = os.environ.get("GITHUB_TOKEN", "")
        if not _token:
            try:
                _token = subprocess.run(
                    ["gh", "auth", "token"], capture_output=True, text=True, timeout=10
                ).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                _token = ""
    return _token


def _wait(bucket: str) -> None:
    gap = SPACING.get(bucket, 1.0) - (time.monotonic() - _last.get(bucket, 0.0))
    if gap > 0:
        time.sleep(gap)
    _last[bucket] = time.monotonic()


def _cache_file(url: str) -> Path:
    return cache_dir() / "http" / (hashlib.sha256(url.encode()).hexdigest() + ".json")


def get(url: str, ttl: float = 86400, bucket: str | None = None, accept: str | None = None) -> bytes:
    """GET with an on-disk cache. ttl=-1 caches forever (use for content pinned to a commit SHA)."""
    cf = _cache_file(url)
    if cf.exists():
        entry = json.loads(cf.read_text())
        if ttl < 0 or time.time() - entry["ts"] < ttl:
            return entry["body"].encode("latin-1")
    host = urllib.parse.urlparse(url).hostname or ""
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    if host == "api.github.com" and github_token():
        headers["Authorization"] = f"Bearer {github_token()}"
    for attempt in range(3):
        _wait(bucket or host)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise FetchError(f"response too large: {url}")
                _respect_remaining(resp.headers)
                break
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                delay = _backoff(e.headers)
                if delay is not None:
                    print(f"[http] rate limited, sleeping {delay:.0f}s", file=sys.stderr)
                    time.sleep(delay)
                    continue
            raise FetchError(f"{e.code} {url}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                raise FetchError(f"{e} {url}") from e
            time.sleep(2 ** attempt)
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps({"ts": time.time(), "url": url, "body": body.decode("latin-1")}))
    return body


def get_json(url: str, **kw):
    return json.loads(get(url, accept=kw.pop("accept", "application/vnd.github+json"), **kw))


def _backoff(headers) -> float | None:
    """Seconds to wait before a retry, or None when the wait is too long to be worth it."""
    if headers.get("Retry-After"):
        delay = float(headers["Retry-After"])
    elif headers.get("X-RateLimit-Remaining") == "0" and headers.get("X-RateLimit-Reset"):
        delay = float(headers["X-RateLimit-Reset"]) - time.time() + 1
    else:
        delay = 60.0
    return delay if delay <= 300 else None


def _respect_remaining(headers) -> None:
    if headers.get("X-RateLimit-Remaining") == "0" and headers.get("X-RateLimit-Reset"):
        delay = float(headers["X-RateLimit-Reset"]) - time.time() + 1
        if 0 < delay <= 300:
            time.sleep(delay)
