# Testing

## Running

```sh
pytest
```

## Policy

The repository contains a pytest module at `tests/test_idle_resource_finder.py`; its compiled artifact is `tests/__pycache__/test_idle_resource_finder.cpython-312-pytest-9.2.0.pyc`. The visible tests exercise `load_inventory` through the public package import and assert returned values and `IdleError` codes. No coverage threshold or conformance setup is configured in the code shown.

## Tiers

The tests are local unit tests in `tests/test_idle_resource_finder.py`. No CI-only conformance files or external-tool setup are present in the provided tree.

## Layout

`tests/test_idle_resource_finder.py` contains the visible `TestLoadInventory` cases:

| Test case | What it covers |
|---|---|
| `test_simple` | Loads one volume with `monthly_cost` `'8.00'`; checks `id`, `type`, `attached_to`, and `Decimal` cost. |
| `test_input_too_large` | Passes a small `max_bytes` and asserts code `'input_too_large'`. |
| `test_too_many_resources` | Builds 100_001 IP resources and asserts code `'too_many_resources'`. |
| `test_invalid_json` | Passes `'not json'` and asserts code `'invalid_json'`. |
| `test_duplicate_id` | Loads two resources with the same id and asserts code `'duplicate_id'`. |
| `test_invalid_resource_no_type` | Resource at index 3 without `type`; asserts code `'invalid_resource'` and the message names index 3. |
| `test_invalid_resource_negative_cost` | `monthly_cost` of `'-1'`; asserts code `'invalid_resource'`. |
| `test_invalid_resource_naive_timestamp` | `created_at` of `'2026-10-01T00:00:00'`; asserts code `'invalid_resource'`. |
| `test_number_cost_parsed_as_decimal` | JSON numeric cost `12.5` is read as `Decimal('12.5')`. |
| `test_tags_validation` | Tags `{'idle-ok': 'true'}` are preserved on the resource. |
| `test_metrics_extraction` | Known metric keys are extracted into the resource `metrics` map. |

No `tests/conftest.py` is present in the provided tree.
