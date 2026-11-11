"""Data models for idle-resource-finder."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Thresholds:
    """Configurable thresholds for idle detection rules."""

    min_age_days: int = 7
    stopped_days: int = 30
    cpu_p95_pct: float = 5.0
    net_bytes_per_day: int = 5_000_000
    metrics_min_days: int = 7
    snapshot_days: int = 90
    exempt_tag: str = "idle-ok"


@dataclass(frozen=True)
class Resource:
    """A normalized cloud resource from the inventory."""

    id: str
    type: str
    state: str | None = None
    created_at: datetime | None = None
    state_since: datetime | None = None
    attached_to: str | None = None
    source_id: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, float | int] = field(default_factory=dict)
    monthly_cost: Decimal = Decimal("0")


@dataclass(frozen=True)
class Finding:
    """A single idle resource finding."""

    resource_id: str
    rule: str
    monthly_savings: Decimal
    detail: str


@dataclass(frozen=True)
class Report:
    """Result of find_idle."""

    findings: list[Finding]
    total_monthly_savings: Decimal
    exempted: int
