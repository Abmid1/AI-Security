"""Scope and authorization enforcement for dynamic (network) scanning.

This is deterministic, code-enforced policy — not an AI instruction. Dynamic
scans may only contact the single authorized origin, and link-local addresses
(which include cloud metadata endpoints) are always blocked as an SSRF
self-protection, even inside the authorized host.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit


def origin_of(url: str) -> str | None:
    """Return 'scheme://host[:port]' for a URL, or None if it can't be parsed."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if not parts.scheme or not parts.hostname:
        return None
    netloc = parts.hostname
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return f"{parts.scheme}://{netloc}"


def _is_link_local(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_link_local  # 169.254.0.0/16 and fe80::/10 (incl. metadata)


def _is_private_or_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


@dataclass
class ScopeDecision:
    allowed: bool
    reason: str | None = None


class ScopePolicy:
    """Decides whether a given URL may be contacted by a dynamic scan."""

    def __init__(self, allowed_origin: str, *, allow_private_hosts: bool = False):
        self.allowed_origin = allowed_origin
        self.allow_private_hosts = allow_private_hosts

    def check(self, url: str) -> ScopeDecision:
        parts = urlsplit(url)
        host = parts.hostname
        if not host:
            return ScopeDecision(False, "URL has no host")

        # Always block link-local / metadata, regardless of authorization.
        if _is_link_local(host):
            return ScopeDecision(False, "link-local/metadata address is never in scope")

        # The request must stay on the authorized origin.
        req_origin = origin_of(url)
        if req_origin != self.allowed_origin:
            return ScopeDecision(
                False,
                f"out of scope: {req_origin} is not the authorized origin "
                f"{self.allowed_origin}",
            )

        # Private/loopback only if explicitly allowed (e.g. local staging).
        if _is_private_or_loopback(host) and not self.allow_private_hosts:
            return ScopeDecision(
                False,
                "private/loopback host not permitted (set allow_private_hosts "
                "for local staging)",
            )

        return ScopeDecision(True, None)
