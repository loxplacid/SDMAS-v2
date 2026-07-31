from __future__ import annotations

from typing import Any

from app.domains.migration.base import MigratorResult
from app.domains.migration.schemas import MigrationSummary


def build_summary(result: MigratorResult) -> MigrationSummary:
    """Build a structured summary from a migrator result."""
    return MigrationSummary(
        entity_type=result.entity_type,
        total=result.total,
        imported=result.imported,
        skipped=result.skipped,
        errors=result.errors,
        warnings=result.warnings,
        duration_seconds=result.duration_seconds,
        status="completed" if result.errors == 0 else "completed_with_errors",
        error_details=result.error_details[:50],
    )


def format_report_text(summaries: list[MigrationSummary]) -> str:
    """Generate a human-readable migration report."""
    lines: list[str] = [
        "=" * 72,
        "  MIGRATION REPORT",
        "=" * 72,
        "",
    ]

    overall = {"total": 0, "imported": 0, "skipped": 0, "errors": 0, "warnings": 0}

    for s in summaries:
        overall["total"] += s.total
        overall["imported"] += s.imported
        overall["skipped"] += s.skipped
        overall["errors"] += s.errors
        overall["warnings"] += s.warnings

        duration = f"{s.duration_seconds:.1f}s" if s.duration_seconds else "N/A"
        status_icon = "OK" if s.errors == 0 else "!!"

        lines.append(f"  [{status_icon}] {s.entity_type}")
        lines.append(f"      Total:     {s.total}")
        lines.append(f"      Imported:  {s.imported}")
        lines.append(f"      Skipped:   {s.skipped}")
        lines.append(f"      Warnings:  {s.warnings}")
        lines.append(f"      Errors:    {s.errors}")
        lines.append(f"      Duration:  {duration}")
        lines.append(f"      Status:    {s.status}")

        if s.error_details:
            lines.append(f"      Errors ({len(s.error_details)}):")
            for i, err in enumerate(s.error_details[:10], 1):
                lines.append(f"        {i}. [{err.get('legacy_id', '?')}] "
                             f"{err.get('subtype', '')} — {err.get('error', '?')}")
            if len(s.error_details) > 10:
                lines.append(f"        ... and {len(s.error_details) - 10} more errors")
        lines.append("")

    lines.append("-" * 72)
    lines.append(f"  OVERALL")
    lines.append(f"      Total:     {overall['total']}")
    lines.append(f"      Imported:  {overall['imported']}")
    lines.append(f"      Skipped:   {overall['skipped']}")
    lines.append(f"      Warnings:  {overall['warnings']}")
    lines.append(f"      Errors:    {overall['errors']}")
    lines.append("-" * 72)

    return "\n".join(lines)


def format_error_report(summaries: list[MigrationSummary]) -> str:
    """Generate a detailed error-only report for operators."""
    lines: list[str] = [
        "=" * 72,
        "  MIGRATION ERROR REPORT",
        "=" * 72,
        "",
    ]

    has_errors = False
    for s in summaries:
        if not s.error_details:
            continue
        has_errors = True
        lines.append(f"  Entity: {s.entity_type} ({len(s.error_details)} errors)")
        lines.append("")
        for i, err in enumerate(s.error_details, 1):
            lines.append(f"  #{i}")
            lines.append(f"      Legacy ID:  {err.get('legacy_id', '?')}")
            lines.append(f"      Subtype:    {err.get('subtype', '-')}")
            lines.append(f"      Error:      {err.get('error', '?')}")
            if "field" in err:
                lines.append(f"      Field:      {err['field']}")
            if "value" in err:
                lines.append(f"      Value:      {err['value']}")
            lines.append("")

    if not has_errors:
        lines.append("  No errors found.")

    lines.append("-" * 72)
    return "\n".join(lines)
