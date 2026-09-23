"""Unit tests for compiler path isolation and security validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract_agent.compiler.isolation import (
    clean_staging_dir,
    ensure_clean_staging_dir,
    validate_output_path,
)
from contract_agent.core.exceptions import IsolationSecurityError


def test_validate_output_path_allowed(tmp_path: Path) -> None:
    """Assert valid paths under dist/ succeed."""
    valid_file = tmp_path / "dist" / "agent.py"
    res = validate_output_path(valid_file, workspace_root=tmp_path)
    assert res == valid_file.resolve()

    valid_staging = tmp_path / "dist" / ".staging" / "test_contract.py"
    res_staging = validate_output_path(valid_staging, workspace_root=tmp_path)
    assert res_staging == valid_staging.resolve()


def test_validate_output_path_forbids_services(tmp_path: Path) -> None:
    """Assert any attempt to write to services/ raises IsolationSecurityError."""
    service_file = tmp_path / "services" / "billing.py"
    with pytest.raises(IsolationSecurityError, match="Isolation violation.*services/"):
        validate_output_path(service_file, workspace_root=tmp_path)


def test_validate_output_path_forbids_traversal(tmp_path: Path) -> None:
    """Assert path traversal outside workspace root raises IsolationSecurityError."""
    outside_file = tmp_path.parent / "escape.py"
    with pytest.raises(IsolationSecurityError, match="Path traversal detected"):
        validate_output_path(outside_file, workspace_root=tmp_path)


def test_validate_output_path_forbids_disallowed_dirs(tmp_path: Path) -> None:
    """Assert writing to src/ or root files raises IsolationSecurityError."""
    src_file = tmp_path / "src" / "rogue.py"
    with pytest.raises(IsolationSecurityError, match="Isolation violation"):
        validate_output_path(src_file, workspace_root=tmp_path)


def test_staging_dir_lifecycle(tmp_path: Path) -> None:
    """Assert ensure_clean_staging_dir and clean_staging_dir function correctly."""
    staging = tmp_path / "dist" / ".staging"
    created = ensure_clean_staging_dir(staging, workspace_root=tmp_path)
    assert created.exists()
    assert created.is_dir()

    # Create dummy artifact
    (created / "dummy.txt").write_text("hello")
    assert (created / "dummy.txt").exists()

    # Re-running ensure_clean removes previous contents
    recreated = ensure_clean_staging_dir(staging, workspace_root=tmp_path)
    assert recreated.exists()
    assert not (recreated / "dummy.txt").exists()

    clean_staging_dir(staging, workspace_root=tmp_path)
    assert not staging.exists()
