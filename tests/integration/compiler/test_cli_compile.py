"""Integration tests for contract-agent compile CLI command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from contract_agent.cli.main import app

runner = CliRunner()


def test_cli_compile_headless_ci_success(tmp_path: Path) -> None:
    """Assert headless CI runs end-to-end and auto-promotes artifacts."""
    contract = "tests/fixtures/benchmarks/01_billing_dispute.contract.yaml"
    out_dir = tmp_path / "dist"
    staging_dir = tmp_path / "dist" / ".staging"

    res = runner.invoke(
        app,
        [
            contract,
            "--output-dir",
            str(out_dir),
            "--staging-dir",
            str(staging_dir),
            "--headless-ci",
        ],
    )
    assert res.exit_code == 0
    assert (out_dir / "agent.py").exists()
    assert (out_dir / "interface.py").exists()
    assert (out_dir / "mocks.py").exists()
    assert (out_dir / "test_contract.py").exists()


def test_cli_compile_interactive_approval(tmp_path: Path) -> None:
    """Assert interactive confirmation with 'y' promotes artifacts."""
    contract = "tests/fixtures/benchmarks/02_sql_read_only_agent.contract.yaml"
    out_dir = tmp_path / "dist"
    staging_dir = tmp_path / "dist" / ".staging"

    res = runner.invoke(
        app,
        [
            contract,
            "--output-dir",
            str(out_dir),
            "--staging-dir",
            str(staging_dir),
        ],
        input="y\n",
    )
    assert res.exit_code == 0
    assert (out_dir / "agent.py").exists()


def test_cli_compile_interactive_rejection(tmp_path: Path) -> None:
    """Assert interactive confirmation with 'n' rejects promotion (exit code 4)."""
    contract = "tests/fixtures/benchmarks/03_api_sync_agent.contract.yaml"
    out_dir = tmp_path / "dist"
    staging_dir = tmp_path / "dist" / ".staging"

    res = runner.invoke(
        app,
        [
            contract,
            "--output-dir",
            str(out_dir),
            "--staging-dir",
            str(staging_dir),
        ],
        input="n\n",
    )
    assert res.exit_code == 4
    assert not (out_dir / "agent.py").exists()


def test_cli_compile_forbids_services_target(tmp_path: Path) -> None:
    """Assert targeting services/ fails with security error (exit code 5)."""
    contract = "tests/fixtures/benchmarks/01_billing_dispute.contract.yaml"
    bad_out = tmp_path / "services"

    res = runner.invoke(
        app,
        [
            contract,
            "--output-dir",
            str(bad_out),
            "--headless-ci",
        ],
    )
    assert res.exit_code == 5
    assert "Security Error" in res.stdout or "Isolation violation" in res.stdout
