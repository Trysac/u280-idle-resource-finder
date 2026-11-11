"""Load and validate an inventory JSON."""

from __future__ import annotations

import json
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .errors import IdleError
from .models import Resource

MAX_BYTES_DEFAULT = 10_485_760
MAX_RESOURCES_DEFAULT = 100_000


def _parse_datetime(value: object) -> datetime:
    """Parse an RFC 3339 timestamp, requiring timezone offset."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp must have a timezone offset")
    return dt


def _parse_resource_item(item: Any, index: int) -> Resource:
    """Parse one inventory entry into a Resource, raising IdleError on any problem."""
    if not isinstance(item, dict):
        raise IdleError("invalid_resource", f"resource at index {index} must be an object")

    # id: required string, 1-256 chars
    raw_id = item.get("id")
    if not isinstance(raw_id, str) or not (1 <= len(raw_id) <= 256):
        raise IdleError("invalid_resource", f"resource at index {index} has invalid 'id'")

    # type: required string
    raw_type = item.get("type")
    if not isinstance(raw_type, str):
        raise IdleError("invalid_resource", f"resource at index {index} has invalid 'type'")

    # state: optional string
    state = item.get("state")
    if state is not None and not isinstance(state, str):
        raise IdleError("invalid_resource", f"resource at index {index} has invalid 'state'")

    # created_at: optional RFC3339 string
    created_at = None
    if "created_at" in item:
        raw_created = item["created_at"]
        if raw_created is not None:
            try:
                created_at = _parse_datetime(raw_created)
            except (ValueError, TypeError):
                raise IdleError(
                    "invalid_resource",
                    f"resource at index {index} has invalid 'created_at'",
                ) from None

    # state_since: optional RFC3339 string
    state_since = None
    if "state_since" in item:
        raw_state_since = item["state_since"]
        if raw_state_since is not None:
            try:
                state_since = _parse_datetime(raw_state_since)
            except (ValueError, TypeError):
                raise IdleError(
                    "invalid_resource",
                    f"resource at index {index} has invalid 'state_since'",
                ) from None

    # attached_to: optional string
    attached_to = item.get("attached_to")
    if attached_to is not None and not isinstance(attached_to, str):
        raise IdleError("invalid_resource", f"resource at index {index} has invalid 'attached_to'")

    # source_id: optional string
    source_id = item.get("source_id")
    if source_id is not None and not isinstance(source_id, str):
        raise IdleError("invalid_resource", f"resource at index {index} has invalid 'source_id'")

    # tags: optional dict[str, str]
    tags: dict[str, str] = {}
    raw_tags = item.get("tags")
    if raw_tags is not None:
        if not isinstance(raw_tags, dict):
            raise IdleError("invalid_resource", f"resource at index {index} has invalid 'tags'")
        for k, v in raw_tags.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise IdleError(
                    "invalid_resource", f"resource at index {index} has invalid tags entry"
                )
            tags[k] = v

    # metrics: only known numeric keys extracted
    metrics: dict[str, float | int] = {}
    raw_metrics = item.get("metrics")
    if raw_metrics is not None:
        if not isinstance(raw_metrics, dict):
            raise IdleError("invalid_resource", f"resource at index {index} has invalid 'metrics'")
        for key in ("cpu_p95_pct", "net_bytes_per_day", "requests_per_day", "days"):
            if key in raw_metrics:
                val = raw_metrics[key]
                if isinstance(val, bool) or not isinstance(val, (int, float, Decimal)):
                    raise IdleError(
                        "invalid_resource",
                        f"resource at index {index} has non-numeric metric '{key}'",
                    )
                if not math.isfinite(val):
                    raise IdleError(
                        "invalid_resource",
                        f"resource at index {index} has non-finite metric '{key}'",
                    )
                if key == "cpu_p95_pct":
                    metrics[key] = float(val)
                elif key == "days":
                    if val != int(val):
                        raise IdleError(
                            "invalid_resource",
                            f"resource at index {index} has non-integral metric '{key}'",
                        )
                    metrics[key] = int(val)
                else:
                    # Preserve the numeric value without lossy truncation.
                    metrics[key] = int(val) if val == int(val) else float(val)

    # monthly_cost: required (default '0'), Decimal >= 0
    monthly_cost = Decimal("0")
    if "monthly_cost" in item:
        raw_cost = item["monthly_cost"]
        if isinstance(raw_cost, Decimal):
            monthly_cost = raw_cost
        elif isinstance(raw_cost, str):
            try:
                monthly_cost = Decimal(raw_cost)
            except InvalidOperation:
                raise IdleError(
                    "invalid_resource",
                    f"resource at index {index} has invalid 'monthly_cost'",
                ) from None
        else:
            raise IdleError(
                "invalid_resource",
                f"resource at index {index} has invalid 'monthly_cost'",
            )
        if not monthly_cost.is_finite():
            raise IdleError(
                "invalid_resource",
                f"resource at index {index} has non-finite 'monthly_cost'",
            )
        if monthly_cost < 0:
            raise IdleError(
                "invalid_resource",
                f"resource at index {index} has negative 'monthly_cost'",
            )

    return Resource(
        id=raw_id,
        type=raw_type,
        state=state,
        created_at=created_at,
        state_since=state_since,
        attached_to=attached_to,
        source_id=source_id,
        tags=tags,
        metrics=metrics,
        monthly_cost=monthly_cost,
    )


def load_inventory(
    text: str,
    *,
    max_bytes: int = MAX_BYTES_DEFAULT,
    max_resources: int = MAX_RESOURCES_DEFAULT,
) -> list[Resource]:
    """Parse inventory JSON text into a list of Resource objects.

    Args:
        text: JSON string containing a list of resource objects.
        max_bytes: Maximum allowed size of ``text`` in UTF-8 bytes.
        max_resources: Maximum allowed number of resources.

    Raises:
        IdleError: with appropriate code on any validation failure.
    """
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise IdleError(
            "input_too_large",
            f"inventory size {len(encoded)} bytes exceeds limit {max_bytes}",
        )

    try:
        data = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    except json.JSONDecodeError:
        raise IdleError("invalid_json", "inventory is not valid JSON") from None

    if not isinstance(data, list):
        raise IdleError("invalid_json", "inventory must be a JSON array")

    if len(data) > max_resources:
        raise IdleError(
            "too_many_resources",
            f"resource count {len(data)} exceeds limit {max_resources}",
        )

    resources: list[Resource] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(data):
        resource = _parse_resource_item(item, i)
        if resource.id in seen_ids:
            raise IdleError("duplicate_id", f"duplicate resource id {resource.id!r}")
        seen_ids.add(resource.id)
        resources.append(resource)

    return resources
