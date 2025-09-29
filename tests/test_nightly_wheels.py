"""Test nightly wheel support with scientific Python packages."""

import json
import os
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from issue_from_pytest_log_action.capture_versions import extract_git_info


class TestNightlyWheelSupport:
    """Test support for scientific Python nightly wheels."""

    @pytest.mark.parametrize(
        "package_name", ["numpy", "pandas", "scipy", "matplotlib", "xarray", "zarr"]
    )
    def test_git_info_extraction_for_scientific_packages(self, package_name):
        """Test git info extraction for common scientific packages."""
        # This test checks if our extraction works, but doesn't require the packages to be installed
        with patch("importlib.import_module") as mock_import:
            # Mock a nightly wheel package with git info
            mock_pkg = MagicMock()
            mock_pkg.version.git_revision = "abc123def456789012345678901234567890abcd"
            mock_pkg.version.full_version = "2.1.0.dev0+123.gabc123d"
            mock_import.return_value = mock_pkg

            git_info = extract_git_info(package_name)

            assert git_info.get("git_revision") == "abc123def456789012345678901234567890abcd"
            assert git_info.get("full_version") == "2.1.0.dev0+123.gabc123d"

    def test_nightly_wheel_version_patterns(self):
        """Test handling of nightly wheel version patterns."""
        # Common nightly version patterns
        nightly_patterns = [
            "2.1.0.dev0",
            "1.5.0.dev0+123.gabc123d",
            "3.0.0a1.dev0+456.gdef456a",
            "2.0.0.post1.dev0+789.g123abc4",
        ]

        for version in nightly_patterns:
            # Test that we can parse these version formats
            package_info = {
                "version": version,
                "git_info": {"git_revision": "abc123def456789012345678901234567890abcd"},
            }

            from issue_from_pytest_log_action.track_packages import (
                extract_version_string,
                format_version_with_git,
            )

            extracted_version = extract_version_string(package_info)
            assert extracted_version == version

            formatted = format_version_with_git(package_info)
            assert version in formatted
            assert "(abc123de)" in formatted

    def test_capture_multiple_scientific_packages(self):
        """Test capturing multiple scientific packages at once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_env = os.environ.copy()
            # Test with packages that might be available
            test_env["TRACK_PACKAGES"] = "pytest,setuptools"

            # Use the installed package script
            result = subprocess.run(
                [sys.executable, "-m", "issue_from_pytest_log_action.capture_versions"],
                env=test_env,
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Script failed: {result.stderr}"

            with open(f"{tmpdir}/captured-package-versions.json") as f:
                data = json.load(f)

            packages = data["packages"]
            assert len(packages) >= 1  # Should capture at least one package

            # Check that each captured package has the expected structure
            for pkg_name, pkg_info in packages.items():
                if pkg_info is not None:  # Skip packages that weren't found
                    if isinstance(pkg_info, dict):
                        assert "version" in pkg_info
                        assert "git_info" in pkg_info
                    else:
                        # Old string format is also acceptable
                        assert isinstance(pkg_info, str)

    def test_scientific_python_nightly_index_handling(self):
        """Test that we can handle the scientific Python nightly wheel index format."""
        # This tests the theoretical handling of nightly wheels
        # In practice, these would come from: https://pypi.anaconda.org/scientific-python-nightly-wheels/simple

        mock_nightly_packages = {
            "numpy": {
                "version": "2.1.0.dev0",
                "git_info": {
                    "git_revision": "e7a123b2d3eca9897843791dd698c1803d9a39c2",
                    "full_version": "2.1.0.dev0+nightly",
                },
            },
            "pandas": {
                "version": "2.2.0.dev0",
                "git_info": {
                    "git_revision": "def456c9b8e7f6a5d4c3b2a1f0e9d8c7b6a59483",
                    "full_version": "2.2.0.dev0+nightly",
                },
            },
        }

        # Test that package changes detect nightly wheel updates properly
        from issue_from_pytest_log_action.track_packages import get_package_changes

        # Simulate updating from one nightly to another
        previous_nightly = {
            "numpy": {
                "version": "2.1.0.dev0",
                "git_info": {
                    "git_revision": "old123b2d3eca9897843791dd698c1803d9a39c2",
                },
            }
        }

        changes = get_package_changes(mock_nightly_packages, previous_nightly)

        # Should detect git revision change for numpy
        numpy_change = [c for c in changes if "numpy" in c][0]
        assert "git revision changed" in numpy_change
        assert "2.1.0.dev0 (old123b2)" in numpy_change
        assert "2.1.0.dev0 (e7a123b2)" in numpy_change

        # Should detect new package pandas
        pandas_change = [c for c in changes if "pandas" in c][0]
        assert "(new)" in pandas_change
        assert "2.2.0.dev0 (def456c9)" in pandas_change


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
