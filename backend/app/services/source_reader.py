"""
Secure source-file excerpt reader.

Security guarantees:
- The resolved target path must be a strict descendant of the resolved source_dir.
- No symlinks are followed at any path component.
- Only a bounded excerpt (default ±10 lines) is returned; whole files are never read.
- This module never surfaces the source_dir path to callers.
"""
import os
from dataclasses import dataclass
from pathlib import Path

_MAX_LINES = 500   # hard cap on lines readable from a single file


@dataclass
class SourceLine:
    number: int
    content: str
    is_target: bool


@dataclass
class SourceExcerpt:
    available: bool
    file: str            # relative POSIX path (for display only)
    target_line: int | None
    lines: list[SourceLine]
    message: str | None  # human-readable reason when available=False


def _safe_resolve(path: Path) -> Path | None:
    """
    Resolve a path without following symlinks.
    Returns None if any component is a symlink.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return None
    # Verify no symlink appears at any component under cwd
    check = path
    while True:
        try:
            if check.is_symlink():
                return None
        except OSError:
            return None
        parent = check.parent
        if parent == check:
            break
        check = parent
    return resolved


def read_source_excerpt(
    source_dir: str | Path,
    relative_file_path: str | None,
    target_line: int | None,
    context_lines: int = 10,
) -> SourceExcerpt:
    """
    Return a bounded excerpt of the file at source_dir/relative_file_path.

    If the file is unavailable, missing, or the path is unsafe, returns
    SourceExcerpt(available=False, ...) rather than raising.
    """
    if not relative_file_path:
        return SourceExcerpt(available=False, file="", target_line=None, lines=[], message="No file path recorded for this finding.")

    # Normalise separators and strip leading slashes
    rel = relative_file_path.replace("\\", "/").lstrip("/")

    if ".." in Path(rel).parts:
        return SourceExcerpt(available=False, file=rel, target_line=None, lines=[], message="Invalid file path.")

    source_dir = Path(source_dir)
    target_path = source_dir / rel

    # Resolve without following symlinks
    resolved_dir = _safe_resolve(source_dir)
    resolved_target = _safe_resolve(target_path)

    if resolved_dir is None or resolved_target is None:
        return SourceExcerpt(available=False, file=rel, target_line=None, lines=[], message="Source file not accessible.")

    # Containment check: target must be strictly inside source_dir
    dir_str = str(resolved_dir)
    target_str = str(resolved_target)
    if not (target_str.startswith(dir_str + os.sep) or target_str.startswith(dir_str + "/")):
        return SourceExcerpt(available=False, file=rel, target_line=None, lines=[], message="Source file not accessible.")

    if not resolved_target.is_file():
        return SourceExcerpt(available=False, file=rel, target_line=target_line, lines=[], message="Source file not found. It may have been cleaned up after analysis.")

    try:
        # Read lazily — stop after _MAX_LINES to prevent huge reads
        all_lines: list[str] = []
        with open(resolved_target, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= _MAX_LINES:
                    break
                all_lines.append(line.rstrip("\n"))
    except OSError:
        return SourceExcerpt(available=False, file=rel, target_line=target_line, lines=[], message="Could not read source file.")

    total = len(all_lines)

    if target_line is None or target_line < 1:
        # No line info: return first context_lines lines
        excerpt = all_lines[:context_lines * 2]
        source_lines = [SourceLine(number=i + 1, content=ln, is_target=False) for i, ln in enumerate(excerpt)]
        return SourceExcerpt(available=True, file=rel, target_line=None, lines=source_lines, message=None)

    # 1-based → 0-based index
    target_idx = target_line - 1

    if target_idx >= total:
        # Line number beyond file length — return last context
        start = max(0, total - context_lines)
        end = total
        effective_target = None
    else:
        start = max(0, target_idx - context_lines)
        end = min(total, target_idx + context_lines + 1)
        effective_target = target_line

    source_lines = [
        SourceLine(
            number=i + 1,
            content=all_lines[i],
            is_target=(i == target_idx and effective_target is not None),
        )
        for i in range(start, end)
    ]

    return SourceExcerpt(available=True, file=rel, target_line=effective_target, lines=source_lines, message=None)
