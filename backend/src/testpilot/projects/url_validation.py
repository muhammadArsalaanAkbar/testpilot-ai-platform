"""SSRF guard for project target URLs (SEC-006, FR-035, FR-135).

Re-validated immediately before execution-engine navigation too (plan.md
Security Architecture), not only at project-creation time — a project's
URL can be edited between creation and a later test run.
"""

import asyncio
import ipaddress
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from testpilot.core.exceptions import InvalidUrlError, UrlNotPublicError

_ALLOWED_SCHEMES = {"http", "https"}

Resolver = Callable[[str], Awaitable[list[str]]]


async def _default_resolver(hostname: str) -> list[str]:
    loop = asyncio.get_running_loop()
    addr_infos = await loop.getaddrinfo(hostname, None)
    return [str(info[4][0]) for info in addr_infos]


async def validate_public_url(url: str, *, resolver: Resolver = _default_resolver) -> None:
    """Rejects malformed URLs and URLs that resolve to a private, loopback,
    link-local, reserved, carrier-grade-NAT, or multicast network address.

    DNS resolution failure does NOT raise: FR-026 treats reachability as a
    non-blocking warning, not a hard block — this guard's job is only to
    reject *known* non-public targets, not to prove a target is reachable.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.hostname:
        raise InvalidUrlError(f"{url!r} is not a valid http(s) URL")

    try:
        addresses = await resolver(parsed.hostname)
    except OSError:
        return

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            raise UrlNotPublicError(f"{url!r} resolved to an unparseable network address") from None
        if ip.is_multicast or not ip.is_global:
            raise UrlNotPublicError(f"{url!r} resolves to a non-public network address")
