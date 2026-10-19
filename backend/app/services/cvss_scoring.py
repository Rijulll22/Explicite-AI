"""
CVSS v3.1 scoring — standards-based implementation following the FIRST specification.
https://www.first.org/cvss/v3.1/specification-document

Only v3.1 base scores are computed here. v4.0 vectors are detected and returned
as (None, "4.0") so callers can store the vector without applying v3.1 formulas.
v2.0 vectors are similarly rejected.

The Roundup function is taken verbatim from the official FIRST JavaScript
reference implementation to avoid floating-point edge cases.
"""
import math
import re
from typing import NamedTuple

# ── Metric value tables ───────────────────────────────────────────────────────

_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED   = {"N": 0.85, "L": 0.50, "H": 0.50}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"N": 0.00, "L": 0.22, "H": 0.56}

_REQUIRED_KEYS_31 = {"AV", "AC", "PR", "UI", "S", "C", "I", "A"}


class CvssResult(NamedTuple):
    score: float | None       # 0.0–10.0 or None when not computable
    version: str | None       # "3.1" | "4.0" | "2.0" | None
    severity: str | None      # None | Low | Medium | High | Critical (v3.x ratings)
    error: str | None         # non-None when vector is invalid


def _roundup(value: float) -> float:
    """
    Roundup as defined by the official FIRST CVSS v3.1 spec.
    Equivalent to ceiling(x * 10) / 10 with correct IEEE-754 handling.
    """
    int_input = round(value * 100_000)
    if int_input % 10_000 == 0:
        return int_input / 100_000
    return (math.floor(int_input / 10_000) + 1) / 10


def _v31_severity(score: float) -> str:
    if score == 0.0:
        return "None"
    if score < 4.0:
        return "Low"
    if score < 7.0:
        return "Medium"
    if score < 9.0:
        return "High"
    return "Critical"


def _detect_version(vector: str) -> str | None:
    """Return '3.1', '4.0', '2.0', or None for unrecognised prefix."""
    if vector.startswith("CVSS:3.1/"):
        return "3.1"
    if vector.startswith("CVSS:4.0/"):
        return "4.0"
    if vector.startswith("CVSS:3.0/"):
        return "3.0"   # treat as 3.1-compatible
    if vector.startswith("CVSS:2.0/") or vector.startswith("("):
        return "2.0"
    return None


def _parse_v31_metrics(vector: str) -> dict[str, str] | None:
    """Parse the metric key=value pairs after the version prefix."""
    prefix_end = vector.index("/") + 1
    pairs = vector[prefix_end:].split("/")
    metrics: dict[str, str] = {}
    for pair in pairs:
        if ":" not in pair:
            return None
        k, v = pair.split(":", 1)
        metrics[k.upper()] = v.upper()
    return metrics


def score_cvss_vector(vector: str | None) -> CvssResult:
    """
    Parse and score a CVSS vector string.

    Returns (score, version, severity, error).
    score is None when the vector cannot be scored (invalid, v4.0, v2.0).
    """
    if not vector or not isinstance(vector, str):
        return CvssResult(None, None, None, None)

    vector = vector.strip()
    version = _detect_version(vector)

    if version is None:
        return CvssResult(None, None, None, f"Unrecognised CVSS version prefix: {vector[:20]!r}")

    if version == "2.0":
        return CvssResult(None, "2.0", None, "CVSS v2.0 scoring not supported")

    if version == "4.0":
        return CvssResult(None, "4.0", None, None)

    # v3.0 and v3.1 use the same base formula; treat both as 3.1
    metrics = _parse_v31_metrics(vector)
    if metrics is None:
        return CvssResult(None, version, None, "Malformed CVSS vector")

    missing = _REQUIRED_KEYS_31 - metrics.keys()
    if missing:
        return CvssResult(None, version, None, f"Missing CVSS metrics: {sorted(missing)}")

    try:
        av_val = _AV[metrics["AV"]]
        ac_val = _AC[metrics["AC"]]
        scope = metrics["S"]
        pr_val = (_PR_CHANGED if scope == "C" else _PR_UNCHANGED).get(metrics["PR"])
        ui_val = _UI[metrics["UI"]]
        c_val = _CIA[metrics["C"]]
        i_val = _CIA[metrics["I"]]
        a_val = _CIA[metrics["A"]]
    except KeyError as exc:
        return CvssResult(None, version, None, f"Invalid CVSS metric value: {exc}")

    if pr_val is None:
        return CvssResult(None, version, None, f"Invalid PR value: {metrics['PR']!r}")

    # Impact sub-score
    isc_base = 1.0 - (1.0 - c_val) * (1.0 - i_val) * (1.0 - a_val)
    if scope == "U":
        isc = 6.42 * isc_base
    else:
        isc = 7.52 * (isc_base - 0.029) - 3.25 * ((isc_base - 0.02) ** 15)

    if isc <= 0:
        return CvssResult(0.0, "3.1", "None", None)

    exploit = 8.22 * av_val * ac_val * pr_val * ui_val

    if scope == "U":
        raw = min(isc + exploit, 10.0)
    else:
        raw = min(1.08 * (isc + exploit), 10.0)

    score = _roundup(raw)
    return CvssResult(score, version, _v31_severity(score), None)


def extract_cvss_from_metadata(metadata: dict) -> tuple[str | None, str | None]:
    """
    Pull a CVSS vector from Semgrep finding metadata.

    Returns (vector_string, version_string) or (None, None).
    Accepts 'cvss' as a string, list of strings, or nested dict.
    """
    raw = metadata.get("cvss")
    if not raw:
        return None, None

    vector: str | None = None
    if isinstance(raw, str):
        vector = raw.strip()
    elif isinstance(raw, list) and raw:
        # Take first string element
        for item in raw:
            if isinstance(item, str) and item.strip():
                vector = item.strip()
                break
    elif isinstance(raw, dict):
        # Some rule sets nest it as {"vector": "CVSS:3.1/..."} or {"cvss3": "..."}
        for key in ("vector", "cvss3", "cvss31", "score"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                vector = val.strip()
                break

    if not vector:
        return None, None

    version = _detect_version(vector)
    return vector, version
