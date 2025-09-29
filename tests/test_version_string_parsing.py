"""Test git hash extraction from version strings."""

import pytest

from issue_from_pytest_log_action.capture_versions import extract_git_hash_from_version


class TestVersionStringParsing:
    """Test parsing git hashes from version strings."""

    @pytest.mark.parametrize(
        "version_string,expected_hash",
        [
            # Common nightly wheel patterns
            ("2.1.0.dev0+123.gabc123d", "abc123d"),
            ("1.5.0.dev0+456.gdef456a789", "def456a789"),
            ("3.0.0a1.dev0+789.g123abc4", "123abc4"),
            ("2.0.0.post1.dev0+100.gabc123def456", "abc123def456"),
            # setuptools_scm patterns
            ("1.0.0+123.gabc123d", "abc123d"),
            ("2.1.0+gabc123def456789", "abc123def456789"),
            # Direct git hash patterns
            ("1.0.0.gabc123d", "abc123d"),
            ("2.1.0.gabc123def456789012345678901234567890", "abc123def456789012345678901234567890"),
            # Full SHA patterns
            ("1.0.0+g" + "a" * 40, "a" * 40),
            ("2.1.0.dev0+123.g" + "b" * 40, "b" * 40),
            # Case insensitive
            ("1.0.0+gABC123D", "ABC123D"),
            ("2.1.0.gDEF456A", "DEF456A"),
        ],
    )
    def test_extract_git_hash_from_version_success(self, version_string, expected_hash):
        """Test successful extraction of git hashes from version strings."""
        result = extract_git_hash_from_version(version_string)
        assert result == expected_hash

    @pytest.mark.parametrize(
        "version_string",
        [
            # No git hash
            "1.0.0",
            "2.1.0.dev0",
            "3.0.0a1",
            "2.0.0.post1",
            # Invalid patterns (too short)
            "1.0.0+g123",
            "2.1.0.g12345",
            # Invalid characters
            "1.0.0+gzzzyyy",
            "2.1.0.gxywzyx",
            # Edge cases
            "",
            "not.a.version",
            "1.0.0+123",  # Number without 'g' prefix
            # Package names that start with 'g' but aren't git hashes
            "1.0.0+glib2.0",
            "2.1.0.gstreamer",
            "1.5.0+gtk3.22",
        ],
    )
    def test_extract_git_hash_from_version_none(self, version_string):
        """Test cases where no git hash should be extracted."""
        result = extract_git_hash_from_version(version_string)
        assert result is None

    def test_extract_git_hash_multiple_patterns(self):
        """Test that the most specific pattern is matched first."""
        # This version has multiple potential matches, should pick the first one
        version = "1.0.0.dev0+123.gabc123d.more.gdef456"
        result = extract_git_hash_from_version(version)
        assert result == "abc123d"  # Should match the first .g pattern

    def test_extract_git_hash_minimum_length(self):
        """Test minimum hash length requirement."""
        # 7 characters should work (git short hash)
        assert extract_git_hash_from_version("1.0.0+gabcdef1") == "abcdef1"

        # 6 characters should not work
        assert extract_git_hash_from_version("1.0.0+gabcdef") is None

    def test_extract_git_hash_real_examples(self):
        """Test with real-world examples from nightly wheels."""
        real_examples = [
            # numpy nightly examples
            ("2.1.0.dev0+nightly.g1a2b3c4", "1a2b3c4"),
            # pandas nightly examples
            ("2.2.0.dev0+123.gabc123d", "abc123d"),
            # setuptools_scm examples
            ("1.0.0+dirty", None),  # dirty build, no git hash
            ("1.0.0+123.dirty", None),  # dirty build, no git hash
        ]

        for version, expected in real_examples:
            result = extract_git_hash_from_version(version)
            assert result == expected, f"Failed for {version}: got {result}, expected {expected}"

    def test_packages_starting_with_g(self):
        """Test that packages starting with 'g' don't interfere with git hash extraction."""
        from unittest.mock import MagicMock, patch

        from issue_from_pytest_log_action.capture_versions import extract_git_info

        # Test packages that start with 'g'
        g_packages = ["glib", "gtk", "gstreamer", "gdal", "greenlet"]

        for package_name in g_packages:
            with patch("importlib.import_module") as mock_import:
                # Mock a package with a version that contains a git hash
                mock_pkg = MagicMock()
                mock_pkg.__version__ = "2.1.0.dev0+123.gabc123d"

                # Remove version module attributes to force fallback to __version__
                delattr(mock_pkg, "version")
                delattr(mock_pkg, "_version")
                delattr(mock_pkg, "__git_revision__")

                mock_import.return_value = mock_pkg

                git_info = extract_git_info(package_name)

                # Should successfully extract git hash despite package name starting with 'g'
                assert git_info.get("git_revision") == "abc123d"
                assert git_info.get("source") == "version_string"

        # Test edge case: package named 'g' itself
        with patch("importlib.import_module") as mock_import:
            mock_pkg = MagicMock()
            mock_pkg.__version__ = "1.0.0+gabc123def"

            # Remove version module attributes to force fallback to __version__
            delattr(mock_pkg, "version")
            delattr(mock_pkg, "_version")
            delattr(mock_pkg, "__git_revision__")

            mock_import.return_value = mock_pkg

            git_info = extract_git_info("g")
            assert git_info.get("git_revision") == "abc123def"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
