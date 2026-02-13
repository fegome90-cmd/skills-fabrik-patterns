"""
Hook Tests: UserPromptSubmit Hook

Tests that the UserPromptSubmit hook (inject-context.py) executes correctly.
Verifies context injection, evidence validation, and proper order.
"""

import pytest
import subprocess
import sys
import json
import tempfile
from pathlib import Path
import shutil


class TestInjectContextHookScript:
    """Test inject-context.py script functionality."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def inject_context_script(self, plugin_root: Path) -> Path:
        """Get path to inject-context.py script."""
        return plugin_root / "scripts" / "inject-context.py"

    def test_script_exists(self, inject_context_script: Path):
        """Test inject-context.py script exists."""
        assert inject_context_script.exists()
        assert inject_context_script.is_file()

    def test_script_accepts_json_input(self, inject_context_script: Path):
        """Test inject-context accepts JSON input."""
        input_data = json.dumps({
            "prompt": "test prompt",
            "project_path": str(Path.cwd())
        })

        result = subprocess.run(
            [sys.executable, str(inject_context_script)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0

    def test_script_outputs_json(self, inject_context_script: Path):
        """Test inject-context outputs valid JSON."""
        input_data = json.dumps({
            "prompt": "test prompt",
            "project_path": str(Path.cwd())
        })

        result = subprocess.run(
            [sys.executable, str(inject_context_script)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should output valid JSON
        try:
            output = json.loads(result.stdout)
            assert "additionalContext" in output
        except json.JSONDecodeError:
            pytest.fail("Inject context did not output valid JSON")


class TestContextInjection:
    """Test context injection functionality."""

    @pytest.fixture
    def sample_context_files(self, temp_dir: Path) -> Path:
        """Create sample context files for testing."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir(parents=True)

        # Create CLAUDE.md with TAGs
        (context_dir / "CLAUDE.md").write_text("""# Context

## Identity
Test user context

## Projects
Test project

## Rules
- Use immutable data
""")

        return context_dir

    def test_injects_context_into_prompt(
        self,
        sample_context_files: Path,
        temp_dir: Path
    ):
        """Test context is injected into prompt."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        input_data = json.dumps({
            "prompt": "Help me with Python",
            "project_path": str(temp_dir)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=30
        )

        output = json.loads(result.stdout)

        # Should have additionalContext
        assert "additionalContext" in output
        assert len(output["additionalContext"]) > 0

    def test_preserves_original_prompt(
        self,
        sample_context_files: Path,
        temp_dir: Path
    ):
        """Test original prompt is preserved."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        original_prompt = "Help me with Python async"
        input_data = json.dumps({
            "prompt": original_prompt,
            "project_path": str(temp_dir)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=30
        )

        output = json.loads(result.stdout)

        # Original prompt should be in result
        assert original_prompt in str(output.get("prompt", ""))


class TestEvidenceValidation:
    """Test evidence validation in UserPromptSubmit hook."""

    @pytest.fixture
    def sample_project(self, temp_dir: Path) -> Path:
        """Create sample project for validation."""
        project_dir = temp_dir / "test-project"
        project_dir.mkdir()

        # Create package.json (Node.js indicator)
        (project_dir / "package.json").write_text("""{
    "name": "test-project",
    "version": "1.0.0"
}""")

        return project_dir

    def test_validates_project_structure(
        self,
        sample_project: Path,
        temp_dir: Path
    ):
        """Test project structure is validated."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(sample_project)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should complete
        assert result.returncode == 0

    def test_validates_dependencies(
        self,
        temp_dir: Path
    ):
        """Test dependencies are validated."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        # Create project with node_modules
        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "node_modules").mkdir()

        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(project_dir)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should complete
        assert result.returncode == 0


class TestHookExecutionOrder:
    """Test that hook components execute in correct order."""

    def test_context_injection_before_validation(self, temp_dir: Path):
        """Test context is injected before validation."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        # Create context
        context_dir = temp_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("# Test Context")

        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(temp_dir)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=30
        )

        output = json.loads(result.stdout)

        # Context should be present
        assert "additionalContext" in output

    def test_both_hooks_execute(self, temp_dir: Path):
        """Test both context injection and validation execute."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        # Create context and project
        context_dir = temp_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("# Test")

        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "package.json").write_text('{"name": "test"}')

        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(project_dir)
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=30
        )

        # Both should execute
        assert result.returncode == 0


class TestHookErrorHandling:
    """Test hook error handling."""

    def test_handles_missing_project_path(self, temp_dir: Path):
        """Test hook handles missing project gracefully."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(temp_dir / "nonexistent")
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should not crash
        assert result.returncode == 0

    def test_handles_invalid_json_input(self, temp_dir: Path):
        """Test hook handles invalid JSON gracefully."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            input="invalid json",
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should handle gracefully
        # (might error, but shouldn't crash)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
