"""Tests for idle_resource_finder package."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from idle_resource_finder import (
    Finding,
    IdleError,
    Report,
    Resource,
    Thresholds,
    find_idle,
    load_inventory,
    render,
)


def make_inventory_json(resources: list[dict[str, Any]]) -> str:
    return json.dumps(resources, default=str)


class TestLoadInventory:
    def test_simple(self) -> None:
        text = make_inventory_json(
            [
                {
                    "id": "vol-1",
                    "type": "volume",
                    "attached_to": None,
                    "monthly_cost": "8.00",
                }
            ]
        )
        resources = load_inventory(text)
        assert len(resources) == 1
        r = resources[0]
        assert r.id == "vol-1"
        assert r.type == "volume"
        assert r.attached_to is None
        assert r.monthly_cost == Decimal("8.00")

    def test_input_too_large(self) -> None:
        text = "x" * (10_485_760 + 1)
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "input_too_large"

    def test_too_many_resources(self) -> None:
        text = make_inventory_json([{"id": f"r{i}", "type": "ip"} for i in range(100_001)])
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "too_many_resources"

    def test_invalid_json(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory("not json")
        assert exc.value.code == "invalid_json"

    def test_duplicate_id(self) -> None:
        text = make_inventory_json(
            [
                {"id": "vol-1", "type": "volume"},
                {"id": "vol-1", "type": "ip"},
            ]
        )
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "duplicate_id"

    def test_invalid_resource_no_type(self) -> None:
        resources = [
            {"id": "a", "type": "volume"},
            {"id": "b", "type": "instance"},
            {"id": "c", "type": "ip"},
            {"id": "d"},  # index 3 missing type
        ]
        text = make_inventory_json(resources)
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"
        assert "index 3" in exc.value.message

    def test_invalid_resource_negative_cost(self) -> None:
        resources = [{"id": "vol-1", "type": "volume", "monthly_cost": "-1"}]
        text = make_inventory_json(resources)
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_invalid_resource_naive_timestamp(self) -> None:
        resources = [
            {
                "id": "vol-1",
                "type": "volume",
                "created_at": "2026-10-01T00:00:00",
            }
        ]
        text = make_inventory_json(resources)
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_number_cost_parsed_as_decimal(self) -> None:
        resources = [{"id": "vol-1", "type": "volume", "monthly_cost": 12.5}]
        text = make_inventory_json(resources)
        result = load_inventory(text)
        assert result[0].monthly_cost == Decimal("12.5")

    def test_tags_validation(self) -> None:
        resources = [{"id": "v1", "type": "volume", "tags": {"idle-ok": "true"}}]
        text = make_inventory_json(resources)
        result = load_inventory(text)
        assert result[0].tags == {"idle-ok": "true"}

    def test_metrics_extraction(self) -> None:
        resources = [
            {
                "id": "i1",
                "type": "instance",
                "metrics": {
                    "cpu_p95_pct": 2.5,
                    "net_bytes_per_day": 1000000,
                    "requests_per_day": 0,
                    "days": 14,
                },
            }
        ]
        text = make_inventory_json(resources)
        result = load_inventory(text)
        assert result[0].metrics == {
            "cpu_p95_pct": 2.5,
            "net_bytes_per_day": 1000000,
            "requests_per_day": 0,
            "days": 14,
        }


class TestFindIdle:
    NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)

    def test_unattached_volume(self) -> None:
        res = Resource(
            id="vol-1",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("8.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == [
            Finding("vol-1", "unattached_volume", Decimal("8.00"), "unattached for 39 days")
        ]

    def test_unattached_volume_below_threshold(self) -> None:
        res = Resource(
            id="vol-2",
            type="volume",
            created_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("5.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == []

    def test_idle_instance(self) -> None:
        res = Resource(
            id="i-1",
            type="instance",
            state="running",
            metrics={"cpu_p95_pct": 2.5, "net_bytes_per_day": 1000000, "days": 14},
            monthly_cost=Decimal("10.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "idle_instance"
        assert report.findings[0].detail == "cpu p95 2.5% over 14 days"

    def test_idle_instance_cpu_at_threshold(self) -> None:
        res = Resource(
            id="i-2",
            type="instance",
            state="running",
            metrics={"cpu_p95_pct": 5.0, "net_bytes_per_day": 1000000, "days": 14},
            monthly_cost=Decimal("10.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == []

    def test_idle_instance_metrics_below_window(self) -> None:
        res = Resource(
            id="i-3",
            type="instance",
            state="running",
            metrics={"cpu_p95_pct": 2.5, "net_bytes_per_day": 1000000, "days": 6},
            monthly_cost=Decimal("10.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == []

    def test_stopped_instance(self) -> None:
        res = Resource(
            id="i-4",
            type="instance",
            state="stopped",
            state_since=datetime(2026, 9, 1, tzinfo=timezone.utc),
            monthly_cost=Decimal("12.50"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "stopped_instance"
        assert report.findings[0].detail == "stopped for 69 days"

    def test_stopped_instance_below_threshold(self) -> None:
        res = Resource(
            id="i-5",
            type="instance",
            state="stopped",
            state_since=datetime(2026, 10, 20, tzinfo=timezone.utc),
            monthly_cost=Decimal("12.50"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == []

    def test_orphaned_snapshot(self) -> None:
        resources = [
            Resource(
                id="snap-1",
                type="snapshot",
                created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                source_id="vol-gone",
                monthly_cost=Decimal("5.00"),
            )
        ]
        report = find_idle(resources, now=self.NOW)
        assert report.findings[0].rule == "orphaned_snapshot"
        assert report.findings[0].detail == "source vol-gone missing, 131 days old"

    def test_unassociated_ip(self) -> None:
        res = Resource(
            id="ip-1",
            type="ip",
            attached_to=None,
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "unassociated_ip"
        assert report.findings[0].detail == "not associated"

    def test_idle_load_balancer(self) -> None:
        res = Resource(
            id="lb-1",
            type="load_balancer",
            metrics={"requests_per_day": 0, "days": 14},
            monthly_cost=Decimal("20.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "idle_load_balancer"
        assert report.findings[0].detail == "no requests over 14 days"

    def test_exempted_resource(self) -> None:
        res = Resource(
            id="vol-1",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("8.00"),
            tags={"idle-ok": "true"},
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == []
        assert report.exempted == 1

    def test_sorting_and_total(self) -> None:
        res1 = Resource(
            id="vol-1",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("12.50"),
        )
        res2 = Resource(
            id="vol-2",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("8.00"),
        )
        report = find_idle([res1, res2], now=self.NOW)
        assert report.total_monthly_savings == Decimal("20.50")
        assert [f.resource_id for f in report.findings] == ["vol-1", "vol-2"]  # descending cost

    def test_duplicate_id_raises(self) -> None:
        res1 = Resource(id="vol-1", type="volume")
        res2 = Resource(id="vol-1", type="volume")
        with pytest.raises(IdleError) as exc:
            find_idle([res1, res2], now=self.NOW)
        assert exc.value.code == "duplicate_id"

    def test_invalid_now_naive(self) -> None:
        res = Resource(id="vol-1", type="volume")
        with pytest.raises(IdleError) as exc:
            find_idle([res], now=datetime(2026, 11, 9))
        assert exc.value.code == "invalid_now"

    def test_edge_exact_threshold(self) -> None:
        # Volume exactly at min_age_days
        res = Resource(
            id="vol-exact",
            type="volume",
            created_at=datetime(2026, 11, 9, tzinfo=timezone.utc) - timedelta(days=7),
            attached_to=None,
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "unattached_volume"
        assert "7 days" in report.findings[0].detail

    def test_edge_volume_state_since_newer(self) -> None:
        res = Resource(
            id="vol-state-newer",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            state_since=datetime(2026, 10, 10, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].detail == "unattached for 30 days"

    def test_edge_stopped_exact_threshold(self) -> None:
        res = Resource(
            id="i-exact",
            type="instance",
            state="stopped",
            state_since=self.NOW - timedelta(days=30),
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "stopped_instance"
        assert report.findings[0].detail == "stopped for 30 days"

    def test_edge_snapshot_exact_threshold(self) -> None:
        res = Resource(
            id="snap-exact",
            type="snapshot",
            created_at=self.NOW - timedelta(days=90),
            source_id="vol-gone",
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "orphaned_snapshot"
        assert report.findings[0].detail == "source vol-gone missing, 90 days old"

    def test_edge_idle_instance_exact_window(self) -> None:
        res = Resource(
            id="i-window",
            type="instance",
            state="running",
            metrics={"cpu_p95_pct": 2.5, "net_bytes_per_day": 1000, "days": 7},
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "idle_instance"
        assert report.findings[0].detail == "cpu p95 2.5% over 7 days"

    def test_edge_load_balancer_exact_window(self) -> None:
        res = Resource(
            id="lb-window",
            type="load_balancer",
            metrics={"requests_per_day": 0, "days": 7},
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].rule == "idle_load_balancer"
        assert report.findings[0].detail == "no requests over 7 days"

    def test_edge_cost_zero_kept(self) -> None:
        res = Resource(
            id="vol-zero",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("0"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings[0].monthly_savings == Decimal("0")

    def test_unknown_type_ignored(self) -> None:
        res = Resource(
            id="other",
            type="unknown",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            monthly_cost=Decimal("1.00"),
        )
        report = find_idle([res], now=self.NOW)
        assert report.findings == []


class TestRender:
    def make_report(self) -> Report:
        findings = [
            Finding("vol-1", "unattached_volume", Decimal("8.00"), "unattached for 39 days"),
            Finding("ip-1", "unassociated_ip", Decimal("1.50"), "not associated"),
        ]
        return Report(findings=findings, total_monthly_savings=Decimal("9.50"), exempted=1)

    def test_text(self) -> None:
        report = self.make_report()
        output = render(report, "text")
        expected = (
            "vol-1\tunattached_volume\t8.00\tunattached for 39 days\n"
            "ip-1\tunassociated_ip\t1.50\tnot associated\n"
            "total\t9.50\n"
        )
        assert output == expected

    def test_json(self) -> None:
        report = self.make_report()
        output = render(report, "json")
        data = json.loads(output)
        assert data == {
            "findings": [
                {
                    "resource_id": "vol-1",
                    "rule": "unattached_volume",
                    "monthly_savings": "8.00",
                    "detail": "unattached for 39 days",
                },
                {
                    "resource_id": "ip-1",
                    "rule": "unassociated_ip",
                    "monthly_savings": "1.50",
                    "detail": "not associated",
                },
            ],
            "total_monthly_savings": "9.50",
            "exempted": 1,
        }

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError):
            render(self.make_report(), "xml")  # type: ignore[arg-type]


class TestCLI:
    def test_main_no_findings_exit_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        inventory = [{"id": "vol-1", "type": "volume", "attached_to": "i-1"}]
        inv_file = tmp_path / "inv.json"
        inv_file.write_text(json.dumps(inventory))
        from idle_resource_finder.__main__ import main

        rc = main([str(inv_file)])
        assert rc == 0

    def test_main_with_findings_exit_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        inventory = [
            {
                "id": "vol-1",
                "type": "volume",
                "created_at": "2026-10-01T00:00:00Z",
                "attached_to": None,
                "monthly_cost": "8.00",
            }
        ]
        inv_file = tmp_path / "inv.json"
        inv_file.write_text(json.dumps(inventory))
        from idle_resource_finder.__main__ import main

        rc = main([str(inv_file), "--now", "2026-11-09T00:00:00Z"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "vol-1\tunattached_volume\t8.00\tunattached for 39 days" in captured.out
        assert "total\t8.00" in captured.out

    def test_main_missing_file_exit_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from idle_resource_finder.__main__ import main

        rc = main([str(tmp_path / "nonexistent.json")])
        assert rc == 2
        captured = capsys.readouterr()
        assert "error reading inventory" in captured.err

    def test_main_invalid_inventory_exit_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        inv_file = tmp_path / "inv.json"
        inv_file.write_text("not json")
        from idle_resource_finder.__main__ import main

        rc = main([str(inv_file)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "invalid inventory" in captured.err

    def test_main_json_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        inventory = [
            {
                "id": "vol-1",
                "type": "volume",
                "created_at": "2026-10-01T00:00:00Z",
                "attached_to": None,
                "monthly_cost": "8.00",
            }
        ]
        inv_file = tmp_path / "inv.json"
        inv_file.write_text(json.dumps(inventory))
        from idle_resource_finder.__main__ import main

        rc = main([str(inv_file), "--now", "2026-11-09T00:00:00Z", "--format", "json"])
        assert rc == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_monthly_savings"] == "8.00"
        assert data["findings"][0]["rule"] == "unattached_volume"


class TestInventoryValidation:
    def test_item_not_object(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([42]))
        assert exc.value.code == "invalid_resource"

    def test_missing_id(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"type": "volume"}]))
        assert exc.value.code == "invalid_resource"

    def test_id_too_long(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "x" * 257, "type": "volume"}]))
        assert exc.value.code == "invalid_resource"

    def test_non_string_state(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "state": 5}]))
        assert exc.value.code == "invalid_resource"

    def test_non_string_timestamp(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "created_at": 5}]))
        assert exc.value.code == "invalid_resource"

    def test_null_timestamps_allowed(self) -> None:
        text = json.dumps(
            [
                {
                    "id": "v",
                    "type": "volume",
                    "created_at": None,
                    "state_since": None,
                }
            ]
        )
        result = load_inventory(text)
        assert result[0].created_at is None
        assert result[0].state_since is None

    def test_invalid_state_since(self) -> None:
        text = json.dumps([{"id": "v", "type": "volume", "state_since": "2026-10-01T00:00:00"}])
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_non_string_attached_to(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "attached_to": 5}]))
        assert exc.value.code == "invalid_resource"

    def test_non_string_source_id(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "s", "type": "snapshot", "source_id": 5}]))
        assert exc.value.code == "invalid_resource"

    def test_tags_not_object(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "tags": []}]))
        assert exc.value.code == "invalid_resource"

    def test_tag_value_not_string(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "tags": {"a": 1}}]))
        assert exc.value.code == "invalid_resource"

    def test_metrics_not_object(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "metrics": []}]))
        assert exc.value.code == "invalid_resource"

    def test_metric_not_numeric(self) -> None:
        text = json.dumps([{"id": "v", "type": "volume", "metrics": {"cpu_p95_pct": "2.5"}}])
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_metric_requests_per_day_fraction_kept(self) -> None:
        text = json.dumps(
            [
                {
                    "id": "lb-1",
                    "type": "load_balancer",
                    "metrics": {"requests_per_day": 0.5, "days": 14},
                }
            ]
        )
        result = load_inventory(text)
        assert result[0].metrics["requests_per_day"] == 0.5

    def test_metric_days_fraction_rejected(self) -> None:
        text = json.dumps([{"id": "i", "type": "instance", "metrics": {"days": 6.9}}])
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_metric_days_bool_rejected(self) -> None:
        text = json.dumps([{"id": "i", "type": "instance", "metrics": {"days": True}}])
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_metric_days_nan_rejected(self) -> None:
        text = '[{"id": "i", "type": "instance", "metrics": {"days": NaN}}]'
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    @pytest.mark.parametrize("cost", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_cost_rejected(self, cost: str) -> None:
        text = json.dumps([{"id": "v", "type": "volume", "monthly_cost": cost}])
        with pytest.raises(IdleError) as exc:
            load_inventory(text)
        assert exc.value.code == "invalid_resource"

    def test_cost_invalid_string(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "monthly_cost": "abc"}]))
        assert exc.value.code == "invalid_resource"

    def test_cost_invalid_type(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory(json.dumps([{"id": "v", "type": "volume", "monthly_cost": []}]))
        assert exc.value.code == "invalid_resource"

    def test_non_array_document(self) -> None:
        with pytest.raises(IdleError) as exc:
            load_inventory("{}")
        assert exc.value.code == "invalid_json"


class TestRulesEdgeCases:
    NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)

    def test_volume_without_timestamp(self) -> None:
        res = Resource(id="vol-1", type="volume", attached_to=None)
        assert find_idle([res], now=self.NOW).findings == []

    def test_stopped_without_state_since(self) -> None:
        res = Resource(id="i-1", type="instance", state="stopped")
        assert find_idle([res], now=self.NOW).findings == []

    def test_idle_instance_missing_metrics(self) -> None:
        res = Resource(id="i-1", type="instance", state="running", metrics={})
        assert find_idle([res], now=self.NOW).findings == []

    def test_idle_instance_missing_cpu(self) -> None:
        res = Resource(
            id="i-1",
            type="instance",
            state="running",
            metrics={"days": 14, "net_bytes_per_day": 1000},
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_idle_instance_missing_net(self) -> None:
        res = Resource(
            id="i-1",
            type="instance",
            state="running",
            metrics={"days": 14, "cpu_p95_pct": 1.0},
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_idle_instance_net_at_threshold(self) -> None:
        res = Resource(
            id="i-1",
            type="instance",
            state="running",
            metrics={"days": 14, "cpu_p95_pct": 1.0, "net_bytes_per_day": 5_000_000},
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_snapshot_source_present(self) -> None:
        resources = [
            Resource(
                id="snap-1",
                type="snapshot",
                created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                source_id="vol-1",
            ),
            Resource(id="vol-1", type="volume", attached_to="i-1"),
        ]
        assert find_idle(resources, now=self.NOW).findings == []

    def test_snapshot_without_created_at(self) -> None:
        res = Resource(id="snap-1", type="snapshot", source_id="vol-gone")
        assert find_idle([res], now=self.NOW).findings == []

    def test_snapshot_below_age(self) -> None:
        res = Resource(
            id="snap-1",
            type="snapshot",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            source_id="vol-gone",
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_snapshot_without_source_id(self) -> None:
        res = Resource(
            id="snap-1",
            type="snapshot",
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_load_balancer_missing_metrics(self) -> None:
        res = Resource(id="lb-1", type="load_balancer", metrics={})
        assert find_idle([res], now=self.NOW).findings == []

    def test_load_balancer_with_requests(self) -> None:
        res = Resource(
            id="lb-1",
            type="load_balancer",
            metrics={"requests_per_day": 5, "days": 14},
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_load_balancer_fractional_requests_not_idle(self) -> None:
        res = Resource(
            id="lb-1",
            type="load_balancer",
            metrics={"requests_per_day": 0.5, "days": 14},
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_load_balancer_below_window(self) -> None:
        res = Resource(
            id="lb-1",
            type="load_balancer",
            metrics={"requests_per_day": 0, "days": 3},
        )
        assert find_idle([res], now=self.NOW).findings == []

    def test_custom_exempt_tag(self) -> None:
        res = Resource(
            id="vol-1",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            tags={"skip": "true"},
        )
        report = find_idle([res], now=self.NOW, thresholds=Thresholds(exempt_tag="skip"))
        assert report.findings == []
        assert report.exempted == 1

    def test_non_true_exempt_tag_not_exempt(self) -> None:
        res = Resource(
            id="vol-1",
            type="volume",
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            attached_to=None,
            tags={"idle-ok": "false"},
        )
        report = find_idle([res], now=self.NOW)
        assert report.exempted == 0
        assert report.findings[0].rule == "unattached_volume"


def test_error_message_is_truncated() -> None:
    error = IdleError("invalid_json", "x" * 250)
    assert len(error.message) <= 200
    assert error.message.endswith("...")


class TestAcceptanceTimestamps:
    NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)

    def test_volume_created_below_threshold_literal(self) -> None:
        resources = load_inventory(
            make_inventory_json(
                [
                    {
                        "id": "vol-1",
                        "type": "volume",
                        "created_at": "2026-11-05T00:00:00Z",
                        "attached_to": None,
                        "monthly_cost": "8.00",
                    }
                ]
            )
        )
        assert find_idle(resources, now=self.NOW).findings == []

    def test_stopped_instance_state_since_literal(self) -> None:
        resources = load_inventory(
            make_inventory_json(
                [
                    {
                        "id": "i-1",
                        "type": "instance",
                        "state": "stopped",
                        "state_since": "2026-09-01T00:00:00Z",
                        "monthly_cost": "12.50",
                    }
                ]
            )
        )
        report = find_idle(resources, now=self.NOW)
        assert report.findings[0].rule == "stopped_instance"
        assert report.findings[0].detail == "stopped for 69 days"

    def test_stopped_instance_below_threshold_literal(self) -> None:
        resources = load_inventory(
            make_inventory_json(
                [
                    {
                        "id": "i-1",
                        "type": "instance",
                        "state": "stopped",
                        "state_since": "2026-10-20T00:00:00Z",
                        "monthly_cost": "12.50",
                    }
                ]
            )
        )
        assert find_idle(resources, now=self.NOW).findings == []

    def test_orphaned_snapshot_created_at_literal(self) -> None:
        resources = load_inventory(
            make_inventory_json(
                [
                    {
                        "id": "snap-1",
                        "type": "snapshot",
                        "created_at": "2026-07-01T00:00:00Z",
                        "source_id": "vol-gone",
                        "monthly_cost": "5.00",
                    }
                ]
            )
        )
        report = find_idle(resources, now=self.NOW)
        assert report.findings[0].rule == "orphaned_snapshot"
        assert report.findings[0].detail == "source vol-gone missing, 131 days old"
