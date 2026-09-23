"""Path isolation and security validation for compiler artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path

from contract_agent.core.exceptions import IsolationSecurityError


def validate_output_path(
    path: Path | str,
    workspace_root: Path | None = None,
    allowed_dirs: tuple[str, ...] = ("dist",),
) -> Path:
    """Validates that path is confined strictly to allowed directories and forbids services/ access.

    Args:
        path: Destination file or directory path.
        workspace_root: Base workspace root (optional; inferred if path contains allowed_dirs).
        allowed_dirs: Tuple of allowed relative root directory names (e.g. ("dist",)).

    Returns:
        Path: Resolved absolute path.

    Raises:
        IsolationSecurityError: If path traverses outside allowed directories or targets services/.
    """
    target = Path(path).resolve()

    # Explicitly prohibit any write to services/
    if "services" in target.parts:
        raise IsolationSecurityError(
            f"Isolation violation: Writes to human service directory 'services/' are strictly prohibited (attempted: '{path}')."
        )

    if workspace_root is not None:
        root = workspace_root.resolve()
    else:
        # If target path contains an allowed dir, infer root from the parent of the allowed dir
        found_root: Path | None = None
        for allowed in allowed_dirs:
            if allowed in target.parts:
                idx = target.parts.index(allowed)
                found_root = Path(*target.parts[:idx])
                break
        root = found_root.resolve() if found_root is not None else Path.cwd().resolve()

    # Check that target is inside inferred or provided root
    try:
        rel = target.relative_to(root)
    except ValueError as exc:
        raise IsolationSecurityError(
            f"Path traversal detected: '{path}' escapes workspace root '{root}'."
        ) from exc

    # Ensure path belongs to one of the allowed directories (e.g. 'dist')
    parts = rel.parts
    if not parts or parts[0] not in allowed_dirs:
        raise IsolationSecurityError(
            f"Isolation violation: Target path '{path}' must be inside allowed directories {allowed_dirs}, got '{rel}'."
        )

    return target


def ensure_clean_staging_dir(
    staging_dir: Path | str, workspace_root: Path | None = None
) -> Path:
    """Cleans and re-creates an empty staging directory."""
    path = Path(staging_dir)
    validated = validate_output_path(path, workspace_root=workspace_root)
    if validated.exists():
        shutil.rmtree(validated)
    validated.mkdir(parents=True, exist_ok=True)
    return validated


def clean_staging_dir(
    staging_dir: Path | str, workspace_root: Path | None = None
) -> None:
    """Removes staging directory if it exists."""
    path = Path(staging_dir)
    validated = validate_output_path(path, workspace_root=workspace_root)
    if validated.exists():
        shutil.rmtree(validated)
