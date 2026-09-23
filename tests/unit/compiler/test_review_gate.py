"""Unit tests for ReviewGate unified diff generation and promotion."""

from __future__ import annotations

from pathlib import Path

from contract_agent.cli.review import ReviewGate


def test_review_gate_diff_new_files(tmp_path: Path) -> None:
    """Assert unified diff displays /dev/null to b/dist when files are newly staged."""
    staging = tmp_path / "dist" / ".staging"
    out_dir = tmp_path / "dist"
    staging.mkdir(parents=True)
    (staging / "agent.py").write_text("class TestAgent:\n    pass\n")

    gate = ReviewGate(output_dir=out_dir, staging_dir=staging)
    diff = gate.generate_diff()

    assert "--- /dev/null" in diff
    assert "+++ b/dist/agent.py" in diff
    assert "+class TestAgent:" in diff


def test_review_gate_diff_modified_files(tmp_path: Path) -> None:
    """Assert unified diff displays delta when existing files are updated."""
    staging = tmp_path / "dist" / ".staging"
    out_dir = tmp_path / "dist"
    staging.mkdir(parents=True, exist_ok=True)

    (out_dir / "agent.py").write_text("class TestAgent:\n    version = 1\n")
    (staging / "agent.py").write_text("class TestAgent:\n    version = 2\n")

    gate = ReviewGate(output_dir=out_dir, staging_dir=staging)
    diff = gate.generate_diff()

    assert "-    version = 1" in diff
    assert "+    version = 2" in diff


def test_review_gate_headless_ci_promotion(tmp_path: Path) -> None:
    """Assert headless CI mode auto-promotes without interactive prompts."""
    staging = tmp_path / "dist" / ".staging"
    out_dir = tmp_path / "dist"
    staging.mkdir(parents=True)
    (staging / "agent.py").write_text("class PromotedAgent:\n    pass\n")

    gate = ReviewGate(output_dir=out_dir, staging_dir=staging)
    promoted = gate.prompt_and_promote(headless_ci=True, workspace_root=tmp_path)

    assert promoted is True
    assert (out_dir / "agent.py").exists()
    assert "PromotedAgent" in (out_dir / "agent.py").read_text()


def test_review_gate_interactive_approval_and_rejection(tmp_path: Path) -> None:
    """Assert confirm_callback controls promotion decision in interactive mode."""
    staging = tmp_path / "dist" / ".staging"
    out_dir = tmp_path / "dist"
    staging.mkdir(parents=True)
    (staging / "agent.py").write_text("class InteractiveAgent:\n    pass\n")

    gate = ReviewGate(output_dir=out_dir, staging_dir=staging)

    # User says NO
    rejected = gate.prompt_and_promote(
        headless_ci=False, confirm_callback=lambda: False, workspace_root=tmp_path
    )
    assert rejected is False
    assert not (out_dir / "agent.py").exists()

    # User says YES
    approved = gate.prompt_and_promote(
        headless_ci=False, confirm_callback=lambda: True, workspace_root=tmp_path
    )
    assert approved is True
    assert (out_dir / "agent.py").exists()
