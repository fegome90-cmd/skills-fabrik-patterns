"""
Integration Tests for Skills-Fabrik Patterns Plugin

Tests complete workflows and hook interactions.
"""

import pytest
import json
import subprocess
import tempfile
from pathlib import Path
import sys

# Add lib to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))


class TestHealthCheckHook:
    """Test SessionStart health check hook."""

    def test_health_check_script_exists(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "health-check.py"
        assert script.exists()

    def test_health_check_runs(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True
        )

        assert result.returncode in [0, 1]  # 1 only if unhealthy

        # Should output valid JSON
        try:
            output = json.loads(result.stdout)
            assert "status" in output
            assert "checks" in output
        except json.JSONDecodeError:
            pytest.fail("Health check did not output valid JSON")


class TestInjectContextHook:
    """Test UserPromptSubmit inject context hook."""

    def test_inject_context_script_exists(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "inject-context.py"
        assert script.exists()

    def test_inject_context_runs(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "inject-context.py"

        # Simulate input from Claude Code
        input_data = json.dumps({
            "prompt": "test prompt",
            "project_path": str(Path.cwd())
        })

        result = subprocess.run(
            [sys.executable, str(script)],
            input=input_data,
            capture_output=True,
            text=True
        )

        # Should not fail
        assert result.returncode == 0

        # Should output valid JSON
        try:
            output = json.loads(result.stdout)
            assert "additionalContext" in output
        except json.JSONDecodeError:
            pytest.fail("Inject context did not output valid JSON")


class TestQualityGatesHook:
    """Test Stop quality gates hook."""

    def test_quality_gates_script_exists(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "quality-gates.py"
        assert script.exists()

    def test_quality_gates_runs(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # May fail if security issues found, that's expected
        # Just check it runs and outputs something
        assert result.returncode in [0, 1]
        assert len(result.stdout) > 0 or len(result.stderr) > 0


class TestHandoffBackupHook:
    """Test PreCompact handoff+backup hook."""

    def test_handoff_backup_script_exists(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"
        assert script.exists()

    def test_handoff_backup_runs(self):
        plugin_root = Path(__file__).parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Handoff saved" in result.stdout
        assert "Backup created" in result.stdout


class TestPluginStructure:
    """Test plugin structure is correct."""

    def test_plugin_metadata_exists(self):
        plugin_root = Path(__file__).parent.parent
        metadata = plugin_root / ".claude-plugin" / "plugin.json"
        assert metadata.exists()

        with open(metadata) as f:
            data = json.load(f)
            assert "name" in data
            assert "hooks" in data

    def test_hooks_json_exists(self):
        plugin_root = Path(__file__).parent.parent
        hooks_file = plugin_root / ".claude-plugin" / "hooks" / "hooks.json"
        assert hooks_file.exists()

        with open(hooks_file) as f:
            data = json.load(f)
            assert "hooks" in data

    def test_required_config_files_exist(self):
        plugin_root = Path(__file__).parent.parent
        config_dir = plugin_root / "config"

        required_files = [
            "gates.yaml",
            "alerts.yaml",
            "evidence.yaml"
        ]

        for filename in required_files:
            assert (config_dir / filename).exists()

    def test_required_lib_files_exist(self):
        plugin_root = Path(__file__).parent.parent
        lib_dir = plugin_root / "lib"

        required_files = [
            "health.py",
            "tag_system.py",
            "evidence_cli.py",
            "quality_gates.py",
            "alerts.py",
            "handoff.py",
            "backup.py"
        ]

        for filename in required_files:
            assert (lib_dir / filename).exists()


class TestConfigLoading:
    """Test configuration file loading."""

    def test_gates_config_loads(self):
        plugin_root = Path(__file__).parent.parent
        import yaml

        with open(plugin_root / "config" / "gates.yaml") as f:
            config = yaml.safe_load(f)
            assert "gates" in config

    def test_alerts_config_loads(self):
        plugin_root = Path(__file__).parent.parent
        import yaml

        with open(plugin_root / "config" / "alerts.yaml") as f:
            config = yaml.safe_load(f)
            assert "thresholds" in config

    def test_evidence_config_loads(self):
        plugin_root = Path(__file__).parent.parent
        import yaml

        with open(plugin_root / "config" / "evidence.yaml") as f:
            config = yaml.safe_load(f)
            assert "validation" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
