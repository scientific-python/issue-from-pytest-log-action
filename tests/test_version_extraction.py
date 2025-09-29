"""Test version extraction and git info functionality."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from capture_versions import extract_git_info
from track_packages import (
    extract_git_revision,
    extract_version_string,
    format_version_with_git,
    get_package_changes,
)


class TestGitInfoExtraction:
    """Test git info extraction from packages."""

    def test_extract_git_info_with_revision(self):
        """Test extracting git info from a package that has git_revision."""
        with patch("importlib.import_module") as mock_import:
            # Mock package with git revision
            mock_pkg = MagicMock()
            mock_pkg.version.git_revision = "abc123def456"
            mock_pkg.version.full_version = "1.0.0"
            mock_import.return_value = mock_pkg

            result = extract_git_info("numpy")

            assert result["git_revision"] == "abc123def456"
            assert result["full_version"] == "1.0.0"

    def test_extract_git_info_with_versioneer(self):
        """Test extracting git info from a package using versioneer."""
        with patch("importlib.import_module") as mock_import:
            # Mock package with versioneer-style version info
            mock_pkg = MagicMock()

            def mock_get_versions():
                return {
                    "version": "1.0.0+123.gabc123d",
                    "full-revisionid": "abc123def456789",
                    "dirty": False,
                    "error": None,
                }

            mock_pkg._version.get_versions = mock_get_versions
            # Remove other attributes to ensure we hit the _version.get_versions path
            delattr(mock_pkg, "version")
            mock_import.return_value = mock_pkg

            result = extract_git_info("some_package")

            # The function should update the result dict with the returned values
            assert "version" in result
            assert "full-revisionid" in result

    def test_extract_git_info_no_version_info(self):
        """Test extracting git info from a package without version info."""
        with patch("importlib.import_module") as mock_import:
            # Mock package without version info
            mock_pkg = MagicMock()
            # Remove all version-related attributes
            del mock_pkg.version
            del mock_pkg._version
            del mock_pkg.__git_revision__
            mock_import.return_value = mock_pkg

            result = extract_git_info("basic_package")

            assert result == {}

    def test_extract_git_info_import_error(self):
        """Test handling import errors gracefully."""
        with patch("importlib.import_module", side_effect=ImportError("Package not found")):
            result = extract_git_info("nonexistent_package")

            assert result == {}


class TestVersionStringExtraction:
    """Test version string extraction from different formats."""

    def test_extract_version_string_from_dict(self):
        """Test extracting version from new dict format."""
        package_info = {"version": "2.1.0", "git_info": {"git_revision": "abc123"}}
        result = extract_version_string(package_info)
        assert result == "2.1.0"

    def test_extract_version_string_from_string(self):
        """Test extracting version from old string format."""
        package_info = "1.5.0"
        result = extract_version_string(package_info)
        assert result == "1.5.0"

    def test_extract_version_string_none(self):
        """Test handling None input."""
        result = extract_version_string(None)
        assert result is None

    def test_extract_git_revision_from_dict(self):
        """Test extracting git revision from dict format."""
        package_info = {"version": "2.1.0", "git_info": {"git_revision": "abc123def456"}}
        result = extract_git_revision(package_info)
        assert result == "abc123def456"

    def test_extract_git_revision_no_git_info(self):
        """Test extracting git revision when not available."""
        package_info = {"version": "2.1.0"}
        result = extract_git_revision(package_info)
        assert result is None

    def test_extract_git_revision_from_string(self):
        """Test extracting git revision from old string format."""
        result = extract_git_revision("1.5.0")
        assert result is None


class TestVersionFormatting:
    """Test version formatting with git info."""

    def test_format_version_with_git_info(self):
        """Test formatting version with git revision."""
        package_info = {
            "version": "2.1.0",
            "git_info": {"git_revision": "abc123def456789012345678901234567890abcd"},
        }
        result = format_version_with_git(package_info)
        assert result == "2.1.0 (abc123de)"

    def test_format_version_without_git_info(self):
        """Test formatting version without git revision."""
        package_info = {"version": "2.1.0"}
        result = format_version_with_git(package_info)
        assert result == "2.1.0"

    def test_format_version_string_format(self):
        """Test formatting old string format."""
        result = format_version_with_git("1.5.0")
        assert result == "1.5.0"

    def test_format_version_none(self):
        """Test formatting None."""
        result = format_version_with_git(None)
        assert result == "(missing)"


class TestPackageChanges:
    """Test package change detection."""

    def test_package_changes_version_only(self):
        """Test detecting version-only changes."""
        current = {"numpy": "2.1.0"}
        previous = {"numpy": "2.0.0"}

        changes = get_package_changes(current, previous)

        assert len(changes) == 1
        assert "numpy: 2.0.0 → 2.1.0" in changes[0]

    def test_package_changes_with_git_info(self):
        """Test detecting changes with git revision info."""
        current = {
            "numpy": {
                "version": "2.1.0",
                "git_info": {"git_revision": "newcommitabc123def456789012345678901234567890"},
            }
        }
        previous = {
            "numpy": {
                "version": "2.1.0",
                "git_info": {"git_revision": "oldcommitdef456789012345678901234567890abc123"},
            }
        }

        changes = get_package_changes(current, previous)

        assert len(changes) == 1
        assert "git revision changed" in changes[0]
        assert "2.1.0 (oldcommi)" in changes[0]
        assert "2.1.0 (newcommi)" in changes[0]

    def test_package_changes_mixed_formats(self):
        """Test detecting changes between old and new formats."""
        current = {
            "numpy": {
                "version": "2.1.0",
                "git_info": {"git_revision": "abc123def456789012345678901234567890abcd"},
            }
        }
        previous = {"numpy": "2.0.0"}

        changes = get_package_changes(current, previous)

        assert len(changes) == 1
        assert "numpy: 2.0.0 → 2.1.0 (abc123de)" in changes[0]

    def test_package_changes_new_package(self):
        """Test detecting new packages."""
        current = {"pandas": "1.5.0"}
        previous = {}

        changes = get_package_changes(current, previous)

        assert len(changes) == 1
        assert "pandas: (new) → 1.5.0" in changes[0]

    def test_package_changes_removed_package(self):
        """Test detecting removed packages."""
        current = {}
        previous = {"pandas": "1.4.0"}

        changes = get_package_changes(current, previous)

        assert len(changes) == 1
        assert "pandas: 1.4.0 → (removed)" in changes[0]


class TestCaptureVersionsIntegration:
    """Integration tests for the capture_versions script."""

    def test_capture_versions_output_structure(self):
        """Test that capture_versions produces correct JSON structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_env = os.environ.copy()
            test_env["TRACK_PACKAGES"] = "pytest"  # Use pytest as it should always be available

            import subprocess
            import sys

            # Use the script directly from the source directory
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "capture_versions.py"
            )
            result = subprocess.run(
                [sys.executable, script_path],
                env=test_env,
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Script failed: {result.stderr}"

            # Read the output file
            with open(os.path.join(tmpdir, "captured-package-versions.json")) as f:
                data = json.load(f)

            # Check required fields
            assert "python_version" in data
            assert "python_executable" in data
            assert "packages" in data
            assert "capture_method" in data

            # Check pytest package info
            assert "pytest" in data["packages"]
            pytest_info = data["packages"]["pytest"]

            if isinstance(pytest_info, dict):
                # New format with git_info
                assert "version" in pytest_info
                assert "git_info" in pytest_info
            else:
                # Old format (string)
                assert isinstance(pytest_info, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
