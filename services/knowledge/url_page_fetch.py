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
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

logger = logging.getLogger(__name__)

MAX_FETCH_BYTES = 2 * 1024 * 1024
_FETCH_TIMEOUT = httpx.Timeout(30.0)

_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
)

_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_PLAIN_CONTENT_TYPES = ("text/plain", "application/json")


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


def _parse_ip_literal(host: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    cleaned = (host or "").strip().strip("[]")
    if not cleaned:
        return None
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def _resolve_public_connect_ip(host: str) -> str:
    """Resolve host once and return a public IP for connecting (SSRF pin)."""
    literal = _parse_ip_literal(host)
    if literal is not None:
        if _ip_is_blocked(literal):
            raise HTTPException(status_code=400, detail="URL host is not allowed")
        return str(literal)

    lowered = (host or "").strip().lower()
    if lowered in {"localhost"} or not lowered:
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise HTTPException(status_code=400, detail="URL host is not allowed") from exc
    if not infos:
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    public_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="URL host is not allowed") from exc
        if _ip_is_blocked(ip):
            raise HTTPException(status_code=400, detail="URL host is not allowed")
        public_ips.append(ip)

    # Prefer IPv4 for broader httpx/SNI compatibility.
    for ip in public_ips:
        if isinstance(ip, ipaddress.IPv4Address):
            return str(ip)
    return str(public_ips[0])


def _pinned_netloc(connect_ip: str, port: Optional[int]) -> str:
    is_ipv6 = ":" in connect_ip
    host_part = f"[{connect_ip}]" if is_ipv6 else connect_ip
    if port is None:
        return host_part
    return f"{host_part}:{port}"


def _host_header_value(hostname: str, port: Optional[int], scheme: str) -> str:
    if port is None:
        return hostname
    default = 443 if scheme == "https" else 80
    if port == default:
        return hostname
    return f"{hostname}:{port}"


def _clean_extracted_text(text: str) -> str:
    cleaned = re.sub(r"[ \t]+\n", "\n", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_html_title(soup: BeautifulSoup) -> Optional[str]:
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = str(og_title["content"]).strip()
        if title:
            return re.sub(r"\s+", " ", title)
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return re.sub(r"\s+", " ", title)
    return None


def _extract_html_body_text(raw_html: str) -> Tuple[str, Optional[str]]:
    """Extract readable body text and title from HTML."""
    soup = BeautifulSoup(raw_html, "html.parser")
    title = _extract_html_title(soup)

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = _clean_extracted_text(root.get_text("\n", strip=True))
    return text, title


def fallback_title_from_url(page_url: str) -> str:
    """Build a short filesystem-safe title when the page has no <title>."""
    parsed = urlparse(page_url.strip())
    host = (parsed.hostname or "page").removeprefix("www.")
    path = (parsed.path or "").strip("/").replace("/", "-")
    slug = f"{host}-{path}" if path else host
    slug = re.sub(r"[^A-Za-z0-9._\u4e00-\u9fff-]+", "-", slug).strip("-._")
    return (slug or "web-page")[:80]


async def _read_stream_capped(response: httpx.Response) -> bytes:
    """Read response body with a hard byte cap (abort mid-stream when exceeded)."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_FETCH_BYTES:
            raise HTTPException(status_code=413, detail="Page too large")
        chunks.append(chunk)
    return b"".join(chunks)


async def fetch_url_page_text(url: str) -> Tuple[str, Optional[str]]:
    """Fetch a public web page and return plain text plus document title."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")

    hostname = parsed.hostname or ""
    connect_ip = _resolve_public_connect_ip(hostname)
    pinned_url = urlunparse(
        (
            parsed.scheme,
            _pinned_netloc(connect_ip, parsed.port),
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",
        )
    )

    headers = {
        "User-Agent": "MindGraphCanvas/1.0 (+https://mg.mindspringedu.com)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        "Host": _host_header_value(hostname, parsed.port, parsed.scheme),
    }
    extensions = {"sni_hostname": hostname} if parsed.scheme == "https" else None

    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=False) as client:
            async with client.stream(
                "GET",
                pinned_url,
                headers=headers,
                extensions=extensions,
            ) as response:
                if 300 <= response.status_code < 400:
                    raise HTTPException(status_code=400, detail="Redirects are not allowed")
                if response.status_code >= 400:
                    raise HTTPException(status_code=502, detail="Failed to fetch page")

                content_type = (response.headers.get("content-type") or "").lower()
                if content_type and not (
                    any(ct in content_type for ct in _HTML_CONTENT_TYPES)
                    or any(ct in content_type for ct in _PLAIN_CONTENT_TYPES)
                ):
                    raise HTTPException(
                        status_code=422,
                        detail="Unsupported content type for web extract",
                    )

                raw_bytes = await _read_stream_capped(response)
                encoding = response.charset_encoding or "utf-8"
                raw = raw_bytes.decode(encoding, errors="replace")

                if any(ct in content_type for ct in _PLAIN_CONTENT_TYPES):
                    text = raw.strip()
                    title = None
                else:
                    text, title = _extract_html_body_text(raw)

                if not text:
                    raise HTTPException(status_code=422, detail="No readable text found on page")
                return text, title
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timeout fetching page") from exc
    except httpx.RequestError as exc:
        logger.warning("url page fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch page") from exc
