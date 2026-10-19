"""
Semgrep static analysis adapter.

Engine: semgrep 1.181.0
Supported languages: Python, Java, JavaScript, TypeScript (r/ registry configs)
SRS note: analysis adapters are replaceable; this is the default engine.
Risk scoring: engine_severity used as risk_level proxy (FR-RISK formula pending).

Security: semgrep is invoked with a fixed argument list.
User-controlled data (file paths) are passed as an argument, never via shell=True.
"""
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.services.cvss_scoring import extract_cvss_from_metadata

logger = logging.getLogger(__name__)

# Semgrep severity string → our Finding.engine_severity (Critical|High|Medium|Low)
_SEVERITY_MAP: dict[str, str] = {
    "ERROR": "High",
    "WARNING": "Medium",
    "INFO": "Low",
}

# Rule metadata keywords → issue_type classification
_HOTSPOT_KW = frozenset({"hotspot", "audit"})
_SECURITY_KW = frozenset({"security", "injection", "sqli", "xss", "command", "traversal", "crypto", "deserialization"})
_BUG_KW = frozenset({"correctness", "null", "bug", "exception", "leak", "memory", "error"})

# File extension → semgrep registry config
_LANG_CONFIGS: dict[str, str] = {
    ".py": "r/python",
    ".java": "r/java",
    ".js": "r/javascript",
    ".jsx": "r/javascript",
    ".ts": "r/typescript",
    ".tsx": "r/typescript",
}
SUPPORTED_EXTENSIONS = frozenset(_LANG_CONFIGS)


def _classify_issue_type(metadata: dict, check_id: str) -> str:
    category = metadata.get("category", "").lower()
    subcategory = " ".join(metadata.get("subcategory", [])).lower()
    combined = f"{category} {check_id.lower()} {subcategory}"
    if any(k in combined for k in _HOTSPOT_KW):
        return "Security Hotspot"
    if any(k in combined for k in _SECURITY_KW):
        return "Vulnerability"
    if any(k in combined for k in _BUG_KW):
        return "Bug"
    return "Code Smell"


def _extract_cwe(metadata: dict) -> str | None:
    cwes = metadata.get("cwe", [])
    if cwes and isinstance(cwes, list) and isinstance(cwes[0], str):
        return cwes[0].split(":")[0].strip()
    return None


def _extract_owasp(metadata: dict) -> str | None:
    owasps = metadata.get("owasp", [])
    if owasps and isinstance(owasps, list) and isinstance(owasps[0], str):
        return owasps[0].split(" - ")[0].strip()
    return None


@dataclass
class RawFinding:
    rule_key: str
    title: str
    description: str | None
    engine_severity: str
    issue_type: str
    file_path: str
    line_number: int | None
    cwe_id: str | None
    owasp_category: str | None
    cvss_vector: str | None = None
    cvss_version: str | None = None


@dataclass
class AnalysisResult:
    engine_name: str
    engine_version: str
    findings: list[RawFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scanned_file_count: int = 0


class AnalysisEngineError(Exception):
    pass


def _find_semgrep() -> str:
    """Locate semgrep next to our Python interpreter, then fall back to PATH."""
    venv_bin = Path(sys.executable).parent
    for candidate in ("semgrep", "semgrep.exe"):
        p = venv_bin / candidate
        if p.is_file():
            return str(p)
    found = shutil.which("semgrep")
    if found:
        return found
    raise AnalysisEngineError(
        "Semgrep not found. Install it with: pip install semgrep"
    )


def get_semgrep_version() -> str:
    exe = _find_semgrep()
    result = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15)
    return result.stdout.strip() or "unknown"


def _detect_configs(source_dir: Path) -> list[str]:
    """Return semgrep --config values for the languages present in source_dir."""
    needed: set[str] = set()
    for p in source_dir.rglob("*"):
        if p.is_file():
            ext = p.suffix.lower()
            if ext in _LANG_CONFIGS:
                needed.add(_LANG_CONFIGS[ext])
    return sorted(needed)


def run_semgrep(source_dir: Path, timeout: int = 300) -> AnalysisResult:
    """
    Invoke semgrep against source_dir and return normalised findings.
    Raises AnalysisEngineError on hard failures.
    Partial failures (some files unparseable) are recorded in result.errors.
    """
    exe = _find_semgrep()
    version = get_semgrep_version()

    configs = _detect_configs(source_dir)
    if not configs:
        return AnalysisResult(
            engine_name="semgrep",
            engine_version=version,
            findings=[],
            errors=["No supported source files found (supported: .py .java .js .jsx .ts .tsx)"],
            scanned_file_count=0,
        )

    # Fixed argument list — NEVER interpolate user-controlled data via shell
    cmd = [exe]
    for cfg in configs:
        cmd += ["--config", cfg]
    cmd += ["--json", "--quiet", "--no-git-ignore", str(source_dir)]

    logger.info("Running semgrep: %s", " ".join(cmd[:6]) + " ...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,   # explicit: never shell=True
        )
    except subprocess.TimeoutExpired:
        raise AnalysisEngineError(f"Semgrep timed out after {timeout}s")
    except FileNotFoundError:
        raise AnalysisEngineError("Semgrep executable not found at runtime")

    # semgrep exits 0 (clean) or 1 (findings) or 2 (error)
    if result.returncode == 2 and not result.stdout.strip():
        raise AnalysisEngineError(
            f"Semgrep returned error: {result.stderr.strip()[:300]}"
        )

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AnalysisEngineError(f"Semgrep output is not valid JSON: {exc}") from exc

    source_dir_str = str(source_dir.resolve())
    findings: list[RawFinding] = []

    for item in output.get("results", []):
        check_id = item.get("check_id", "unknown")
        path_raw = item.get("path", "")

        try:
            rel = os.path.relpath(path_raw, source_dir_str)
        except ValueError:
            rel = path_raw
        rel = rel.replace("\\", "/")

        extra = item.get("extra", {})
        message = extra.get("message", "")
        sev_raw = extra.get("severity", "INFO")
        metadata = extra.get("metadata", {})

        engine_sev = _SEVERITY_MAP.get(sev_raw, "Low")
        issue_type = _classify_issue_type(metadata, check_id)

        title = message.split("\n")[0][:200] or check_id
        start = item.get("start", {})

        cvss_vector, cvss_version = extract_cvss_from_metadata(metadata)

        findings.append(RawFinding(
            rule_key=check_id[:255],
            title=title[:500],
            description=message[:2000] or None,
            engine_severity=engine_sev,
            issue_type=issue_type,
            file_path=rel[:1000],
            line_number=start.get("line"),
            cwe_id=_extract_cwe(metadata),
            owasp_category=_extract_owasp(metadata),
            cvss_vector=cvss_vector[:300] if cvss_vector else None,
            cvss_version=cvss_version[:10] if cvss_version else None,
        ))

    scanned = output.get("paths", {}).get("scanned", [])
    errors = [str(e) for e in output.get("errors", [])]

    return AnalysisResult(
        engine_name="semgrep",
        engine_version=version,
        findings=findings,
        errors=errors,
        scanned_file_count=len(scanned),
    )
