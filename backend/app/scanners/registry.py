"""Scanner registry: the one place that knows which adapters exist.

Add or replace a scanner by editing _build_default_adapters(). Everything else
(the worker, the API) goes through this registry, so scanners stay replaceable.
"""

from __future__ import annotations

from .base import ScanTarget, ScannerAdapter
from .deps_pip_audit import PipAuditAdapter
from .dynamic_safe import DynamicSafeAdapter
from .sast_bandit import BanditAdapter
from .secrets_detect import DetectSecretsAdapter


def _build_default_adapters() -> list[ScannerAdapter]:
    return [
        BanditAdapter(),
        DetectSecretsAdapter(),
        PipAuditAdapter(),
        DynamicSafeAdapter(),
    ]


class ScannerRegistry:
    def __init__(self, adapters: list[ScannerAdapter] | None = None):
        self._adapters = adapters if adapters is not None else _build_default_adapters()

    def all(self) -> list[ScannerAdapter]:
        return list(self._adapters)

    def by_name(self, name: str) -> ScannerAdapter | None:
        return next((a for a in self._adapters if a.name == name), None)

    def applicable(self, target: ScanTarget,
                   requested: list[str] | None = None) -> list[ScannerAdapter]:
        """Adapters relevant to this target, optionally filtered to a requested set."""
        chosen = []
        for a in self._adapters:
            if requested and a.name not in requested:
                continue
            if a.applies_to(target):
                chosen.append(a)
        return chosen


def default_registry() -> ScannerRegistry:
    return ScannerRegistry()
