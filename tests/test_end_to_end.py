"""End-to-end integration tests for the GitHub Action workflow.

These tests verify that the complete action workflow functions correctly
with realistic test scenarios and data.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest


class TestActionWorkflow:
    """Test the complete GitHub Action workflow end-to-end."""

    def create_realistic_pytest_log(self, temp_dir: Path, scenario: str) -> Path:
        """Create realistic pytest log files for different test scenarios."""
        scenarios = {
            "numpy_import_failure": [
                {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
                {
                    "$report_type": "CollectReport",
                    "nodeid": "",
                    "outcome": "failed",
                    "result": [],
                    "longrepr": "ModuleNotFoundError: No module named 'numpy'",
                },
            ],
            "mixed_failures": [
                {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
                {
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_data_processing.py::test_numpy_operations",
                    "outcome": "failed",
                    "location": ("tests/test_data_processing.py", 45, "test_numpy_operations"),
                    "keywords": {"parametrize": True},
                    "when": "call",
                    "longrepr": "AssertionError: Arrays are not equal\\nExpected: [1, 2, 3]\\nActual: [1, 2, 4]",
                },
                {
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_analysis.py::test_pandas_groupby[method-mean]",
                    "outcome": "failed",
                    "location": ("tests/test_analysis.py", 23, "test_pandas_groupby"),
                    "keywords": {"parametrize": True},
                    "when": "call",
                    "longrepr": "KeyError: 'column_name'",
                },
                {
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_plotting.py::test_visualization",
                    "outcome": "passed",
                    "location": ("tests/test_plotting.py", 67, "test_visualization"),
                    "keywords": {},
                    "when": "call",
                    "longrepr": None,
                },
                {"$report_type": "SessionFinish", "exitstatus": "1"},
            ],
            "all_pass": [
                {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
                {
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_basic.py::test_simple",
                    "outcome": "passed",
                    "location": ("tests/test_basic.py", 10, "test_simple"),
                    "keywords": {},
                    "when": "call",
                    "longrepr": None,
                },
                {"$report_type": "SessionFinish", "exitstatus": "0"},
            ],
        }

        log_file = temp_dir / "pytest-log.jsonl"
        with log_file.open("w") as f:
            for record in scenarios[scenario]:
                json.dump(record, f)
                f.write("\n")

        return log_file

    def create_realistic_package_versions(self, temp_dir: Path, scenario: str) -> Path:
        """Create realistic package version files for different scenarios."""
        scenarios = {
            "scientific_stack_update": {
                "python_version": "3.11.0",
                "python_executable": "/opt/miniconda3/bin/python",
                "packages": {
                    "numpy": {
                        "version": "1.26.0.dev0+1234.g5678abc",
                        "git_info": {"git_revision": "5678abc", "source": "version_string"}
                    },
                    "pandas": {
                        "version": "2.2.0rc1",
                        "git_info": None
                    },
                    "xarray": {
                        "version": "2024.1.0",
                        "git_info": None
                    },
                    "zarr": {
                        "version": "2.16.0.dev0+123.gdef456",
                        "git_info": {"git_revision": "def456", "source": "version_string"}
                    },
                },
                "capture_method": "importlib.metadata"
            },
            "stable_versions": {
                "python_version": "3.11.0",
                "python_executable": "/usr/bin/python3",
                "packages": {
                    "numpy": {"version": "1.25.0", "git_info": None},
                    "pandas": {"version": "2.1.0", "git_info": None},
                    "xarray": {"version": "2023.8.0", "git_info": None},
                },
                "capture_method": "importlib.metadata"
            },
        }

        versions_file = temp_dir / "captured-package-versions.json"
        with versions_file.open("w") as f:
            json.dump(scenarios[scenario], f, indent=2)

        return versions_file

    def test_complete_failure_workflow(self):
        """Test the complete workflow when tests fail with package tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create realistic test scenario files
            log_file = self.create_realistic_pytest_log(temp_path, "mixed_failures")
            versions_file = self.create_realistic_package_versions(temp_path, "scientific_stack_update")

            # Simulate running the main workflow commands
            env = os.environ.copy()
            env.update({
                "TRACK_PACKAGES": "numpy,pandas,xarray,zarr",
                "GITHUB_WORKSPACE": str(temp_path),
            })

            # Change to temp directory for the test
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)

                # Test log parsing step
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.parse_logs",
                    str(log_file)
                ], env=env, capture_output=True, text=True)

                assert result.returncode == 0
                assert Path("pytest-logs.txt").exists()

                # Verify log parsing output
                log_content = Path("pytest-logs.txt").read_text()
                assert "test_numpy_operations" in log_content
                assert "test_pandas_groupby" in log_content
                assert "AssertionError" in log_content

                # Test bisection data creation
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.simple_bisect",
                    "--packages", "numpy,pandas,xarray,zarr",
                    "--log-path", str(log_file),
                    "--captured-versions", str(versions_file),
                    "--branch", "test-bisect-branch",
                    "--store-run"
                ], env=env, capture_output=True, text=True)

                assert result.returncode == 0

                # Check that run file was created
                run_files = list(Path(".").glob("run_*.json"))
                assert len(run_files) == 1

                # Verify run file content
                run_data = json.loads(run_files[0].read_text())
                assert run_data["test_status"] == "failed"
                assert len(run_data["failed_tests"]) == 2
                assert "tests/test_data_processing.py::test_numpy_operations" in run_data["failed_tests"]
                assert "tests/test_analysis.py::test_pandas_groupby[method-mean]" in run_data["failed_tests"]
                assert "numpy" in run_data["packages"]
                assert "pandas" in run_data["packages"]

            finally:
                os.chdir(original_cwd)

    def test_package_tracking_integration(self):
        """Test package version tracking integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            env["TRACK_PACKAGES"] = "pytest,setuptools"  # Use packages we know exist

            # Test package capture
            result = subprocess.run([
                sys.executable, "-m", "issue_from_pytest_log_action.capture_versions"
            ], env=env, cwd=temp_dir, capture_output=True, text=True)

            assert result.returncode == 0

            # Verify output file
            output_file = Path(temp_dir) / "captured-package-versions.json"
            assert output_file.exists()

            data = json.loads(output_file.read_text())
            assert "packages" in data
            assert "python_version" in data
            assert "pytest" in data["packages"]
            assert "setuptools" in data["packages"]

    def test_run_metadata_extraction(self):
        """Test the run metadata extraction CLI."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a test run file
            run_data = {
                "test_status": "failed",
                "failed_tests": ["test_a.py::test_1", "test_b.py::test_2"],
                "timestamp": "2024-01-01T10:00:00Z",
                "packages": {"numpy": {"version": "1.25.0"}}
            }

            run_file = temp_path / "run_12345.json"
            with run_file.open("w") as f:
                json.dump(run_data, f)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)

                # Test status extraction
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.extract_run_metadata",
                    "test_status"
                ], capture_output=True, text=True)

                assert result.returncode == 0
                assert result.stdout.strip() == "failed"

                # Test failed count extraction
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.extract_run_metadata",
                    "failed_count"
                ], capture_output=True, text=True)

                assert result.returncode == 0
                assert result.stdout.strip() == "2"

            finally:
                os.chdir(original_cwd)

    def test_successful_run_workflow(self):
        """Test workflow when all tests pass."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create passing test scenario
            log_file = self.create_realistic_pytest_log(temp_path, "all_pass")
            versions_file = self.create_realistic_package_versions(temp_path, "stable_versions")

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)

                # Test log parsing
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.parse_logs",
                    str(log_file)
                ], capture_output=True, text=True)

                assert result.returncode == 0

                # For passing tests, the action should still work but produce different output
                log_content = Path("pytest-logs.txt").read_text()
                # The exact content will depend on implementation, but it should not crash

            finally:
                os.chdir(original_cwd)

    def test_error_handling(self):
        """Test error handling for various failure modes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Test with missing log file
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.parse_logs",
                    "nonexistent.jsonl"
                ], capture_output=True, text=True)

                # Should handle missing files gracefully
                assert result.returncode != 0  # Expected to fail

                # Test with invalid JSON
                bad_log = Path("bad.jsonl")
                bad_log.write_text("invalid json content")

                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.parse_logs",
                    str(bad_log)
                ], capture_output=True, text=True)

                # Should handle invalid JSON gracefully
                assert result.returncode != 0  # Expected to fail

            finally:
                os.chdir(original_cwd)


class TestRealisticScenarios:
    """Test realistic scientific computing CI/CD scenarios."""

    def test_nightly_wheel_scenario(self):
        """Test scenario with nightly wheels causing failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create scenario: numpy nightly introduced breaking change
            test_data = [
                {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
                {
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_numerical.py::test_array_ops",
                    "outcome": "failed",
                    "location": ("tests/test_numerical.py", 15, "test_array_ops"),
                    "keywords": {},
                    "when": "call",
                    "longrepr": "AttributeError: module 'numpy' has no attribute 'array_function_like'",
                },
                {"$report_type": "SessionFinish", "exitstatus": "1"},
            ]

            log_file = temp_path / "pytest-log.jsonl"
            with log_file.open("w") as f:
                for record in test_data:
                    json.dump(record, f)
                    f.write("\n")

            # Package versions showing nightly numpy
            package_data = {
                "python_version": "3.11.0",
                "packages": {
                    "numpy": {
                        "version": "1.26.0.dev0+1598.g1234abc",
                        "git_info": {"git_revision": "1234abc", "source": "version_string"}
                    },
                    "pandas": {"version": "2.1.0", "git_info": None},
                },
                "capture_method": "importlib.metadata"
            }

            versions_file = temp_path / "versions.json"
            with versions_file.open("w") as f:
                json.dump(package_data, f)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)

                # Test the complete pipeline
                result = subprocess.run([
                    sys.executable, "-m", "issue_from_pytest_log_action.simple_bisect",
                    "--packages", "numpy,pandas",
                    "--log-path", str(log_file),
                    "--captured-versions", str(versions_file),
                    "--branch", "test-nightly-scenario",
                    "--store-run"
                ], capture_output=True, text=True)

                assert result.returncode == 0

                # Verify the run data captures the nightly version correctly
                run_files = list(Path(".").glob("run_*.json"))
                assert len(run_files) == 1

                run_data = json.loads(run_files[0].read_text())
                assert run_data["test_status"] == "failed"
                numpy_info = run_data["packages"]["numpy"]
                assert "1.26.0.dev0" in numpy_info["version"]
                assert numpy_info["git_info"]["git_revision"] == "1234abc"

            finally:
                os.chdir(original_cwd)

    def test_version_pinning_scenario(self):
        """Test scenario where version pinning resolves issues."""
        # This would be useful for testing the bisection feature
        # when we have historical data showing when a test last passed
        pass


class TestPerformance:
    """Test performance with large datasets."""

    def test_large_log_file_handling(self):
        """Test handling of large pytest log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a large log file (simulate 1000 tests)
            log_file = temp_path / "large-pytest-log.jsonl"

            with log_file.open("w") as f:
                # Session start
                json.dump({"$report_type": "SessionStart", "pytest_version": "7.4.0"}, f)
                f.write("\n")

                # Generate many test results
                for i in range(1000):
                    test_result = {
                        "$report_type": "TestReport",
                        "nodeid": f"tests/test_module_{i % 10}.py::test_function_{i}",
                        "outcome": "failed" if i % 50 == 0 else "passed",  # 2% failure rate
                        "location": (f"tests/test_module_{i % 10}.py", 10 + i % 100, f"test_function_{i}"),
                        "keywords": {},
                        "when": "call",
                        "longrepr": f"AssertionError: Test {i} failed" if i % 50 == 0 else None,
                    }

                    json.dump(test_result, f)
                    f.write("\n")

                # Session finish
                json.dump({"$report_type": "SessionFinish", "exitstatus": "1"}, f)
                f.write("\n")

            start_time = time.time()

            # Test parsing performance
            result = subprocess.run([
                sys.executable, "-m", "issue_from_pytest_log_action.parse_logs",
                str(log_file)
            ], cwd=temp_path, capture_output=True, text=True)

            processing_time = time.time() - start_time

            assert result.returncode == 0
            assert processing_time < 5.0  # Should process 1000 tests in under 5 seconds

            # Verify output
            assert Path(temp_path / "pytest-logs.txt").exists()
            log_content = Path(temp_path / "pytest-logs.txt").read_text()

            # Should contain information about the failed tests
            assert "test_function_" in log_content

    def test_many_packages_performance(self):
        """Test performance with many tracked packages."""
        # Test with a scenario tracking many packages
        env = os.environ.copy()
        env["TRACK_PACKAGES"] = "all"  # Track all installed packages

        start_time = time.time()

        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run([
                sys.executable, "-m", "issue_from_pytest_log_action.capture_versions"
            ], env=env, cwd=temp_dir, capture_output=True, text=True)

            processing_time = time.time() - start_time

            assert result.returncode == 0
            assert processing_time < 10.0  # Should complete in reasonable time

            # Check that many packages were captured
            output_file = Path(temp_dir) / "captured-package-versions.json"
            data = json.loads(output_file.read_text())

            # Should have captured multiple packages
            assert len(data["packages"]) >= 5  # At least a few packages should be installed


@pytest.mark.integration
class TestGitHubActionEnvironment:
    """Test components that simulate GitHub Actions environment."""

    def test_environment_variable_handling(self):
        """Test handling of GitHub Actions environment variables."""
        env_vars = {
            "GITHUB_WORKSPACE": "/github/workspace",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_SHA": "abc123def456",
        }

        # These tests would verify that the action handles GitHub environment
        # variables correctly, but we can't easily test this without actual
        # GitHub Actions infrastructure
        pass

    def test_github_api_integration(self):
        """Test GitHub API integration (would require mocking)."""
        # This would test the JavaScript portion that creates issues
        # For now, we can at least verify the data format is correct
        pass