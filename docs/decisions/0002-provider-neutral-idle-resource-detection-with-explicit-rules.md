# Provider-neutral idle resource detection with explicit rules

Status: accepted (generated, pending human review)

## Context

Cloud bills contain idle resources; consoles present them with differing semantics. Need a reusable, offline, provider-neutral way to identify them.

## Decision

Implement a pure Python library that parses a normalized JSON inventory, applies six explicit rules with configurable thresholds, and ranks findings by Decimal monthly savings. No cloud SDKs or external services.

## Consequences

Teams can run the same rule set across providers and in CI; Decimal avoids float errors; offline operation ensures reproducibility; limitations: requires normalized inventory and does not call cloud APIs.
