"""Unit tests for the projects SSRF guard (T086; SEC-006, FR-035, FR-135).

DNS resolution is stubbed via an injectable resolver so these tests never
depend on real network access or real DNS — literal-IP-style assertions
without the flakiness of actual lookups.
"""

import pytest

from testpilot.core.exceptions import InvalidUrlError, UrlNotPublicError
from testpilot.projects.url_validation import validate_public_url

pytestmark = pytest.mark.anyio


def _resolver(*addresses: str):
    async def _resolve(hostname: str) -> list[str]:
        return list(addresses)

    return _resolve


async def _resolver_raises(hostname: str) -> list[str]:
    raise OSError("simulated DNS resolution failure")


async def test_rejects_malformed_url_no_scheme():
    with pytest.raises(InvalidUrlError):
        await validate_public_url("not-a-url")


async def test_rejects_unsupported_scheme():
    with pytest.raises(InvalidUrlError):
        await validate_public_url("ftp://example.com/")


async def test_rejects_url_with_no_host():
    with pytest.raises(InvalidUrlError):
        await validate_public_url("http://")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # RFC 1918 private
        "172.16.0.1",  # RFC 1918 private
        "192.168.1.1",  # RFC 1918 private
        "169.254.169.254",  # link-local / cloud metadata endpoint
        "100.64.0.1",  # RFC 6598 carrier-grade NAT
        "224.0.0.1",  # multicast
        "0.0.0.0",  # unspecified
        "::1",  # IPv6 loopback
        "fc00::1",  # IPv6 unique local
    ],
)
async def test_rejects_url_resolving_to_non_public_address(address):
    with pytest.raises(UrlNotPublicError):
        await validate_public_url("http://internal.example/", resolver=_resolver(address))


async def test_accepts_url_resolving_to_a_public_address():
    await validate_public_url("https://example.com/", resolver=_resolver("8.8.8.8"))


async def test_rejects_if_any_resolved_address_is_non_public():
    with pytest.raises(UrlNotPublicError):
        await validate_public_url("http://mixed.example/", resolver=_resolver("8.8.8.8", "10.0.0.1"))


async def test_dns_resolution_failure_does_not_raise():
    """FR-026: reachability is a non-blocking warning, not a hard block —
    the SSRF guard only rejects *known* non-public targets."""
    await validate_public_url("http://this-host-does-not-exist.invalid/", resolver=_resolver_raises)
