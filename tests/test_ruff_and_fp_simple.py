"""
Simple tests for Ruff Formatter and FP Utils - no isinstance complexity

Tests verify the actual functionality works correctly.
"""
import pytest
import tempfile
from pathlib import Path
import subprocess

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
import sys
sys.path.insert(0, str(lib_dir))

from ruff_formatter import RuffFormatter, RuffResult
from fp_utils import (
    load_config, validate_project_structure,
    safe_write_file, map_success, map_failure,
    get_or_log, parse_and_validate_config,
    get_logger, LogLevel, ConfigError, ValidationError
)


class TestRuffFormatterSimple:
    """Simple tests for Ruff formatter."""

    @pytest.mark.unit
    def test_formatter_creates_instance(self):
        """RuffFormatter should create instance."""
        formatter = RuffFormatter()
        assert formatter is not None
        assert hasattr(formatter, 'format_file')

    @pytest.mark.unit
    def test_is_available_returns_bool(self):
        """is_available should return boolean."""
        formatter = RuffFormatter()
        result = formatter.is_available()
        
        # Should return bool
        assert isinstance(result, bool)

    @pytest.mark.skipifnot(
        subprocess.run(['which', 'ruff'], capture_output=True).returncode == 0,
        reason="ruff not installed"
    )
    def test_format_creates_file(self, tmp_path):
        """format_file should create file."""
        formatter = RuffFormatter()
        
        test_file = tmp_path / "test_format.py"
        test_file.write_text("x=1\ny=2\n", encoding='utf-8')
        
        result = formatter.format_file(test_file)
        
        # Should complete
        assert result.success is True
        assert "1 file" in result.output.lower()

    @pytest.mark.unit
    def test_check_returns_exit_code(self):
        """check_and_fix should return proper exit code."""
        formatter = RuffFormatter()
        
        test_file = tmp_path / "test_check.py"
        test_file.write_text("def foo():return 1", encoding='utf-8')
        
        result = formatter.check_and_fix(test_file)
        
        # Should capture exit code
        assert result.exit_code in [0, 1]

    @pytest.mark.unit
    def test_format_and_check_works(self, tmp_path):
        """format_and_check should work correctly."""
        formatter = RuffFormatter()
        
        test_file = tmp_path / "test_both.py"
        test_file.write_text("def foo():return 1", encoding='utf-8')
        
        result = formatter.format_and_check(test_file)
        
        # Should have both operations
        assert result.success is True
        assert result.formatted is True

    @pytest.mark.unit
    def test_config_args_passed(self):
        """Config args should be passed correctly."""
        config_path = tmp_path / "ruff.toml"
        config_path.write_text("[line-length]\nmax-line-length = 100", encoding='utf-8')
        
        formatter = RuffFormatter(config_path=config_path)
        
        # Verify config args include config
        test_file = tmp_path / "test_config.py"
        test_file.write_text("x=1", encoding='utf-8')
        formatter.format_file(test_file)
        
        call_args = formatter.config_args
        assert len(call_args) > 0
        assert any("--config" in arg for arg in call_args)


class TestFPUtilsSimple:
    """Simple tests for FP utilities."""

    @pytest.mark.unit
    def test_load_config_works(self):
        """load_config should load YAML config."""
        config_path = Path("/dev/null")  # Use null device
        
        result = load_config(config_path)
        
        # Should be Failure (file not found)
        assert isinstance(result, Failure)

    @pytest.mark.unit
    def test_validate_project_passes(self):
        """validate_project_structure should pass validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid Python project structure
            project = Path(tmpdir)
            (project / "src").mkdir(parents=True, exist_ok=True)
            (project / "lib").mkdir(parents=True, exist_ok=True)
            (project / "package.json").write_text('{"name": "test"}')
            (project / "README.md").write_text("# Test")
            
            result = validate_project_structure(project)
        
        # Should be Success
        assert isinstance(result, Success)
        metadata = result.unwrap()
        assert metadata["validation_status"] == "passed"

    @pytest.mark.integration
    def test_safe_write_file_works(self):
        """safe_write_file should create files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_write.txt"
            content = "Hello, World!"
            
            result = safe_write_file(test_file, content)
        
        assert isinstance(result, Success)
        assert test_file.exists()
        assert test_file.read_text(encoding='utf-8') == content

    @pytest.mark.unit
    def test_map_success_works(self):
        """map_success should transform Success."""
        from fp_utils import map_success, Success
        
        # Create a simple function
        def add_one(x):
            return x + 1
        
        result = map_success(add_one, Success(5))
        
        assert isinstance(result, Success)
        assert result.unwrap() == 6

    @pytest.mark.unit
    def test_get_or_log_unwraps_success(self):
        """get_or_log should unwrap Success."""
        from fp_utils import get_or_log, Success
        
        result = get_or_log(Success(42), 999)
        
        assert isinstance(result, Success)
        assert result == 42

    @pytest.mark.unit
    def test_parse_and_validate_flow(self, tmp_path):
        """parse_and_validate_config should work."""
        config_path = tmp_path / "gates.yaml"
        config_path.write_text("""
gates:
  check-gate:
    command: echo "test"
""", encoding='utf-8')
        
        result = parse_and_validate_config(
            config_path,
            required_keys=["gates"]
        )
        
        assert isinstance(result, Success)
        config = result.unwrap()
        assert "check-gate" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
