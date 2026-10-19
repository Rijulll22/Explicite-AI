"""
Safe ZIP archive validation and extraction.

Security controls implemented:
- Magic-bytes check (ZIP PK header)
- Size limit: configurable max compressed size (FR-PROJ-02)
- Expansion limit: 50 MB total uncompressed
- Entry count limit: 1000 entries
- Per-entry compression ratio limit: 100:1 (zip bomb detection)
- Path traversal: rejects entries containing '..'
- Absolute paths and Windows drive paths rejected
- Symlinks rejected
- Nested archives (.zip .tar .gz .jar etc.) skipped, not extracted
- Extraction path verified to stay within dest_dir
- Partial extraction cleaned up on failure
"""
import io
import os
import re
import shutil
import zipfile
from pathlib import Path

_NESTED_ARCHIVE_EXTS = frozenset({
    ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".7z", ".rar", ".jar", ".war", ".ear",
})
_MAX_ENTRY_COUNT = 1000
_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB aggregate
_MAX_ENTRY_RATIO = 100                        # per-entry bomb threshold


class ArchiveError(Exception):
    """Raised for invalid, unsafe, or policy-violating archives."""


def validate_and_extract(data: bytes, dest_dir: Path) -> list[str]:
    """
    Validate and securely extract a ZIP archive to dest_dir.

    Returns a list of relative POSIX paths that were extracted.
    Raises ArchiveError for any security or validity violation.
    dest_dir is created if it does not exist; cleaned up on failure.
    """
    # ZIP magic: local-file entries start with PK\x03\x04, but an empty
    # ZIP has only the end-of-central-directory record (PK\x05\x06).
    # Accept any PK-prefixed file and let ZipFile validate the structure.
    if len(data) < 4 or data[:2] != b"PK":
        raise ArchiveError("Not a valid ZIP archive (missing PK header)")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ArchiveError(f"Malformed ZIP archive: {exc}") from exc

    entries = zf.infolist()

    if not entries:
        raise ArchiveError("Archive is empty — no files to analyse")

    if len(entries) > _MAX_ENTRY_COUNT:
        raise ArchiveError(
            f"Archive contains {len(entries)} entries; limit is {_MAX_ENTRY_COUNT}"
        )

    # Pre-scan: validate all entries before writing any bytes
    total_uncompressed = 0
    for entry in entries:
        name = entry.filename
        if name.endswith("/") or name.endswith("\\"):
            continue  # directory entry — skip

        parts = Path(name).parts
        if ".." in parts:
            raise ArchiveError(f"Path traversal in entry: {name!r}")

        if os.path.isabs(name):
            raise ArchiveError(f"Absolute path in archive entry: {name!r}")

        if re.match(r"^[A-Za-z]:[/\\]", name):
            raise ArchiveError(f"Windows drive path in archive entry: {name!r}")

        # Symlink bit in external file attributes (Unix mode 0xA1ED)
        if (entry.external_attr >> 16) & 0xFFFF == 0xA1ED:
            raise ArchiveError(f"Symlink rejected: {name!r}")

        ext = Path(name).suffix.lower()
        if ext in _NESTED_ARCHIVE_EXTS:
            continue  # nested archive — will be skipped during extraction

        if entry.compress_size > 0 and entry.file_size > 1024:
            ratio = entry.file_size / entry.compress_size
            if ratio > _MAX_ENTRY_RATIO:
                raise ArchiveError(
                    f"Entry {name!r} has compression ratio {ratio:.0f}:1 "
                    f"(limit {_MAX_ENTRY_RATIO}:1) — possible decompression bomb"
                )

        total_uncompressed += entry.file_size
        if total_uncompressed > _MAX_UNCOMPRESSED_BYTES:
            limit_mb = _MAX_UNCOMPRESSED_BYTES // (1024 * 1024)
            raise ArchiveError(
                f"Total uncompressed size exceeds {limit_mb} MB limit"
            )

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_str = str(dest_dir.resolve())
    extracted: list[str] = []

    try:
        for entry in entries:
            name = entry.filename
            if name.endswith("/") or name.endswith("\\"):
                continue

            ext = Path(name).suffix.lower()
            if ext in _NESTED_ARCHIVE_EXTS:
                continue  # skip nested archives

            safe_name = name.replace("\\", "/").lstrip("/")
            target_path = (dest_dir / safe_name).resolve()

            # Guard: resolved path must stay inside dest_dir
            if not str(target_path).startswith(dest_str + os.sep) and str(target_path) != dest_str:
                raise ArchiveError(f"Path escape detected: {name!r}")

            target_path.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(entry) as src, open(target_path, "wb") as dst:
                written = 0
                for chunk in iter(lambda: src.read(65536), b""):
                    written += len(chunk)
                    if written > entry.file_size + 4096:
                        raise ArchiveError(
                            f"Entry {name!r} expanded beyond declared size"
                        )
                    dst.write(chunk)

            extracted.append(safe_name)

    except ArchiveError:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise ArchiveError(f"Extraction failed: {exc}") from exc

    return extracted
