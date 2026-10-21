"""Bounded open-access PDF downloads. Search results are untrusted URLs, including their redirects."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

MAX_PDF_BYTES = 30 * 1024 * 1024


async def public_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("Only public HTTP(S) PDF URLs are supported")
    hosts = await asyncio.to_thread(socket.getaddrinfo, p.hostname, p.port or (443 if p.scheme == "https" else 80),
                                    type=socket.SOCK_STREAM)
    if not hosts or any(not ipaddress.ip_address(h[4][0]).is_global for h in hosts):
        raise ValueError("Private/local PDF URLs are not allowed")


async def pdf_bytes(url: str) -> bytes:
    return await asyncio.wait_for(_pdf_bytes(url), timeout=25)


async def pdf_bytes_limited(url: str, max_bytes: int) -> bytes:
    return await asyncio.wait_for(_pdf_bytes(url, min(MAX_PDF_BYTES, max_bytes)), timeout=25)


async def _pdf_bytes(url: str, max_bytes: int | None = None) -> bytes:
    max_bytes = MAX_PDF_BYTES if max_bytes is None else min(MAX_PDF_BYTES, max_bytes)
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as c:
        for _ in range(4):
            await public_url(url)
            async with c.stream("GET", url, headers={"User-Agent": "PhD-Research-Lab/5"}) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code == 429:
                    raise ValueError("PDF source rate limited the request; retry after " + r.headers.get("retry-after", "the provider's cooldown")[:120])
                r.raise_for_status()
                data = bytearray()
                async for chunk in r.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ValueError("PDF exceeds the 30 MB download limit")
                if not data.startswith(b"%PDF"):
                    raise ValueError("The publisher returned a page instead of an open-access PDF")
                return bytes(data)
    raise ValueError("Too many redirects while downloading PDF")
