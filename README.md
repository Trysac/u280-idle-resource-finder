# idle-resource-finder

[![PyPI version](https://img.shields.io/pypi/v/trysac-idle-resource-finder)](https://pypi.org/project/trysac-idle-resource-finder/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-idle-resource-finder)](LICENSE)
[![CI](https://github.com/Trysac/u280-idle-resource-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u280-idle-resource-finder/actions/workflows/ci.yml)

Find idle cloud resources in a provider-neutral JSON inventory: unattached volumes, idle or long-stopped instances, free IPs, orphaned snapshots, with Decimal savings

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-idle-resource-finder
# or
uv add trysac-idle-resource-finder
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import idle_resource_finder

# normalize() trims surrounding whitespace and lower-cases the text.
print(idle_resource_finder.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    idle_resource_finder.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
