"""
Quality gate evaluation service — Explicite AI v1.0.

Extracts and centralises quality gate logic (previously inline in projects.py).
Thresholds are named constants; changing them here changes the gate behaviour
uniformly across all call sites.
"""
from dataclasses import dataclass, field

QUALITY_GATE_VERSION = "v1.0"


@dataclass
class QualityGateResult:
    passed: bool
    failed_conditions: list[str] = field(default_factory=list)
    not_evaluated: bool = False


def evaluate(
    bugs_count: int,
    vulnerabilities_count: int,
    coverage_pct: float | None = None,
    *,
    no_analysis: bool = False,
    max_bugs: int = 0,
    max_vulnerabilities: int = 0,
    enforce_coverage: bool = False,
    coverage_target_pct: float = 80.0,
) -> QualityGateResult:
    """
    Evaluate the quality gate from analysis job counts.

    Returns a QualityGateResult with passed=True/False and a list of
    human-readable failed condition strings.

    The stored AnalysisJob.quality_gate_passed is set at analysis time
    using the same formula (vulns == 0 and bugs == 0) and must not be
    mutated; this function provides the enriched representation for API
    responses without touching the stored value.
    """
    if no_analysis:
        return QualityGateResult(
            passed=False,
            failed_conditions=["No analysis run yet"],
            not_evaluated=True,
        )

    conditions: list[str] = []

    if vulnerabilities_count > max_vulnerabilities:
        n = vulnerabilities_count
        label = "vulnerability" if n == 1 else "vulnerabilities"
        conditions.append(f"{n} {label} detected")

    if bugs_count > max_bugs:
        n = bugs_count
        label = "bug" if n == 1 else "bugs"
        conditions.append(f"{n} {label} detected")

    if (
        enforce_coverage
        and coverage_pct is not None
        and coverage_pct < coverage_target_pct
    ):
        conditions.append(
            f"coverage {coverage_pct:.1f}% below {coverage_target_pct:.0f}% target"
        )

    return QualityGateResult(passed=len(conditions) == 0, failed_conditions=conditions)
