# trysac-idle-resource-finder

[![CI](https://github.com/Trysac/u280-idle-resource-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u280-idle-resource-finder/actions/workflows/ci.yml)

Find idle cloud resources in a provider-neutral JSON inventory: unattached volumes, idle or long-stopped instances, unassociated IPs, orphaned snapshots, and idle load balancers, with Decimal savings.

## Features

- Six explicit idle rules: `unattached_volume`, `stopped_instance`, `idle_instance`, `unassociated_ip`, `orphaned_snapshot`, `idle_load_balancer`.
- Works on a normalized JSON inventory; no cloud API calls.
- Offline and deterministic; the library takes `now` explicitly, and the CLI reads the clock once.
- `Decimal` monthly costs; JSON numbers are parsed with `parse_float=Decimal` and `parse_int=Decimal`.
- One finding per resource, first matching rule in fixed order; findings are sorted by monthly savings descending, then resource id.
- Typed errors with machine-readable codes.

## Installation

```bash
pip install trysac-idle-resource-finder
```

Python >= 3.10. No runtime dependencies.

## Usage

### Library

```python
from datetime import datetime, timezone
from idle_resource_finder import load_inventory, find_idle, render

inv = '[{"id":"vol-1","type":"volume","created_at":"2026-10-01T00:00:00Z","attached_to":null,"monthly_cost":"8.00"}]'
report = find_idle(load_inventory(inv), now=datetime(2026, 11, 9, tzinfo=timezone.utc))
print(render(report, "text"), end="")
```

Output:

```text
vol-1\tunattached_volume\t8.00\tunattached for 39 days
total\t8.00
```

### Command line

```bash
python -m idle_resource_finder inv.json --now 2026-11-09T00:00:00Z
python -m idle_resource_finder inv.json --format json --min-age-days 7 --stopped-days 30
```

`--now` must be RFC 3339 with an offset. Default output is tab-separated text. Exit codes: `0` no findings, `1` findings or invalid inventory, `2` usage or I/O error.

## Public API

- `Thresholds(min_age_days=7, stopped_days=30, cpu_p95_pct=5.0, net_bytes_per_day=5_000_000, metrics_min_days=7, snapshot_days=90, exempt_tag='idle-ok')` is a frozen dataclass.
- `Resource(id, type, state=None, created_at=None, state_since=None, attached_to=None, source_id=None, tags={}, metrics={}, monthly_cost=Decimal('0'))` is a frozen dataclass. `id` must be 1-256 characters; `type` is any string; timestamps require a timezone offset; `monthly_cost` must be finite and non-negative.
- `load_inventory(text, *, max_bytes=10_485_760, max_resources=100_000) -> list[Resource]` parses a JSON array, checks UTF-8 byte length before parsing, parses JSON numbers as `Decimal`, requires unique ids, and raises `IdleError` with codes `'input_too_large'`, `'invalid_json'`, `'too_many_resources'`, `'invalid_resource'`, or `'duplicate_id'`.
- `find_idle(resources, *, now, thresholds=Thresholds()) -> Report` requires timezone-aware `now`, rejects duplicate ids, counts resources tagged `{'idle-ok': 'true'}` as exempted, sorts findings by savings descending then id, and raises `IdleError` with `'invalid_now'` or `'duplicate_id'`.
- `render(report, fmt) -> str` accepts `fmt='text'` or `fmt='json'`. Text output is tab-separated finding lines plus `total\t<amount>`. JSON output contains `findings`, `total_monthly_savings`, and `exempted`; amounts are strings. An unsupported format raises `ValueError`.
- `Finding(resource_id, rule, monthly_savings, detail)` and `Report(findings, total_monthly_savings, exempted)` are frozen dataclasses.

Rules, first match per resource:

- `unattached_volume`: volume with `attached_to` null; age from `state_since` else `created_at` is at least `min_age_days`; detail `unattached for N days`.
- `stopped_instance`: instance with state `stopped`; stopped days from `state_since` is at least `stopped_days`; detail `stopped for N days`.
- `idle_instance`: running instance with `metrics.days >= metrics_min_days`, `cpu_p95_pct < cpu_p95_pct` threshold, and `net_bytes_per_day < net_bytes_per_day` threshold; detail `cpu p95 X% over N days`.
- `unassociated_ip`: IP with `attached_to` null; detail `not associated`.
- `orphaned_snapshot`: snapshot at least `snapshot_days` old whose `source_id` is absent from the inventory ids; detail `source <id> missing, N days old`.
- `idle_load_balancer`: load balancer with `metrics.requests_per_day == 0` and `metrics.days >= metrics_min_days`; detail `no requests over N days`.

`IdleError` carries a code in `'input_too_large'`, `'invalid_json'`, `'too_many_resources'`, `'invalid_resource'`, `'duplicate_id'`, or `'invalid_now'`. Messages are truncated to 200 characters.

## Why not provider cost advisors

Provider advisors are provider-specific. This utility applies one rule set and one threshold model across providers, keeps the decision offline and reproducible in CI, and does not call cloud APIs or perform pricing lookups.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Security](docs/SECURITY.md)
- [Testing](docs/TESTING.md)

## License

MIT
