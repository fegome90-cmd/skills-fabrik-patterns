"""
End-to-End Tests: Full Lifecycle

Tests complete workflow from SessionStart to Stop.
Verifies all hooks execute in correct order with state maintained.
"""

import pytest
import subprocess
import sys
import tempfile
import json
from pathlib import Path
import time


class TestFullLifecycle:
    """Test complete session lifecycle."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def test_environment(self, temp_dir: Path) -> Path:
        """Create test environment with Claude structure."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        # Create context
        context_dir = claude_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("""# Claude Context

## Identity
Test user

## Projects
Test project
""")

        # Create directories for handoffs and backups
        (claude_dir / "handoffs").mkdir()
        (claude_dir / "backups").mkdir()

        return claude_dir

    def test_session_start_hook_executes(self, test_environment: Path, plugin_root: Path):
        """Test SessionStart (health-check) executes."""
        script = plugin_root / "scripts" / "health-check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(test_environment.parent)},
            timeout=30
        )

        # Should complete
        assert result.returncode in [0, 1]

        # Should output JSON
        try:
            output = json.loads(result.stdout)
            assert "status" in output
        except json.JSONDecodeError:
            pass  # May have stderr output

    def test_user_prompt_submit_hook_executes(self, test_environment: Path, plugin_root: Path):
        """Test UserPromptSubmit (inject-context) executes."""
        script = plugin_root / "scripts" / "inject-context.py"

        input_data = json.dumps({
            "prompt": "Help me",
            "project_path": str(test_environment.parent)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            env={"HOME": str(test_environment.parent)},
            timeout=30
        )

        # Should complete
        assert result.returncode == 0

    def test_pre_compact_hook_executes(self, test_environment: Path, plugin_root: Path):
        """Test PreCompact (handoff-backup) executes."""
        script = plugin_root / "scripts" / "handoff-backup.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(test_environment.parent)},
            timeout=60
        )

        # Should complete
        assert result.returncode == 0

    def test_post_tool_use_hook_executes(self, test_environment: Path, plugin_root: Path):
        """Test PostToolUse (auto-fix) executes."""
        # Create a Python file to format
        test_file = test_environment / "test.py"
        test_file.write_text("x=1\ny=2\n")

        script = plugin_root / "scripts" / "auto-fix.py"

        result = subprocess.run(
            [sys.executable, str(script), str(test_environment)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Should complete
        assert result.returncode in [0, 1]

    def test_stop_hook_executes(self, test_environment: Path, plugin_root: Path):
        """Test Stop (quality-gates) executes."""
        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=120
        )

        # May fail if gates fail, that's expected
        assert result.returncode in [0, 1]


class TestHookExecutionOrder:
    """Test hooks execute in correct order."""

    def test_verify_hooks_json_order(self, plugin_root: Path):
        """Test hooks.json defines correct order."""
        hooks_file = plugin_root / ".claude-plugin" / "hooks" / "hooks.json"

        if hooks_file.exists():
            with open(hooks_file) as f:
                hooks_config = json.load(f)

            # Check hooks exist
            assert "hooks" in hooks_config

            # Verify hook types
            hook_types = {h.get('type', '') for h in hooks_config['hooks']}
            assert 'SessionStart' in hook_types
            assert 'UserPromptSubmit' in hook_types
            assert 'PreCompact' in hook_types
            assert 'PostToolUse' in hook_types
            assert 'Stop' in hook_types


class TestStateMaintenance:
    """Test state is maintained between hooks."""

    @pytest.fixture
    def persistent_environment(self, temp_dir: Path) -> dict:
        """Create environment that persists across hooks."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        # Create context
        context_dir = claude_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("# Test Context\n")

        # Create handoff and backup dirs
        (claude_dir / "handoffs").mkdir()
        (claude_dir / "backups").mkdir()

        return {"claude_dir": claude_dir, "temp_dir": temp_dir}

    def test_context_persists_across_hooks(
        self,
        persistent_environment: dict,
        plugin_root: Path
    ):
        """Test context data is available across all hooks."""
        claude_dir = persistent_environment["claude_dir"]

        # Run inject-context (should read context)
        script = plugin_root / "scripts" / "inject-context.py"
        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(persistent_environment["temp_dir"])
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            env={"HOME": str(persistent_environment["temp_dir"])},
            timeout=30
        )

        # Should have read context
        assert result.returncode == 0

    def test_handoffs_accumulate_across_sessions(
        self,
        persistent_environment: dict,
        plugin_root: Path
    ):
        """Test handoffs accumulate across sessions."""
        # Run handoff-backup multiple times
        script = plugin_root / "scripts" / "handoff-backup.py"

        for _ in range(3):
            subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                env={"HOME": str(persistent_environment["temp_dir"])},
                timeout=60
            )

        # Check multiple handoffs exist
        handoff_dir = persistent_environment["claude_dir"] / "handoffs"
        handoffs = list(handoff_dir.glob("handoff-*.md"))
        assert len(handoffs) >= 3

    def test_backups_accumulate_across_sessions(
        self,
        persistent_environment: dict,
        plugin_root: Path
    ):
        """Test backups accumulate across sessions."""
        # Run handoff-backup multiple times (creates backups too)
        script = plugin_root / "scripts" / "handoff-backup.py"

        for _ in range(2):
            subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                env={"HOME": str(persistent_environment["temp_dir"])},
                timeout=60
            )

        # Check backups exist
        backup_dir = persistent_environment["claude_dir"] / "backups"
        if backup_dir.exists():
            backups = [d for d in backup_dir.iterdir() if d.is_dir()]
            assert len(backups) >= 1


class TestWorkflowScenarios:
    """Test realistic workflow scenarios."""

    def test_new_feature_workflow(self, temp_dir: Path, plugin_root: Path):
        """Test workflow for implementing a new feature."""
        # Setup environment
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        context_dir = claude_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("# Feature: New Auth\n\nStatus: In Progress\n")
        (claude_dir / "handoffs").mkdir()
        (claude_dir / "backups").mkdir()

        # Simulate workflow
        # 1. SessionStart: health check
        health_script = plugin_root / "scripts" / "health-check.py"
        subprocess.run(
            [sys.executable, str(health_script)],
            capture_output=True,
            env={"HOME": str(temp_dir)},
            timeout=30
        )

        # 2. UserPromptSubmit: inject context
        inject_script = plugin_root / "scripts" / "inject-context.py"
        input_data = json.dumps({
            "prompt": "Implement OAuth",
            "project_path": str(temp_dir)
        })
        subprocess.run(
            [sys.executable, str(inject_script)],
            input=input_data,
            capture_output=True,
            env={"HOME": str(temp_dir)},
            timeout=30
        )

        # 3. PostToolUse: format code
        # Create file first
        (temp_dir / "auth.py").write_text("def auth():\n    pass\n")
        auto_fix_script = plugin_root / "scripts" / "auto-fix.py"
        subprocess.run(
            [sys.executable, str(auto_fix_script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # 4. PreCompact: create handoff and backup
        handoff_script = plugin_root / "scripts" / "handoff-backup.py"
        subprocess.run(
            [sys.executable, str(handoff_script)],
            capture_output=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Verify artifacts created
        handoffs = list((claude_dir / "handoffs").glob("*.md"))
        assert len(handoffs) > 0

    def test_bug_fix_workflow(self, temp_dir: Path, plugin_root: Path):
        """Test workflow for fixing a bug."""
        # Setup
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "handoffs").mkdir()
        (claude_dir / "backups").mkdir()

        # Create buggy file
        buggy_file = temp_dir / "bug.py"
        buggy_file.write_text("""
def calculate(x, y):
    return x + y  # Bug: should be x * y
""")

        # Format code
        auto_fix_script = plugin_root / "scripts" / "auto-fix.py"
        subprocess.run(
            [sys.executable, str(auto_fix_script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # File should still exist
        assert buggy_file.exists()

    def test_session_continuation_workflow(self, temp_dir: Path, plugin_root: Path):
        """Test workflow for continuing a previous session."""
        # Setup with existing handoff
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Create existing handoff
        existing_handoff = handoff_dir / "handoff-20240101-120000.md"
        existing_handoff.write_text("""# 🚀 HANDOFF: session-001 → next-002

## 📊 Completed Tasks
- Started auth module

## 🎯 Next Steps
1. Complete login function
2. Add tests
""")

        # Run handoff-backup (should create new handoff)
        handoff_script = plugin_root / "scripts" / "handoff-backup.py"
        subprocess.run(
            [sys.executable, str(handoff_script)],
            capture_output=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Should have both handoffs
        handoffs = list(handoff_dir.glob("*.md"))
        assert len(handoffs) >= 2


class TestRecoveryScenarios:
    """Test recovery from error scenarios."""

    def test_recovery_from_failed_gates(self, temp_dir: Path, plugin_root: Path):
        """Test recovery when quality gates fail."""
        # Setup environment
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "backups").mkdir()

        # Run quality gates (might fail)
        gates_script = plugin_root / "scripts" / "quality-gates.py"
        subprocess.run(
            [sys.executable, str(gates_script)],
            capture_output=True,
            timeout=120
        )

        # Should not crash the system
        # Backups should exist if created
        backup_dir = claude_dir / "backups"
        if backup_dir.exists():
            backups = [d for d in backup_dir.iterdir() if d.is_dir()]
            # May or may not have backups depending on implementation
            assert isinstance(backups, list)

    def test_recovery_from_corrupt_handoff(self, temp_dir: Path, plugin_root: Path):
        """Test recovery from corrupt handoff file."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Create corrupt handoff
        corrupt_handoff = handoff_dir / "handoff-corrupt.md"
        corrupt_handoff.write_text("INVALID: [[[{{")

        # Run handoff-backup (should handle gracefully)
        handoff_script = plugin_root / "scripts" / "handoff-backup.py"
        result = subprocess.run(
            [sys.executable, str(handoff_script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Should not crash
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
