"""Tests for track_packages module."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from issue_from_pytest_log_action.track_packages import (
    PACKAGE_METADATA,
    clean_version_for_tag,
    create_bisect_data,
    extract_failed_tests_from_log,
    format_bisect_comparison,
    generate_package_diff_link,
    get_git_info,
    get_package_changes,
    retrieve_last_successful_run,
)


class TestPackageMetadata:
    """Test package metadata constants."""

    def test_package_metadata_structure(self):
        """Test that package metadata has expected structure."""
        assert isinstance(PACKAGE_METADATA, dict)
        assert "numpy" in PACKAGE_METADATA
        assert "github" in PACKAGE_METADATA["numpy"]
        assert "tag_format" in PACKAGE_METADATA["numpy"]

    def test_tag_formats(self):
        """Test that tag formats are reasonable."""
        for pkg, meta in PACKAGE_METADATA.items():
            tag_format = meta["tag_format"]
            assert "{version}" in tag_format
            # Tag format should produce a valid tag
            test_version = "1.0.0"
            tag = tag_format.format(version=test_version)
            assert test_version in tag


class TestCleanVersionForTag:
    """Test version cleaning for tag generation."""

    def test_clean_stable_version(self):
        """Test cleaning stable version."""
        assert clean_version_for_tag("1.2.3") == "1.2.3"
        assert clean_version_for_tag("2.0.0") == "2.0.0"

    def test_clean_dev_version(self):
        """Test cleaning dev version."""
        assert clean_version_for_tag("1.2.3.dev0") == "1.2.3"
        assert clean_version_for_tag("2.0.0.dev123") == "2.0.0"

    def test_clean_nightly_version(self):
        """Test cleaning nightly version."""
        assert clean_version_for_tag("1.2.3.dev0+123.gabc123d") == "1.2.3"
        assert clean_version_for_tag("2.1.0.dev0+456.gdef456a") == "2.1.0"

    def test_clean_rc_version(self):
        """Test cleaning release candidate version."""
        assert clean_version_for_tag("1.2.3rc1") == "1.2.3rc1"
        assert clean_version_for_tag("2.0.0a1") == "2.0.0a1"

    def test_clean_post_version(self):
        """Test cleaning post-release version."""
        assert clean_version_for_tag("1.2.3.post1") == "1.2.3"
        assert clean_version_for_tag("2.0.0.post123") == "2.0.0"

    def test_clean_complex_version(self):
        """Test cleaning complex version with multiple suffixes."""
        assert clean_version_for_tag("1.2.3a1.dev0+abc.g123456") == "1.2.3a1"
        assert clean_version_for_tag("2.0.0rc1.post1.dev0") == "2.0.0rc1"


class TestGeneratePackageDiffLink:
    """Test package diff link generation."""

    def test_generate_diff_link_numpy(self):
        """Test diff link for numpy."""
        link = generate_package_diff_link("numpy", "1.21.0", "1.22.0")
        assert link is not None
        assert "github.com/numpy/numpy/compare" in link
        assert "v1.21.0" in link
        assert "v1.22.0" in link

    def test_generate_diff_link_with_git_commit(self):
        """Test diff link with git commit info."""
        old_git_info = {"git_revision": "abc123"}
        new_git_info = {"git_revision": "def456"}

        link = generate_package_diff_link("numpy", "1.21.0", "1.22.0", old_git_info, new_git_info)
        assert link is not None
        assert "github.com/numpy/numpy/compare" in link
        assert "abc123" in link
        assert "def456" in link

    def test_generate_diff_link_sqlalchemy_prefix(self):
        """Test diff link for SQLAlchemy with rel_ prefix."""
        link = generate_package_diff_link("sqlalchemy", "1.4.0", "1.4.1")
        assert link is not None
        assert "github.com/sqlalchemy/sqlalchemy/compare" in link
        assert "rel_1_4_0" in link
        assert "rel_1_4_1" in link

    def test_generate_diff_link_unknown_package(self):
        """Test diff link for unknown package."""
        link = generate_package_diff_link("unknown_package", "1.0.0", "2.0.0")
        assert link is None


class TestGetPackageChanges:
    """Test package change detection."""

    def test_get_package_changes_version_change(self):
        """Test detecting version changes."""
        old_packages = {"numpy": "1.21.0", "pandas": "1.3.0"}
        new_packages = {"numpy": "1.22.0", "pandas": "1.3.0"}

        changes = get_package_changes(new_packages, old_packages)
        assert len(changes) == 1
        assert "numpy: 1.21.0 → 1.22.0" in changes[0]

    def test_get_package_changes_new_package(self):
        """Test detecting new packages."""
        old_packages = {"numpy": "1.21.0"}
        new_packages = {"numpy": "1.21.0", "pandas": "1.3.0"}

        changes = get_package_changes(new_packages, old_packages)
        assert len(changes) == 1
        assert "pandas: (new) → 1.3.0" in changes[0]

    def test_get_package_changes_removed_package(self):
        """Test detecting removed packages."""
        old_packages = {"numpy": "1.21.0", "pandas": "1.3.0"}
        new_packages = {"numpy": "1.21.0"}

        changes = get_package_changes(new_packages, old_packages)
        assert len(changes) == 1
        assert "pandas: 1.3.0 → (removed)" in changes[0]

    def test_get_package_changes_no_changes(self):
        """Test when there are no changes."""
        packages = {"numpy": "1.21.0", "pandas": "1.3.0"}

        changes = get_package_changes(packages, packages)
        assert len(changes) == 0

    def test_get_package_changes_multiple_changes(self):
        """Test multiple package changes."""
        old_packages = {"numpy": "1.21.0", "pandas": "1.3.0", "scipy": "1.7.0"}
        new_packages = {"numpy": "1.22.0", "pandas": "1.3.0", "matplotlib": "3.5.0"}

        changes = get_package_changes(new_packages, old_packages)
        assert len(changes) == 3  # numpy changed, scipy removed, matplotlib added


# Note: format_package_changes function doesn't exist in the module
# Removed tests for non-existent function


class TestExtractFailedTestsFromLog:
    """Test failed test extraction from log files."""

    def test_extract_failed_tests_basic(self):
        """Test extracting failed tests from log."""
        test_data = [
            {"$report_type": "TestReport", "nodeid": "test1.py::test_func1", "outcome": "failed"},
            {"$report_type": "TestReport", "nodeid": "test2.py::test_func2", "outcome": "passed"},
            {"$report_type": "TestReport", "nodeid": "test3.py::test_func3", "outcome": "failed"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                json.dump(item, f)
                f.write("\n")
            log_file = f.name

        try:
            failed_tests = extract_failed_tests_from_log(log_file)
            assert len(failed_tests) == 2
            assert "test1.py::test_func1" in failed_tests
            assert "test3.py::test_func3" in failed_tests
            assert "test2.py::test_func2" not in failed_tests
        finally:
            Path(log_file).unlink()

    def test_extract_failed_tests_no_failures(self):
        """Test extracting when no tests failed."""
        test_data = [
            {"$report_type": "TestReport", "nodeid": "test1.py::test_func1", "outcome": "passed"},
            {"$report_type": "SessionFinish", "exitstatus": "0"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                json.dump(item, f)
                f.write("\n")
            log_file = f.name

        try:
            failed_tests = extract_failed_tests_from_log(log_file)
            assert len(failed_tests) == 0
        finally:
            Path(log_file).unlink()

    def test_extract_failed_tests_nonexistent_file(self):
        """Test extracting from non-existent file."""
        failed_tests = extract_failed_tests_from_log("nonexistent.jsonl")
        assert failed_tests == []

    def test_extract_failed_tests_invalid_json(self):
        """Test extracting from file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("invalid json line\n")
            f.write(
                '{"$report_type": "TestReport", "outcome": "failed", "nodeid": "test.py::test"}\n'
            )
            log_file = f.name

        try:
            failed_tests = extract_failed_tests_from_log(log_file)
            assert len(failed_tests) == 1
            assert "test.py::test" in failed_tests
        finally:
            Path(log_file).unlink()


class TestGetGitInfo:
    """Test git information extraction."""

    @mock.patch("subprocess.run")
    def test_get_git_info_success(self, mock_subprocess):
        """Test successful git info extraction."""

        # Mock git commands
        def mock_run(cmd, *args, **kwargs):
            result = mock.Mock()
            result.returncode = 0
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "rev-parse HEAD" in cmd_str:
                result.stdout = "abc123def456789\n"
            elif "rev-parse --short HEAD" in cmd_str:
                result.stdout = "abc123d\n"
            elif "log -1 --pretty=format:%s" in cmd_str:
                result.stdout = "Fix critical bug\n"
            elif "log -1 --pretty=format:%an <%ae>" in cmd_str:
                result.stdout = "John Doe <john@example.com>\n"
            elif "log -1 --pretty=format:%ci" in cmd_str:
                result.stdout = "2024-01-01 10:00:00 +0000\n"
            return result

        mock_subprocess.side_effect = mock_run

        git_info = get_git_info()

        assert git_info["commit_hash"] == "abc123def456789"
        assert git_info["commit_hash_short"] == "abc123de"
        assert git_info["commit_message"] == "Fix critical bug"
        assert git_info["commit_author"] == "John Doe <john@example.com>"
        assert git_info["commit_date"] == "2024-01-01 10:00:00 +0000"

    @mock.patch("subprocess.run")
    def test_get_git_info_failure(self, mock_subprocess):
        """Test git info extraction when git fails."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")

        git_info = get_git_info()

        assert git_info["commit_hash"] == "unknown"
        assert git_info["commit_hash_short"] == "unknown"
        assert git_info["commit_message"] == "unknown"
        assert git_info["commit_author"] == "unknown"
        assert git_info["commit_date"] == "unknown"


class TestCreateBisectData:
    """Test bisect data creation."""

    def test_create_bisect_data_with_failed_tests(self):
        """Test creating bisect data with failed tests."""
        packages = ["numpy", "pandas"]

        # Create test log file with failed tests
        test_log_data = [
            {"$report_type": "TestReport", "nodeid": "test1.py::test_func", "outcome": "failed"},
        ]

        # Create test captured versions
        test_versions = {
            "python_version": "3.9.0",
            "packages": {
                "numpy": {"version": "1.21.0", "git_info": None},
                "pandas": {"version": "1.3.0", "git_info": None},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as log_f:
            for item in test_log_data:
                json.dump(item, log_f)
                log_f.write("\n")
            log_path = log_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as ver_f:
            json.dump(test_versions, ver_f)
            versions_path = ver_f.name

        try:
            bisect_data = create_bisect_data(packages, log_path, versions_path)

            assert bisect_data["test_status"] == "failed"
            assert len(bisect_data["failed_tests"]) == 1
            assert "test1.py::test_func" in bisect_data["failed_tests"]
            assert "numpy" in bisect_data["packages"]
            assert "pandas" in bisect_data["packages"]
            assert bisect_data["python_version"] == "3.9.0"
            assert "timestamp" in bisect_data
            assert "git" in bisect_data

        finally:
            Path(log_path).unlink()
            Path(versions_path).unlink()

    def test_create_bisect_data_no_failed_tests(self):
        """Test creating bisect data with no failed tests."""
        packages = ["numpy"]

        test_log_data = [
            {"$report_type": "TestReport", "nodeid": "test1.py::test_func", "outcome": "passed"},
        ]

        test_versions = {
            "python_version": "3.9.0",
            "packages": {"numpy": {"version": "1.21.0", "git_info": None}},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as log_f:
            for item in test_log_data:
                json.dump(item, log_f)
                log_f.write("\n")
            log_path = log_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as ver_f:
            json.dump(test_versions, ver_f)
            versions_path = ver_f.name

        try:
            bisect_data = create_bisect_data(packages, log_path, versions_path)

            assert bisect_data["test_status"] == "passed"
            assert len(bisect_data["failed_tests"]) == 0

        finally:
            Path(log_path).unlink()
            Path(versions_path).unlink()


class TestRetrieveLastSuccessfulRun:
    """Test retrieving last successful run."""

    def test_retrieve_last_successful_run_no_files(self):
        """Test when no run files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                result = retrieve_last_successful_run("test-branch")
                assert result is None
            finally:
                os.chdir(original_cwd)

    @mock.patch("subprocess.run")
    def test_retrieve_last_successful_run_with_files(self, mock_subprocess):
        """Test finding last successful run with existing files."""

        # Mock git operations to succeed
        def mock_run(cmd, *args, **kwargs):
            result = mock.Mock()
            result.returncode = 0
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "ls-remote --heads origin" in cmd_str:
                # Return branch reference to indicate it exists
                result.stdout = "abc123\trefs/heads/test-branch\n"
            elif "fetch origin" in cmd_str:
                result.stdout = ""
            elif "ls-tree -r --name-only" in cmd_str:
                # Return list of JSON files in the branch
                result.stdout = "run_0.json\nrun_1.json\n"
            elif "show test-branch:run_0.json" in cmd_str:
                # Return failed run data
                result.stdout = json.dumps(
                    {
                        "timestamp": "2024-01-01T10:00:00Z",
                        "test_status": "failed",
                        "packages": {"numpy": {"version": "1.21.0"}},
                    }
                )
            elif "show test-branch:run_1.json" in cmd_str:
                # Return passed run data
                result.stdout = json.dumps(
                    {
                        "timestamp": "2024-01-01T09:00:00Z",
                        "test_status": "passed",
                        "packages": {"numpy": {"version": "1.20.0"}},
                    }
                )
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run
        test_runs = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "test_status": "failed",
                "packages": {"numpy": {"version": "1.21.0"}},
            },
            {
                "timestamp": "2024-01-01T09:00:00Z",
                "test_status": "passed",
                "packages": {"numpy": {"version": "1.20.0"}},
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create run files
            for i, run_data in enumerate(test_runs):
                run_file = temp_path / f"run_{i}.json"
                run_file.write_text(json.dumps(run_data))

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                result = retrieve_last_successful_run("test-branch")
                # Should find the passed run
                assert result is not None
                assert result["test_status"] == "passed"
                assert result["packages"]["numpy"]["version"] == "1.20.0"
            finally:
                os.chdir(original_cwd)


class TestFormatBisectComparison:
    """Test bisection comparison formatting."""

    def test_format_bisect_comparison_no_failed_tests(self):
        """Test formatting when there are no failed tests."""
        current_data = {
            "failed_tests": [],
            "test_status": "passed",
            "packages": {"numpy": {"version": "1.21.0"}},
        }

        result = format_bisect_comparison(current_data, None, "test-branch")
        assert result is None

    def test_format_bisect_comparison_no_previous_data(self):
        """Test formatting when there's no previous data."""
        current_data = {
            "failed_tests": ["test1.py::test_func"],
            "test_status": "failed",
            "packages": {"numpy": {"version": "1.21.0"}},
            "git": {"commit_hash": "abc123"},
        }

        result = format_bisect_comparison(current_data, None, "test-branch")
        assert result is not None
        assert "No recent successful run found for this test" in result
        assert "test1.py::test_func" in result

    @mock.patch("issue_from_pytest_log_action.track_packages.find_last_successful_run_for_tests")
    def test_format_bisect_comparison_with_changes(self, mock_find_success):
        """Test formatting comparison with package changes."""
        mock_find_success.return_value = {
            "test1.py::test_func": {
                "packages": {"numpy": {"version": "1.20.0", "git_info": None}},
                "git": {"commit_hash": "def456"},
                "workflow_run_id": "12345",
                "timestamp": "2024-01-01T10:00:00Z",
            }
        }

        current_data = {
            "failed_tests": ["test1.py::test_func"],
            "test_status": "failed",
            "packages": {"numpy": {"version": "1.21.0", "git_info": None}},
            "git": {"commit_hash": "abc123"},
        }

        previous_data = {
            "test_status": "passed",
            "packages": {"numpy": {"version": "1.20.0"}},
        }

        result = format_bisect_comparison(current_data, previous_data, "test-branch")
        assert result is not None
        assert "test1.py::test_func" in result
        assert "1.20.0" in result
        assert "1.21.0" in result
