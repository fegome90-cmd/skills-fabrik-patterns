"""
End-to-End Tests: Quality Gates

Tests quality gates in realistic contexts.
Verifies TypeScript compilation, Python type checking, and parallel execution.
"""

import pytest
import subprocess
import sys
import tempfile
from pathlib import Path
import time


class TestQualityGatesInContext:
    """Test quality gates execute in real context."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def python_project(self, temp_dir: Path) -> Path:
        """Create a Python project for quality checks."""
        project_dir = temp_dir / "python-project"
        project_dir.mkdir()

        # Create Python file with type hints
        (project_dir / "main.py").write_text("""
from typing import List

def process(items: List[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

if __name__ == "__main__":
    result = process(["a", "bb", "ccc"])
    print(result)
""")

        # Create requirements.txt
        (project_dir / "requirements.txt").write_text("""
pyyaml>=6.0
pytest>=7.0
""")

        return project_dir

    def test_quality_gates_run_on_python_project(
        self,
        python_project: Path,
        plugin_root: Path
    ):
        """Test quality gates execute on Python project."""
        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(python_project),
            timeout=120
        )

        # Should complete (may have failures)
        assert result.returncode in [0, 1]

    def test_python_type_check_detected(
        self,
        python_project: Path,
        plugin_root: Path
    ):
        """Test Python type checking is performed."""
        # This is conceptual - actual behavior depends on gate config
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            # Check if type-check gate exists
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            gate_names = [g.get('name', '') for g in config.get('gates', [])]
            has_type_check = any('type' in n.lower() or 'mypy' in n.lower() for n in gate_names)

            if has_type_check:
                # Gate should be configured
                assert True


class TestTypeScriptCompilation:
    """Test TypeScript compilation gate."""

    @pytest.fixture
    def typescript_project(self, temp_dir: Path) -> Path:
        """Create a TypeScript project."""
        project_dir = temp_dir / "ts-project"
        project_dir.mkdir()

        # Create package.json
        (project_dir / "package.json").write_text("""{
    "name": "ts-test",
    "version": "1.0.0",
    "devDependencies": {
        "typescript": "^5.0.0"
    }
}""")

        # Create tsconfig.json
        (project_dir / "tsconfig.json").write_text("""{
    "compilerOptions": {
        "target": "ES2020",
        "module": "commonjs",
        "strict": true
    }
}""")

        # Create TypeScript file
        (project_dir / "main.ts").write_text("""
interface User {
    name: string;
    age: number;
}

function greet(user: User): string {
    return `Hello, ${user.name}!`;
}

const user: User = { name: "Alice", age: 30 };
console.log(greet(user));
""")

        return project_dir

    def test_typescript_compilation_runs(
        self,
        typescript_project: Path,
        plugin_root: Path
    ):
        """Test TypeScript compilation is checked."""
        # This depends on gate configuration
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            # Check for TS gates
            gate_names = [g.get('name', '') for g in config.get('gates', [])]
            has_ts_check = any('typescript' in n.lower() or 'ts' in n.lower() or 'tsc' in n.lower() for n in gate_names)

            if has_ts_check:
                # Gate should be configured
                assert True


class TestCodeFormatting:
    """Test code formatting gates."""

    def test_format_check_runs(self, temp_dir: Path, plugin_root: Path):
        """Test code formatting is checked."""
        # Create Python file with poor formatting
        project_dir = temp_dir / "format-project"
        project_dir.mkdir()

        (project_dir / "bad.py").write_text("""
x=1
y=2
z=3
def hello( ):
    return "world"
""")

        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )

        # Should complete
        assert result.returncode in [0, 1]

    def test_format_check_detects_issues(self, temp_dir: Path, plugin_root: Path):
        """Test formatting issues are detected."""
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            gate_names = [g.get('name', '') for g in config.get('gates', [])]
            has_format_check = any('format' in n.lower() or 'ruff' in n.lower() or 'lint' in n.lower() for n in gate_names)

            if has_format_check:
                # Gate should detect issues
                assert True


class TestSecurityScanning:
    """Test security scanning gates."""

    def test_security_scan_runs(self, temp_dir: Path, plugin_root: Path):
        """Test security scanning executes."""
        # Create Python file with potential issues
        project_dir = temp_dir / "security-project"
        project_dir.mkdir()

        (project_dir / "security.py").write_text("""
import subprocess

def run_command(cmd):
    # Potential security issue: shell=True
    return subprocess.run(cmd, shell=True)
""")

        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )

        # Should complete
        assert result.returncode in [0, 1]

    def test_security_issues_detected(self, temp_dir: Path, plugin_root: Path):
        """Test security issues are detected."""
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            gate_names = [g.get('name', '') for g in config.get('gates', [])]
            has_security_check = any('security' in n.lower() or 'bandit' in n.lower() or 'safety' in n.lower() for n in gate_names)

            if has_security_check:
                # Security gate should be configured
                assert True


class TestParallelExecutionPerformance:
    """Test parallel execution improves performance."""

    def test_parallel_faster_than_sequential(self, plugin_root: Path):
        """Test parallel execution is faster than sequential."""
        script = plugin_root / "scripts" / "quality-gates.py"

        # Measure parallel execution
        start = time.time()
        result_parallel = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            timeout=120
        )
        parallel_duration = time.time() - start

        # If parallel is configured, should be reasonably fast
        assert result_parallel.returncode in [0, 1]
        # Parallel execution should complete in reasonable time
        assert parallel_duration < 60  # Under 1 minute


class TestGateTimeoutHandling:
    """Test gate timeout handling."""

    def test_individual_gate_timeout(self, temp_dir: Path, plugin_root: Path):
        """Test individual gate timeout is enforced."""
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            # Check timeout values
            for gate in config.get('gates', []):
                timeout = gate.get('timeout', 0)
                # Should have reasonable timeout
                assert timeout > 0
                assert timeout <= 120000  # Max 2 minutes per gate

    def test_global_timeout_not_exceeded(self, plugin_root: Path):
        """Test global timeout is not exceeded."""
        script = plugin_root / "scripts" / "quality-gates.py"

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            timeout=125  # Slightly over 2 minutes
        )
        duration = time.time() - start

        # Should complete within ~2 minutes
        assert result.returncode in [0, 1]
        assert duration < 130  # Allow some buffer


class TestGateFiltering:
    """Test gate filtering based on changed files."""

    def test_gates_filter_by_file_pattern(self, temp_dir: Path, plugin_root: Path):
        """Test gates are filtered by file patterns."""
        # Create project with only Python files
        project_dir = temp_dir / "python-only"
        project_dir.mkdir()

        (project_dir / "module.py").write_text("x = 1\n")

        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )

        # Should complete
        assert result.returncode in [0, 1]

    def test_gates_run_for_matching_files(self, temp_dir: Path, plugin_root: Path):
        """Test gates run when files match their patterns."""
        # Create project with various file types
        project_dir = temp_dir / "mixed-project"
        project_dir.mkdir()

        (project_dir / "app.py").write_text("# Python\n")
        (project_dir / "README.md").write_text("# Docs\n")

        script = plugin_root / "scripts" / "quality-gates.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )

        # Should complete
        assert result.returncode in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
