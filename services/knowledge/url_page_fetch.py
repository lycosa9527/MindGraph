"""Fetch public web pages as plain text for Document Summary ingest.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

MAX_FETCH_BYTES = 2 * 1024 * 1024


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor for web page fetch."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        """Join extracted text chunks into a single plain-text document."""
        return re.sub(r"\n{3,}", "\n\n", "\n".join(self._chunks)).strip()


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    candidate = ip
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        candidate = ip.ipv4_mapped
    return (
        candidate.is_private
        or candidate.is_loopback
        or candidate.is_link_local
        or candidate.is_reserved
        or candidate.is_multicast
        or candidate.is_unspecified
    )


def _is_blocked_fetch_host(host: str) -> bool:
    lowered = (host or "").strip().lower()
    if lowered in {"localhost", "127.0.0.1", "::1"} or not lowered:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    if not infos:
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if _ip_is_blocked(ip):
            return True
    return False


async def fetch_url_page_text(url: str) -> Tuple[str, Optional[str]]:
    """Fetch a public web page and return plain text plus document title."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")

    host = parsed.hostname or ""
    if _is_blocked_fetch_host(host):
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    headers = {
        "User-Agent": "MindGraphCanvas/1.0 (+https://mg.mindspringedu.com)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False, headers=headers) as client:
            response = await client.get(url.strip())
            if 300 <= response.status_code < 400:
                raise HTTPException(status_code=400, detail="Redirects are not allowed")
            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail="Failed to fetch page")
            if len(response.content) > MAX_FETCH_BYTES:
                raise HTTPException(status_code=413, detail="Page too large")

            content_type = (response.headers.get("content-type") or "").lower()
            raw = response.text

            if "text/plain" in content_type or "application/json" in content_type:
                text = raw.strip()
            else:
                parser = _HTMLTextExtractor()
                parser.feed(raw)
                text = parser.get_text()

            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None

            if not text:
                raise HTTPException(status_code=422, detail="No readable text found on page")
            # Full extracted text (response body already capped by MAX_FETCH_BYTES).
            return text, title
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timeout fetching page") from exc
    except httpx.RequestError as exc:
        logger.warning("url page fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch page") from exc
