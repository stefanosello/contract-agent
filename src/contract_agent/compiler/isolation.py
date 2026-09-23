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
        workspace_root: Base workspace root (defaults to current working directory).
        allowed_dirs: Tuple of allowed relative root directory names (e.g. ("dist",)).

    Returns:
        Path: Resolved absolute path.

    Raises:
        IsolationSecurityError: If path traverses outside allowed directories or targets services/.
    """
    root = (workspace_root or Path.cwd()).resolve()
    target = Path(path)
    if not target.is_absolute():
        target = (root / target).resolve()
    else:
        target = target.resolve()

    # Check that target is inside workspace root
    try:
        rel = target.relative_to(root)
    except ValueError as exc:
        raise IsolationSecurityError(
            f"Path traversal detected: '{path}' escapes workspace root '{root}'."
        ) from exc

    # Explicitly prohibit any write to services/
    parts = rel.parts
    if parts and parts[0] == "services":
        raise IsolationSecurityError(
            f"Isolation violation: Writes to human service directory 'services/' are strictly prohibited (attempted: '{path}')."
        )

    # Ensure path belongs to one of the allowed directories (e.g. 'dist')
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
