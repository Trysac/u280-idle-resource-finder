# Security

## Threat Model

### Defended

- The library processes user-supplied JSON input and enforces `max_bytes` (default `10_485_760` UTF-8 bytes) before parsing.
- The number of resources is limited by `max_resources` (default `100_000`).
- Resource ids are limited to 1-256 characters; required `type` is checked; optional string fields are type-checked.
- Timestamps must be RFC 3339 with a timezone offset; a trailing `Z` is replaced with `+00:00` before `datetime.fromisoformat`.
- `monthly_cost` is parsed as `Decimal`, must be finite, and must be non-negative.
- Only the known metric keys `cpu_p95_pct`, `net_bytes_per_day`, `requests_per_day`, and `days` are read; booleans and non-finite numbers are rejected.
- Duplicate resource ids are rejected by both `load_inventory` and `find_idle`.
- Errors are raised as `IdleError` with a machine-readable code; messages are truncated to 200 characters and do not include tag values.
- The library performs no network access, has no secrets, uses no dynamic imports, and installs a `NullHandler` on its logger.

### Not defended

- Inventory contents are not authenticated or integrity-checked; the library treats them as trusted input data.
- Resource ids, details, and tags are not escaped for terminal output. If those strings contain control characters, text or JSON rendering can emit them unchanged.
- Tags are type-checked as string keys and values but have no individual length limit; only the overall UTF-8 byte limit applies.
- Resource types are not restricted to a fixed set; unknown types are kept and match no rule.
- There is no rate limiting, sandboxing, or memory isolation beyond the input size and resource count limits.
- The library does not delete resources, call cloud APIs, or verify prices.

## Handling Untrusted Input

- JSON parsing uses the standard library parser after the UTF-8 byte-size check.
- All fields used by the rules are validated; malformed input raises typed errors.
- Error messages include resource indexes and field names, but not tag values.
- Logging uses a `NullHandler`; the library does not log inventory contents.

## Recommendations

- In production, set lower `max_bytes` and `max_resources` limits appropriate to the inventory source.
- Treat inventory data as trusted configuration data; if it is untrusted, sanitize resource ids and tags before displaying text output.
- Review inventory data before feeding it to the library.
