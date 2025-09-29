"""Tests for simple_bisect module."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from issue_from_pytest_log_action.simple_bisect import main


class TestSimpleBisectMain:
    """Test simple_bisect main function."""

    def test_main_store_run_success(self):
        """Test storing a run successfully."""
        # Create test log file
        test_log_data = [
            {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
            {
                "$report_type": "TestReport",
                "nodeid": "test_example.py::test_failing",
                "outcome": "failed",
                "location": ("test_example.py", 10, "test_failing"),
                "keywords": {},
                "when": "call",
                "longrepr": "Test failed",
            },
            {"$report_type": "SessionFinish", "exitstatus": "1"},
        ]

        # Create test captured versions file
        test_versions = {
            "python_version": "3.9.0",
            "packages": {
                "numpy": {"version": "1.21.0", "git_info": {"revision": "abc123"}},
                "pandas": {"version": "1.3.0", "git_info": None},
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Write test files
            log_file = temp_path / "test.jsonl"
            versions_file = temp_path / "versions.json"

            with log_file.open("w") as f:
                for item in test_log_data:
                    json.dump(item, f)
                    f.write("\n")

            with versions_file.open("w") as f:
                json.dump(test_versions, f)

            # Test storing run
            args = [
                "--packages",
                "numpy,pandas",
                "--log-path",
                str(log_file),
                "--captured-versions",
                str(versions_file),
                "--branch",
                "test-branch",
                "--store-run",
            ]

            # Change to temp directory to capture output files
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                main(args)

                # Check that a run file was created
                run_files = list(Path(".").glob("run_*.json"))
                assert len(run_files) == 1

                # Verify run file content
                run_data = json.loads(run_files[0].read_text())
                assert run_data["test_status"] == "failed"
                assert len(run_data["failed_tests"]) == 1
                assert run_data["failed_tests"][0] == "test_example.py::test_failing"
                assert "numpy" in run_data["packages"]
                assert "pandas" in run_data["packages"]

            finally:
                os.chdir(original_cwd)

    def test_main_store_run_passed_tests(self):
        """Test storing a run with passed tests."""
        test_log_data = [
            {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
            {
                "$report_type": "TestReport",
                "nodeid": "test_example.py::test_passing",
                "outcome": "passed",
            },
            {"$report_type": "SessionFinish", "exitstatus": "0"},
        ]

        test_versions = {
            "python_version": "3.9.0",
            "packages": {"numpy": {"version": "1.21.0", "git_info": None}},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "test.jsonl"
            versions_file = temp_path / "versions.json"

            with log_file.open("w") as f:
                for item in test_log_data:
                    json.dump(item, f)
                    f.write("\n")

            with versions_file.open("w") as f:
                json.dump(test_versions, f)

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                main(
                    [
                        "--packages",
                        "numpy",
                        "--log-path",
                        str(log_file),
                        "--captured-versions",
                        str(versions_file),
                        "--branch",
                        "test-branch",
                        "--store-run",
                    ]
                )

                run_files = list(Path(".").glob("run_*.json"))
                assert len(run_files) == 1

                run_data = json.loads(run_files[0].read_text())
                assert run_data["test_status"] == "passed"
                assert len(run_data["failed_tests"]) == 0

            finally:
                os.chdir(original_cwd)

    def test_main_generate_comparison_no_data(self):
        """Test generating comparison with no historical data."""
        test_log_data = [{"$report_type": "SessionFinish", "exitstatus": "1"}]
        test_versions = {"python_version": "3.9.0", "packages": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "test.jsonl"
            versions_file = temp_path / "versions.json"

            with log_file.open("w") as f:
                for item in test_log_data:
                    json.dump(item, f)
                    f.write("\n")

            with versions_file.open("w") as f:
                json.dump(test_versions, f)

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                main(
                    [
                        "--packages",
                        "numpy",
                        "--log-path",
                        str(log_file),
                        "--captured-versions",
                        str(versions_file),
                        "--branch",
                        "test-branch",
                        "--generate-comparison",
                    ]
                )

                # Check that bisect-comparison.txt was NOT created (no failed tests)
                comparison_file = Path("bisect-comparison.txt")
                assert not comparison_file.exists()

            finally:
                os.chdir(original_cwd)

    @mock.patch("subprocess.run")
    def test_main_generate_comparison_with_data(self, mock_subprocess):
        """Test generating comparison with historical data."""
        # Mock git log to return fake historical data
        mock_result = mock.Mock()
        mock_result.stdout = json.dumps(
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "test_status": "passed",
                "packages": {"numpy": {"version": "1.20.0", "git_info": None}},
                "failed_tests": [],
            }
        )
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        test_log_data = [
            {
                "$report_type": "TestReport",
                "nodeid": "test_example.py::test_failing",
                "outcome": "failed",
                "location": ("test_example.py", 10, "test_failing"),
                "keywords": {},
                "when": "call",
                "longrepr": "Test failed",
            },
            {"$report_type": "SessionFinish", "exitstatus": "1"},
        ]
        test_versions = {
            "python_version": "3.9.0",
            "packages": {"numpy": {"version": "1.21.0", "git_info": None}},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_file = temp_path / "test.jsonl"
            versions_file = temp_path / "versions.json"

            with log_file.open("w") as f:
                for item in test_log_data:
                    json.dump(item, f)
                    f.write("\n")

            with versions_file.open("w") as f:
                json.dump(test_versions, f)

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                main(
                    [
                        "--packages",
                        "numpy",
                        "--log-path",
                        str(log_file),
                        "--captured-versions",
                        str(versions_file),
                        "--branch",
                        "test-branch",
                        "--generate-comparison",
                    ]
                )

                comparison_file = Path("bisect-comparison.txt")
                assert comparison_file.exists()

                content = comparison_file.read_text()
                # Should contain comparison information
                assert content.strip() != ""

            finally:
                os.chdir(original_cwd)

    def test_main_invalid_args(self):
        """Test main with invalid arguments."""
        with pytest.raises(SystemExit):
            main(["--invalid-arg"])

    def test_main_missing_required_args(self):
        """Test main with missing required arguments."""
        with pytest.raises(SystemExit):
            main(["--store-run"])

    def test_main_missing_files(self):
        """Test main with missing input files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                # This should fail gracefully - the specific behavior depends on implementation
                # At minimum it shouldn't crash with unhandled exceptions
                try:
                    main(
                        [
                            "--packages",
                            "numpy",
                            "--log-path",
                            "nonexistent.jsonl",
                            "--captured-versions",
                            "nonexistent.json",
                            "--branch",
                            "test-branch",
                            "--store-run",
                        ]
                    )
                except (FileNotFoundError, SystemExit):
                    # Expected behavior when files don't exist
                    pass
            finally:
                os.chdir(original_cwd)
