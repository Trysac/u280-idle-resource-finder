"""Render a report as text or JSON."""

from __future__ import annotations

import json
from typing import Literal

from .models import Report


def render(report: Report, fmt: Literal["text", "json"]) -> str:
    """Render a report in the requested format.

    Args:
        report: the report to render.
        fmt: either 'text' or 'json'.
    """
    if fmt == "text":
        lines = [
            f"{f.resource_id}\t{f.rule}\t{f.monthly_savings}\t{f.detail}" for f in report.findings
        ]
        lines.append(f"total\t{report.total_monthly_savings}")
        return "\n".join(lines) + "\n"

    if fmt == "json":
        data = {
            "findings": [
                {
                    "resource_id": f.resource_id,
                    "rule": f.rule,
                    "monthly_savings": str(f.monthly_savings),
                    "detail": f.detail,
                }
                for f in report.findings
            ],
            "total_monthly_savings": str(report.total_monthly_savings),
            "exempted": report.exempted,
        }
        return json.dumps(data)

    raise ValueError(f"unsupported format: {fmt}")
