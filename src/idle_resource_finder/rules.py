"""Core idle detection logic."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from .errors import IdleError
from .models import Finding, Report, Resource, Thresholds

_DEFAULT_THRESHOLDS = Thresholds()


def _days_between(start: datetime, now: datetime) -> int:
    """Whole days elapsed from start to now."""
    return (now - start).days


def find_idle(
    resources: Sequence[Resource],
    *,
    now: datetime,
    thresholds: Thresholds = _DEFAULT_THRESHOLDS,
) -> Report:
    """Evaluate idle rules on resources and produce findings.

    Args:
        resources: sequence of Resource objects (must have unique ids).
        now: current time (must be timezone-aware).
        thresholds: rule thresholds.

    Raises:
        IdleError: with 'invalid_now' if now is naive, or 'duplicate_id' if ids repeat.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise IdleError("invalid_now", "now must be timezone-aware")

    # Duplicate check (even though load_inventory already ensures uniqueness)
    seen: set[str] = set()
    for res in resources:
        if res.id in seen:
            raise IdleError("duplicate_id", f"duplicate resource id {res.id!r}")
        seen.add(res.id)

    resource_ids = {res.id for res in resources}
    findings: list[Finding] = []
    exempted = 0

    for res in resources:
        # Exemption
        if res.tags.get(thresholds.exempt_tag) == "true":
            exempted += 1
            continue

        rule: str | None = None
        detail: str | None = None

        # Rule 1: unattached volume
        if res.type == "volume" and res.attached_to is None:
            # age from state_since else created_at
            timestamp = res.state_since if res.state_since is not None else res.created_at
            if timestamp is not None:
                days = _days_between(timestamp, now)
                if days >= thresholds.min_age_days:
                    rule = "unattached_volume"
                    detail = f"unattached for {days} days"

        # Rule 2: stopped instance
        if (
            rule is None
            and res.type == "instance"
            and res.state == "stopped"
            and res.state_since is not None
        ):
            days = _days_between(res.state_since, now)
            if days >= thresholds.stopped_days:
                rule = "stopped_instance"
                detail = f"stopped for {days} days"

        # Rule 3: idle instance
        if rule is None and res.type == "instance" and res.state == "running":
            metrics = res.metrics
            if (
                "days" in metrics
                and metrics["days"] >= thresholds.metrics_min_days
                and "cpu_p95_pct" in metrics
                and metrics["cpu_p95_pct"] < thresholds.cpu_p95_pct
                and "net_bytes_per_day" in metrics
                and metrics["net_bytes_per_day"] < thresholds.net_bytes_per_day
            ):
                metric_days = metrics["days"]
                cpu = metrics["cpu_p95_pct"]
                rule = "idle_instance"
                detail = f"cpu p95 {cpu}% over {metric_days} days"

        # Rule 4: unassociated ip
        if rule is None and res.type == "ip" and res.attached_to is None:
            rule = "unassociated_ip"
            detail = "not associated"

        # Rule 5: orphaned snapshot
        if rule is None and res.type == "snapshot" and res.created_at is not None:
            days = _days_between(res.created_at, now)
            if (
                days >= thresholds.snapshot_days
                and res.source_id is not None
                and res.source_id not in resource_ids
            ):
                rule = "orphaned_snapshot"
                detail = f"source {res.source_id} missing, {days} days old"

        # Rule 6: idle load balancer
        if rule is None and res.type == "load_balancer":
            metrics = res.metrics
            if (
                "requests_per_day" in metrics
                and metrics["requests_per_day"] == 0
                and "days" in metrics
                and metrics["days"] >= thresholds.metrics_min_days
            ):
                metric_days = metrics["days"]
                rule = "idle_load_balancer"
                detail = f"no requests over {metric_days} days"

        if rule is not None and detail is not None:
            findings.append(
                Finding(
                    resource_id=res.id,
                    rule=rule,
                    monthly_savings=res.monthly_cost,
                    detail=detail,
                )
            )

    # Sort by monthly_savings descending, then resource_id ascending
    findings.sort(key=lambda f: (-f.monthly_savings, f.resource_id))

    total = Decimal("0")
    for f in findings:
        total += f.monthly_savings

    return Report(findings=findings, total_monthly_savings=total, exempted=exempted)
