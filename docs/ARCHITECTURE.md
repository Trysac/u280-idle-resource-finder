# Architecture

## Overview

The library is split into several small modules:

- `models.py`: frozen dataclasses for thresholds, resources, findings, reports.
- `errors.py`: `IdleError` with stable error codes.
- `inventory.py`: parsing and validation of the JSON inventory.
- `rules.py`: core idle detection logic with the six rules.
- `render.py`: output formatting as text or JSON.
- `__main__.py`: command-line interface.

All modules are dependency-free and use only the Python standard library.

## Design decisions

- **Frozen dataclasses** ensure immutability and easy reasoning.
- **Decimal for costs** avoids floating point errors.
- **Provider-neutral inventory** decouples from cloud APIs.
- **Configurable thresholds** allow tuning per environment.
- **Offline and deterministic** makes it suitable for CI.

For ADRs, see `docs/decisions/`.
