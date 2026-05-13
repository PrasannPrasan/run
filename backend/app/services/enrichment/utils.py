from __future__ import annotations

import hashlib
from urllib.parse import urlparse


def canonicalize_linkedin_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().replace("www.", "")
    if host not in {"linkedin.com"}:
        return url.strip()
    path = parsed.path.rstrip("/")
    return f"https://www.linkedin.com{path}"


def profile_hash(linkedin_url: str) -> str:
    normalized = canonicalize_linkedin_url(linkedin_url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

