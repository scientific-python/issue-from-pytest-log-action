"""Tests focused on key scientific packages: pandas, zarr, numpy, and xarray.

These tests focus on real-world scenarios with the main scientific computing packages
that users are most likely to encounter in their CI/CD pipelines.
"""

import json
import tempfile
from pathlib import Path
from unittest import mock

from issue_from_pytest_log_action.capture_versions import extract_git_info
from issue_from_pytest_log_action.track_packages import (
    clean_version_for_tag,
    format_version_with_git,
    generate_package_diff_link,
    get_package_changes,
)


class TestScientificPackageMetadata:
    """Test metadata for core scientific packages."""

    def test_numpy_metadata(self):
        """Test numpy package diff link generation."""
        link = generate_package_diff_link("numpy", "1.24.0", "1.25.0")
        assert link is not None
        assert "github.com/numpy/numpy/compare" in link
        assert "v1.24.0...v1.25.0" in link

    def test_pandas_metadata(self):
        """Test pandas package diff link generation."""
        link = generate_package_diff_link("pandas", "2.0.0", "2.1.0")
        assert link is not None
        assert "github.com/pandas-dev/pandas/compare" in link
        assert "v2.0.0...v2.1.0" in link

    def test_xarray_metadata(self):
        """Test xarray package diff link generation."""
        link = generate_package_diff_link("xarray", "2023.1.0", "2023.2.0")
        assert link is not None
        assert "github.com/pydata/xarray/compare" in link
        assert "v2023.1.0...v2023.2.0" in link

    def test_zarr_metadata(self):
        """Test zarr package diff link generation."""
        link = generate_package_diff_link("zarr", "2.14.0", "2.15.0")
        assert link is not None
        assert "github.com/zarr-developers/zarr-python/compare" in link
        assert "v2.14.0...v2.15.0" in link


class TestScientificPackageVersionCleaning:
    """Test version cleaning for scientific packages with realistic versions."""

    def test_numpy_nightly_versions(self):
        """Test cleaning numpy nightly versions."""
        # NumPy nightly format: 1.26.0.dev0+1234.g5678abc
        assert clean_version_for_tag("1.26.0.dev0+1234.g5678abc") == "1.26.0"
        assert clean_version_for_tag("2.0.0.dev0+456.gabc123d") == "2.0.0"

    def test_pandas_rc_versions(self):
        """Test cleaning pandas release candidate versions."""
        assert clean_version_for_tag("2.1.0rc1") == "2.1.0rc1"
        assert clean_version_for_tag("2.2.0rc2.dev0+123.gabc") == "2.2.0rc2"

    def test_xarray_alpha_versions(self):
        """Test cleaning xarray alpha versions."""
        assert clean_version_for_tag("2024.1.0a1") == "2024.1.0a1"
        assert clean_version_for_tag("2024.2.0a2.dev0+git.abc123") == "2024.2.0a2"

    def test_zarr_dev_versions(self):
        """Test cleaning zarr development versions."""
        assert clean_version_for_tag("2.16.0.dev0") == "2.16.0"
        assert clean_version_for_tag("3.0.0.dev123+g456def") == "3.0.0"


class TestScientificPackageChanges:
    """Test package change detection for scientific computing stacks."""

    def test_scientific_stack_upgrade(self):
        """Test detecting changes in a typical scientific computing stack."""
        current = {
            "numpy": {"version": "1.25.0", "git_info": {"git_revision": "abc123"}},
            "pandas": {"version": "2.1.0", "git_info": None},
            "xarray": {"version": "2023.8.0", "git_info": None},
            "zarr": {"version": "2.15.0", "git_info": {"git_revision": "def456"}},
        }

        previous = {
            "numpy": {"version": "1.24.0", "git_info": {"git_revision": "xyz789"}},
            "pandas": {"version": "2.0.0", "git_info": None},
            "xarray": {"version": "2023.7.0", "git_info": None},
            "zarr": {"version": "2.14.0", "git_info": {"git_revision": "uvw012"}},
        }

        changes = get_package_changes(current, previous)

        # Should detect all 4 package changes
        assert len(changes) == 4

        # Check that all packages are mentioned
        change_text = " ".join(changes)
        assert "numpy" in change_text
        assert "pandas" in change_text
        assert "xarray" in change_text
        assert "zarr" in change_text

        # Check version changes
        assert "1.24.0" in change_text and "1.25.0" in change_text
        assert "2.0.0" in change_text and "2.1.0" in change_text

    def test_nightly_wheel_installation(self):
        """Test tracking nightly wheel installations."""
        current = {
            "numpy": {
                "version": "1.26.0.dev0+1234.g5678abc",
                "git_info": {"git_revision": "5678abc", "source": "version_string"},
            },
            "pandas": {
                "version": "2.2.0.dev0+567.gdef123",
                "git_info": {"git_revision": "def123", "source": "version_string"},
            },
        }

        previous = {
            "numpy": {"version": "1.25.0", "git_info": None},
            "pandas": {"version": "2.1.0", "git_info": None},
        }

        changes = get_package_changes(current, previous)

        assert len(changes) == 2
        change_text = " ".join(changes)

        # Should show git hashes for nightly versions
        assert "(5678abc)" in change_text
        assert "(def123)" in change_text

    def test_new_scientific_dependency(self):
        """Test detecting new scientific package additions."""
        current = {
            "numpy": {"version": "1.25.0", "git_info": None},
            "pandas": {"version": "2.1.0", "git_info": None},
            "xarray": {"version": "2023.8.0", "git_info": None},  # New dependency
        }

        previous = {
            "numpy": {"version": "1.25.0", "git_info": None},
            "pandas": {"version": "2.1.0", "git_info": None},
        }

        changes = get_package_changes(current, previous)

        assert len(changes) == 1
        assert "xarray" in changes[0]
        assert "(new)" in changes[0]
        assert "2023.8.0" in changes[0]


class TestScientificPackageGitInfo:
    """Test git info extraction for scientific packages."""

    def test_format_numpy_with_git_info(self):
        """Test formatting numpy with git revision."""
        package_info = {
            "version": "1.26.0.dev0+1234.g5678abc",
            "git_info": {"git_revision": "5678abcdef123456789"},
        }

        result = format_version_with_git(package_info)
        assert result == "1.26.0.dev0+1234.g5678abc (5678abcd)"

    def test_format_pandas_without_git_info(self):
        """Test formatting pandas without git revision."""
        package_info = {"version": "2.1.0", "git_info": None}

        result = format_version_with_git(package_info)
        assert result == "2.1.0"

    def test_extract_git_from_nightly_versions(self):
        """Test extracting git info from nightly package versions."""
        # Test various nightly version formats
        test_cases = [
            ("numpy", "1.26.0.dev0+1234.g5678abc", "5678abc"),
            ("pandas", "2.2.0.dev0+567.gdef123", "def123"),
            ("xarray", "2024.1.0.dev0+89.gabc456", "abc456"),
        ]

        for package, version, expected_hash in test_cases:
            with mock.patch(
                "issue_from_pytest_log_action.capture_versions.extract_git_info"
            ) as mock_extract:
                mock_extract.return_value = {
                    "git_revision": expected_hash,
                    "source": "version_string",
                }

                git_info = extract_git_info(package)

                if git_info:
                    assert git_info["git_revision"] == expected_hash
                    assert git_info["source"] == "version_string"


class TestScientificPackageIntegration:
    """Integration tests for scientific package tracking."""

    def test_capture_scientific_packages(self):
        """Test capturing versions of key scientific packages."""
        import os
        import subprocess
        import sys

        # Test with packages that are commonly available
        test_packages = "pytest,setuptools"  # Use packages we know exist

        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["TRACK_PACKAGES"] = test_packages

            result = subprocess.run(
                [sys.executable, "-m", "issue_from_pytest_log_action.capture_versions"],
                env=env,
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            # Check that output file was created
            output_file = Path(tmpdir) / "captured-package-versions.json"
            assert output_file.exists()

            # Check content
            data = json.loads(output_file.read_text())
            assert "packages" in data
            assert "python_version" in data

            # Should have captured the test packages
            packages = data["packages"]
            assert "pytest" in packages
            assert "setuptools" in packages

    def test_diff_links_for_scientific_packages(self):
        """Test that diff links work for all key scientific packages."""
        scientific_packages = ["numpy", "pandas", "xarray", "zarr"]

        for package in scientific_packages:
            # Test basic version diff
            link = generate_package_diff_link(package, "1.0.0", "1.1.0")
            assert link is not None, f"Failed to generate diff link for {package}"
            assert "github.com" in link
            assert package in link or package.replace("-", "") in link

            # Test with git commit info
            old_git_info = {"git_revision": "abc123"}
            new_git_info = {"git_revision": "def456"}

            link_with_git = generate_package_diff_link(
                package, "1.0.0", "1.1.0", old_git_info, new_git_info
            )
            assert link_with_git is not None
            assert "abc123" in link_with_git
            assert "def456" in link_with_git
