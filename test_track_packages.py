import json
import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import hypothesis.strategies as st
from hypothesis import given

import track_packages


def test_get_package_version_existing():
    """Test getting version of an existing package."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Name: pytest\nVersion: 7.4.0\nSummary: ..."
        mock_run.return_value.check = True

        version = track_packages.get_package_version("pytest")
        assert version == "7.4.0"


def test_get_package_version_nonexistent():
    """Test getting version of a non-existent package."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = track_packages.subprocess.CalledProcessError(1, "pip")

        version = track_packages.get_package_version("nonexistent-package")
        assert version is None


def test_get_all_installed_packages():
    """Test getting all installed packages."""
    mock_packages = [
        {"name": "pytest", "version": "7.4.0"},
        {"name": "hypothesis", "version": "6.82.0"},
        {"name": "more-itertools", "version": "10.1.0"},
    ]

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = json.dumps(mock_packages)
        mock_run.return_value.check = True

        packages = track_packages.get_all_installed_packages()
        expected = {
            "pytest": "7.4.0",
            "hypothesis": "6.82.0",
            "more-itertools": "10.1.0",
        }
        assert packages == expected


def test_get_current_package_versions_specific():
    """Test getting versions of specific packages."""
    with patch("track_packages.get_package_version") as mock_get_version:
        mock_get_version.side_effect = lambda pkg: {
            "pytest": "7.4.0",
            "hypothesis": "6.82.0",
            "nonexistent": None,
        }.get(pkg)

        versions = track_packages.get_current_package_versions(
            ["pytest", "hypothesis", "nonexistent"]
        )
        expected = {
            "pytest": "7.4.0",
            "hypothesis": "6.82.0",
            "nonexistent": None,
        }
        assert versions == expected


def test_get_current_package_versions_from_captured_file():
    """Test getting versions from a captured JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        captured_data = {
            "python_version": "3.11.0",
            "packages": {"pytest": "7.4.0", "numpy": "1.24.0", "requests": "2.31.0"},
            "capture_method": "importlib.metadata",
        }
        json.dump(captured_data, f)
        captured_file = f.name

    try:
        # Test specific packages
        versions = track_packages.get_current_package_versions(
            ["pytest", "numpy", "missing"], captured_file
        )
        expected = {"pytest": "7.4.0", "numpy": "1.24.0", "missing": None}
        assert versions == expected

        # Test "all" packages
        all_versions = track_packages.get_current_package_versions(["all"], captured_file)
        expected_all = {"pytest": "7.4.0", "numpy": "1.24.0", "requests": "2.31.0"}
        assert all_versions == expected_all
    finally:
        os.unlink(captured_file)


def test_get_current_package_versions_fallback_on_bad_file():
    """Test fallback when captured file is invalid."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("invalid json content")
        bad_file = f.name

    try:
        with patch("track_packages.get_package_version") as mock_get_version:
            mock_get_version.return_value = "fallback-version"

            versions = track_packages.get_current_package_versions(["pytest"], bad_file)
            expected = {"pytest": "fallback-version"}
            assert versions == expected
    finally:
        os.unlink(bad_file)


def test_get_current_package_versions_all():
    """Test getting versions when 'all' is specified."""
    with patch("track_packages.get_all_installed_packages") as mock_get_all:
        mock_get_all.return_value = {"pytest": "7.4.0", "hypothesis": "6.82.0"}

        versions = track_packages.get_current_package_versions(["all"])
        assert versions == {"pytest": "7.4.0", "hypothesis": "6.82.0"}


def test_get_git_info():
    """Test getting Git information."""
    with patch("subprocess.run") as mock_run:
        # Mock the sequence of git commands
        mock_run.side_effect = [
            Mock(stdout="abc123def456789\n", check=True),  # git rev-parse HEAD
            Mock(stdout="Fix test regression\n", check=True),  # git log -1 --pretty=format:%s
            Mock(
                stdout="John Doe <john@example.com>\n", check=True
            ),  # git log -1 --pretty=format:%an <%ae>
            Mock(
                stdout="2024-01-15 10:30:00 +0000\n", check=True
            ),  # git log -1 --pretty=format:%ci
        ]

        git_info = track_packages.get_git_info()

        expected = {
            "commit_hash": "abc123def456789",
            "commit_hash_short": "abc123de",
            "commit_message": "Fix test regression",
            "commit_author": "John Doe <john@example.com>",
            "commit_date": "2024-01-15 10:30:00 +0000",
        }
        assert git_info == expected


def test_extract_failed_tests_from_log():
    """Test extracting failed tests from pytest log file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write sample pytest log entries
        f.write(
            '{"$report_type": "TestReport", "nodeid": "test_file.py::test_pass", "outcome": "passed"}\n'
        )
        f.write(
            '{"$report_type": "TestReport", "nodeid": "test_file.py::test_fail1", "outcome": "failed"}\n'
        )
        f.write(
            '{"$report_type": "CollectReport", "nodeid": "test_file.py::test_fail2", "outcome": "failed"}\n'
        )
        f.write(
            '{"$report_type": "TestReport", "nodeid": "test_file.py::test_skip", "outcome": "skipped"}\n'
        )
        f.write('{"$report_type": "WarningMessage", "outcome": "failed"}\n')  # Should be ignored
        log_path = f.name

    try:
        failed_tests = track_packages.extract_failed_tests_from_log(log_path)
        expected = ["test_file.py::test_fail1", "test_file.py::test_fail2"]
        assert failed_tests == expected
    finally:
        os.unlink(log_path)


def test_extract_failed_tests_from_log_missing_file():
    """Test extracting failed tests when log file doesn't exist."""
    failed_tests = track_packages.extract_failed_tests_from_log("nonexistent.jsonl")
    assert failed_tests == []


def test_get_git_info_failure():
    """Test getting Git information when git commands fail."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = track_packages.subprocess.CalledProcessError(1, "git")

        git_info = track_packages.get_git_info()

        expected = {
            "commit_hash": "unknown",
            "commit_hash_short": "unknown",
            "commit_message": "unknown",
            "commit_author": "unknown",
            "commit_date": "unknown",
        }
        assert git_info == expected


def test_create_bisect_data():
    """Test creating bisection data."""
    packages = ["pytest", "hypothesis"]

    with (
        patch("track_packages.get_current_package_versions") as mock_get_versions,
        patch("track_packages.get_git_info") as mock_get_git,
        patch("track_packages.extract_failed_tests_from_log") as mock_extract_tests,
    ):
        mock_get_versions.return_value = {"pytest": "7.4.0", "hypothesis": "6.82.0"}
        mock_get_git.return_value = {
            "commit_hash": "abc123",
            "commit_hash_short": "abc123de",
            "commit_message": "Test commit",
            "commit_author": "Test Author",
            "commit_date": "2024-01-01",
        }
        mock_extract_tests.return_value = []

        with patch.dict("os.environ", {"GITHUB_RUN_ID": "12345"}):
            data = track_packages.create_bisect_data(packages)

            assert data["workflow_run_id"] == "12345"
            assert data["python_version"] == ".".join(str(v) for v in sys.version_info[:3])
            assert data["packages"] == {"pytest": "7.4.0", "hypothesis": "6.82.0"}
            assert data["failed_tests"] == []
            assert data["test_status"] == "passed"
            assert data["git"]["commit_hash"] == "abc123"
            assert "timestamp" in data
            # Check timestamp format
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


def test_create_bisect_data_with_captured_versions():
    """Test creating bisection data with captured versions file."""
    packages = ["pytest", "numpy"]

    # Create a captured versions file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        captured_data = {
            "python_version": "3.11.5",
            "packages": {"pytest": "7.4.2", "numpy": "1.25.1"},
        }
        json.dump(captured_data, f)
        captured_file = f.name

    try:
        with (
            patch("track_packages.get_git_info") as mock_get_git,
            patch("track_packages.extract_failed_tests_from_log") as mock_extract_tests,
        ):
            mock_get_git.return_value = {
                "commit_hash": "def456",
                "commit_hash_short": "def456gh",
                "commit_message": "Test commit with captured versions",
                "commit_author": "Test Author",
                "commit_date": "2024-01-01",
            }
            mock_extract_tests.return_value = ["test_fail.py::test_example"]

            with patch.dict("os.environ", {"GITHUB_RUN_ID": "67890"}):
                data = track_packages.create_bisect_data(
                    packages, captured_versions_file=captured_file
                )

                assert data["workflow_run_id"] == "67890"
                assert data["python_version"] == "3.11.5"  # From captured file
                assert data["packages"] == {
                    "pytest": "7.4.2",
                    "numpy": "1.25.1",
                }  # From captured file
                assert data["failed_tests"] == ["test_fail.py::test_example"]
                assert data["test_status"] == "failed"
                assert data["git"]["commit_hash"] == "def456"
                assert "timestamp" in data
    finally:
        os.unlink(captured_file)


def test_format_bisect_comparison_no_previous():
    """Test formatting comparison when no previous data exists."""
    current_data = {
        "workflow_run_id": "456",
        "packages": {"pytest": "7.4.0", "hypothesis": "6.82.0"},
    }

    result = track_packages.format_bisect_comparison(current_data, None)
    assert result is None


def test_format_bisect_comparison_with_changes():
    """Test formatting comparison with package changes."""
    previous_data = {
        "workflow_run_id": "123",
        "packages": {"pytest": "7.3.0", "hypothesis": "6.82.0", "removed-pkg": "1.0.0"},
    }
    current_data = {
        "workflow_run_id": "456",
        "packages": {"pytest": "7.4.0", "hypothesis": "6.82.0", "new-pkg": "2.0.0"},
    }

    result = track_packages.format_bisect_comparison(current_data, previous_data)

    assert "Package Version Changes" in result
    assert "Last Successful Run #123 → Current Failed Run #456" in result
    assert "pytest: 7.3.0 → 7.4.0" in result
    assert "hypothesis: 6.82.0 (unchanged)" in result
    assert "removed-pkg: 1.0.0 → (not installed)" in result
    assert "new-pkg: (not installed) → 2.0.0" in result


def test_format_bisect_comparison_no_changes():
    """Test formatting comparison when no packages changed."""
    data = {
        "workflow_run_id": "456",
        "packages": {"pytest": "7.4.0", "hypothesis": "6.82.0"},
    }

    result = track_packages.format_bisect_comparison(data, data)

    assert "Package Version Changes" in result
    assert "pytest: 7.4.0 (unchanged)" in result
    assert "hypothesis: 6.82.0 (unchanged)" in result


@given(st.lists(st.text(min_size=1), min_size=1, max_size=5))
def test_get_current_package_versions_property(package_names):
    """Property test for get_current_package_versions."""
    with patch("track_packages.get_package_version") as mock_get_version:
        mock_get_version.return_value = "1.0.0"

        versions = track_packages.get_current_package_versions(package_names)

        assert len(versions) == len(package_names)
        for pkg in package_names:
            assert pkg in versions


def test_retrieve_bisect_data_from_branch_no_branch():
    """Test retrieving data when branch doesn't exist."""
    with patch("subprocess.run") as mock_run:
        # Simulate no branch found
        mock_run.return_value.stdout = ""
        mock_run.return_value.check = True

        result = track_packages.retrieve_bisect_data_from_branch("nonexistent-branch")
        assert result is None


def test_retrieve_bisect_data_from_branch_success():
    """Test successfully retrieving data from branch."""
    mock_data = {
        "workflow_run_id": "123",
        "packages": {"pytest": "7.3.0"},
    }

    with patch("subprocess.run") as mock_run:
        # Mock the sequence of git commands
        mock_run.side_effect = [
            Mock(stdout="abc123\trefs/heads/bisect-data\n", check=True),  # ls-remote
            Mock(check=True),  # fetch
            Mock(stdout=json.dumps(mock_data), check=True),  # show
        ]

        result = track_packages.retrieve_bisect_data_from_branch("bisect-data")
        assert result == mock_data


def test_generate_package_diff_link():
    """Test generating GitHub diff links for package changes."""
    # Test known package
    link = track_packages.generate_package_diff_link("numpy", "1.24.0", "1.25.0")
    assert link == "https://github.com/numpy/numpy/compare/v1.24.0...v1.25.0"

    # Test unknown package
    link = track_packages.generate_package_diff_link("unknown-package", "1.0.0", "2.0.0")
    assert link is None


def test_get_package_changes_with_github_links():
    """Test package changes include GitHub links when available."""
    previous_packages = {"numpy": "1.24.0", "unknown-pkg": "1.0.0"}
    current_packages = {"numpy": "1.25.0", "unknown-pkg": "2.0.0"}

    changes = track_packages.get_package_changes(current_packages, previous_packages)

    # Should have GitHub link for numpy
    numpy_change = next((c for c in changes if "numpy" in c), None)
    assert numpy_change is not None
    assert "https://github.com/numpy/numpy/compare/v1.24.0...v1.25.0" in numpy_change
    assert "[numpy: 1.24.0 → 1.25.0]" in numpy_change

    # Should not have GitHub link for unknown package
    unknown_change = next((c for c in changes if "unknown-pkg" in c), None)
    assert unknown_change is not None
    assert "unknown-pkg: 1.0.0 → 2.0.0" in unknown_change
    assert "https://" not in unknown_change
