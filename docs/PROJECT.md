# Project record

## Objective

Find idle cloud resources in a provider-neutral JSON inventory: unattached volumes, idle or long-stopped instances, free IPs, orphaned snapshots, with Decimal savings.

## Scope

In scope: loading and validating a provider-neutral JSON inventory; applying the six idle rules with configurable thresholds; producing text or JSON reports; the command-line interface; the typed public API; and tests for those behaviors.

Out of scope: calling cloud APIs, converting provider exports (documented recipe only), pricing lookups, and deleting resources.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 8681945 / 306060 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.5995 |

## Factory run u280 (measured from API usage)

| Date (UTC) | Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-10 | generation | deepseek-v4-pro | yes | 2070 | 18880 | 0 | 3200 | 0.0388 |
| 2026-11-10 | fix-1 | deepseek-flash | no | 38962 | 27205 | 0 | 1041408 | 0.0253 |
| 2026-11-10 | fix-2 | deepseek-flash | no | 37576 | 31794 | 0 | 1302912 | 0.0286 |
| 2026-11-10 | fix-3 | deepseek-flash | no | 72503 | 33952 | 0 | 2123392 | 0.0376 |
| 2026-11-10 | fix-4 | deepseek-flash | no | 69735 | 18526 | 0 | 1728512 | 0.0268 |
| 2026-11-11 | fix-1 | deepseek-v4-pro | no | 30492 | 27910 | 0 | 341504 | 0.0829 |
| 2026-11-11 | fix-2 | deepseek-v4-pro | no | 27430 | 41277 | 0 | 480000 | 0.1104 |
| 2026-11-11 | fix-3 | deepseek-v4-pro | no | 30783 | 39273 | 0 | 414080 | 0.1072 |
| 2026-11-11 | fix-4 | deepseek-v4-pro | no | 17182 | 19217 | 0 | 283520 | 0.0556 |
| 2026-11-11 | fix-1 | deepseek-v4-pro | no | 13842 | 3094 | 0 | 36352 | 0.0161 |
| 2026-11-11 | audit | deepseek-flash | no | 35005 | 22481 | 0 | 371072 | 0.0199 |
| 2026-11-11 | fix-2 | deepseek-v4-pro | no | 13315 | 9405 | 0 | 77184 | 0.0291 |
| 2026-11-11 | docs | deepseek-flash | no | 89658 | 13046 | 0 | 256 | 0.0213 |

Total: $0.5995. Prices: deepseek line, as measured by its adapter. Providers serve the current version of each model id, so the date tells which version answered; versions, launch stages and price sources per line are in the factory's model register (docs/MODELS.md).
