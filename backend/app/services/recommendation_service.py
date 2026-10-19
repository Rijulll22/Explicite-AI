"""
Deterministic learning-resource recommendation service (SRS FR-LEARN-01, FR-LEARN-06).

Matching priority (highest score first):
  3 — Exact rule-key match
  2 — Exact issue-type match
  1 — Tag match for security/quality findings

Resources are ranked by score * (finding.risk_score or 1.0) across all
unresolved findings so that high-risk issues drive recommendations to the top.

This service never invents resources. It returns an empty list when no match
exists, and does not require an AI provider.
"""
import uuid
from dataclasses import dataclass
from typing import Sequence

from app.models.finding import Finding
from app.models.learning import LearningResource

# Tags considered "security-relevant" for tag-based matching
_SECURITY_TYPES = {"Vulnerability", "Security Hotspot"}
_QUALITY_TYPES = {"Code Smell", "Bug"}


@dataclass
class ResourceMatch:
    resource: LearningResource
    match_reason: str
    score: float
    is_completed: bool = False


def _match_score_and_reason(
    finding: Finding,
    resource: LearningResource,
) -> tuple[int, str] | None:
    """
    Return (priority_score, human-readable reason) or None if no match.
    Priority score: 3 = rule key, 2 = issue type, 1 = tag.
    """
    if resource.related_rule_key and resource.related_rule_key == finding.rule_key:
        return (3, f"Specifically addresses rule {finding.rule_key}")

    if resource.related_issue_type and resource.related_issue_type == finding.issue_type:
        return (2, f"Relevant to {finding.issue_type} findings")

    if resource.tag == "Security" and finding.issue_type in _SECURITY_TYPES:
        return (1, f"General security guidance relevant to {finding.issue_type} issues")

    if resource.tag == "Quality" and finding.issue_type in _QUALITY_TYPES:
        return (1, f"General quality guidance relevant to {finding.issue_type} issues")

    return None


def recommend_for_finding(
    finding: Finding,
    resources: Sequence[LearningResource],
    completed_ids: set[uuid.UUID],
) -> list[ResourceMatch]:
    """
    Return resources relevant to a single finding, ordered by priority (best first).
    Does not exclude completed resources — marks them instead.
    """
    seen: set[uuid.UUID] = set()
    results: list[ResourceMatch] = []

    for resource in resources:
        if resource.id in seen:
            continue
        match = _match_score_and_reason(finding, resource)
        if match is None:
            continue
        priority, reason = match
        seen.add(resource.id)
        results.append(ResourceMatch(
            resource=resource,
            match_reason=reason,
            score=float(priority),
            is_completed=resource.id in completed_ids,
        ))

    results.sort(key=lambda m: -m.score)
    return results


def recommend_for_project(
    findings: Sequence[Finding],
    resources: Sequence[LearningResource],
    completed_ids: set[uuid.UUID],
    max_results: int = 10,
) -> list[ResourceMatch]:
    """
    Return personalised recommendations across all unresolved findings.

    Algorithm (deterministic, explainable):
    1. For each finding, find matching resources with _match_score_and_reason().
    2. Weight the match score by the finding's risk_score (default 1.0 if None).
    3. Keep the highest-weighted match reason for each resource across all findings.
    4. Sort: uncompleted resources first, then by weighted score descending.
    5. Return at most max_results.

    Never recommends completed resources if uncompleted alternatives exist.
    """
    # best_score[resource_id] = (weighted_score, reason, finding_title)
    best: dict[uuid.UUID, tuple[float, str, str]] = {}

    for finding in findings:
        risk_weight = float(finding.risk_score or 1.0)
        for resource in resources:
            match = _match_score_and_reason(finding, resource)
            if match is None:
                continue
            priority, reason = match
            weighted = priority * risk_weight
            enriched_reason = f"{reason} (detected: {finding.title})"
            if resource.id not in best or weighted > best[resource.id][0]:
                best[resource.id] = (weighted, enriched_reason, finding.title)

    if not best:
        return []

    resources_by_id = {r.id: r for r in resources}

    results = [
        ResourceMatch(
            resource=resources_by_id[rid],
            match_reason=reason,
            score=wscore,
            is_completed=rid in completed_ids,
        )
        for rid, (wscore, reason, _) in best.items()
        if rid in resources_by_id
    ]

    # Sort: uncompleted first, then by score descending
    results.sort(key=lambda m: (m.is_completed, -m.score))
    return results[:max_results]
