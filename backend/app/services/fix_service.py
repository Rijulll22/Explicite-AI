"""
Fix-generation service (SRS FR-FIX-01 – FR-FIX-07).

Responsibilities:
- Extract bounded, path-validated source context from a job's source directory.
- Compute unified diffs from original vs proposed snippets.
- Create patched ZIP archives in memory (never modifies the original source_path).
"""
import difflib
import hashlib
import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum file size read into memory for context extraction (512 KB)
_MAX_FILE_BYTES = 512 * 1024

# Lines before/after the finding line included in the snippet
_CONTEXT_LINES = 20

# Maximum snippet size we pass to the model (characters)
_MAX_SNIPPET_CHARS = 8_000


class SourceUnavailableError(Exception):
    """Raised when source context cannot be accessed safely."""


class StaleFixError(Exception):
    """Raised when the source file has changed since the fix was generated."""


@dataclass
class SourceContext:
    file_path: str        # relative path as given by the finding
    content: str          # full file content (UTF-8 decoded)
    content_hash: str     # SHA-256 of raw file bytes
    snippet: str          # bounded lines around line_number
    snippet_start_line: int   # 1-based first line of snippet (inclusive)
    snippet_end_line: int     # 1-based last line of snippet (inclusive)


def extract_source_context(
    source_dir: str | None,
    file_path: str | None,
    line_number: int | None,
) -> SourceContext:
    """
    Extract a bounded source context from the job's source directory.

    Raises SourceUnavailableError when the file cannot be read safely
    (source not present, path traversal attempt, binary file, oversized file).
    Never executes file content or treats it as instructions.
    """
    if not source_dir:
        raise SourceUnavailableError("Job has no source_path; cannot read source.")
    if not file_path:
        raise SourceUnavailableError("Finding has no file_path; cannot read source.")

    source_root = Path(source_dir).resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise SourceUnavailableError(
            f"Source directory no longer exists: {source_dir}"
        )

    # Resolve and validate — prevent path traversal
    try:
        full_path = (source_root / file_path).resolve()
        full_path.relative_to(source_root)   # raises ValueError if outside
    except (ValueError, OSError):
        logger.warning(
            "Path traversal attempt or invalid path: %r within %r",
            file_path, source_dir,
        )
        raise SourceUnavailableError("File path resolves outside the source directory.")

    if not full_path.exists() or not full_path.is_file():
        raise SourceUnavailableError(f"Source file not found: {file_path}")

    raw_bytes = full_path.read_bytes()
    if len(raw_bytes) > _MAX_FILE_BYTES:
        raise SourceUnavailableError(
            f"Source file exceeds {_MAX_FILE_BYTES // 1024} KB limit."
        )

    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = raw_bytes.decode("latin-1")
        except Exception:
            raise SourceUnavailableError("Source file is binary or has an unsupported encoding.")

    lines = content.splitlines()

    if line_number is not None and 1 <= line_number <= len(lines):
        start_idx = max(0, line_number - _CONTEXT_LINES - 1)
        end_idx = min(len(lines), line_number + _CONTEXT_LINES)
    else:
        start_idx = 0
        end_idx = min(len(lines), _CONTEXT_LINES * 2 + 1)

    snippet_start = start_idx + 1    # 1-based
    snippet_end = end_idx             # 1-based (last line is lines[end_idx-1])
    snippet = "\n".join(lines[start_idx:end_idx])[:_MAX_SNIPPET_CHARS]

    return SourceContext(
        file_path=file_path,
        content=content,
        content_hash=content_hash,
        snippet=snippet,
        snippet_start_line=snippet_start,
        snippet_end_line=snippet_end,
    )


def compute_unified_diff(
    original_snippet: str,
    proposed_snippet: str,
    file_path: str,
) -> str:
    """
    Compute a unified diff between the original and proposed snippets.
    Returns an empty string if there are no differences.
    """
    original_lines = original_snippet.splitlines(keepends=True)
    proposed_lines = proposed_snippet.splitlines(keepends=True)

    # Ensure each list ends with a newline for clean diff output
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if proposed_lines and not proposed_lines[-1].endswith("\n"):
        proposed_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        proposed_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
        n=3,
    )
    return "\n".join(diff)


def create_patched_zip(
    source_dir: str,
    target_file: str,
    original_hash: str,
    original_snippet: str,
    proposed_snippet: str,
) -> bytes:
    """
    Build a ZIP archive in memory with the proposed fix applied.

    The original source_dir is NEVER modified.
    Raises StaleFixError if the target file has changed since the fix was generated.
    Raises SourceUnavailableError if the source directory or file is missing.
    """
    source_root = Path(source_dir).resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise SourceUnavailableError("Source directory is no longer available.")

    # Validate path
    try:
        full_path = (source_root / target_file).resolve()
        full_path.relative_to(source_root)
    except (ValueError, OSError):
        raise SourceUnavailableError("Target file path resolves outside the source directory.")

    if not full_path.exists() or not full_path.is_file():
        raise SourceUnavailableError("Target file no longer exists in source directory.")

    current_bytes = full_path.read_bytes()
    current_hash = hashlib.sha256(current_bytes).hexdigest()
    if current_hash != original_hash:
        raise StaleFixError(
            "The source file has changed since this fix was generated. "
            "Generate a new fix to obtain an up-to-date proposal."
        )

    try:
        current_content = current_bytes.decode("utf-8")
    except UnicodeDecodeError:
        current_content = current_bytes.decode("latin-1")

    # Normalize line endings to \n for consistent matching and diff application
    current_norm = current_content.replace("\r\n", "\n").replace("\r", "\n")
    snippet_norm = original_snippet.replace("\r\n", "\n").replace("\r", "\n")

    # Apply fix: replace original_snippet text with proposed_snippet
    if snippet_norm and snippet_norm in current_norm:
        patched_content = current_norm.replace(snippet_norm, proposed_snippet, 1)
    else:
        # Snippet no longer matches exactly — fix is stale
        raise StaleFixError(
            "The original code section could not be located precisely in the current file. "
            "The fix may be stale. Generate a new fix."
        )

    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(source_root.rglob("*")):
            if not fp.is_file():
                continue
            rel = fp.relative_to(source_root).as_posix()
            if rel == target_file.replace("\\", "/"):
                zf.writestr(rel, patched_content)
            else:
                # Only include reasonably sized files
                try:
                    file_bytes = fp.read_bytes()
                    if len(file_bytes) <= _MAX_FILE_BYTES:
                        zf.writestr(rel, file_bytes)
                except OSError:
                    pass

    return buf.getvalue()
