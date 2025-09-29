"""Tests for extract_run_metadata module."""

import json
import pathlib
import tempfile

import pytest

from issue_from_pytest_log_action.extract_run_metadata import (
    extract_failed_test_count,
    extract_test_status,
    find_latest_run_file,
    load_run_data,
    main,
)


@pytest.fixture
def sample_run_data():
    """Sample run data for testing."""
    return {
        "test_status": "failed",
        "failed_tests": ["test1", "test2", "test3"],
        "packages": {"numpy": "1.21.0"},
        "timestamp": "2024-01-01T10:00:00Z",
    }


@pytest.fixture
def temp_run_file(sample_run_data):
    """Create a temporary run file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix="run_", delete=False) as f:
        json.dump(sample_run_data, f)
        temp_file = pathlib.Path(f.name)

    yield temp_file

    # Cleanup
    if temp_file.exists():
        temp_file.unlink()


def test_load_run_data(temp_run_file, sample_run_data):
    """Test loading run data from a JSON file."""
    data = load_run_data(temp_run_file)
    assert data == sample_run_data


def test_load_run_data_invalid_file():
    """Test loading run data from a non-existent file."""
    with pytest.raises(ValueError, match="Failed to load run data"):
        load_run_data(pathlib.Path("nonexistent.json"))


def test_extract_test_status(sample_run_data):
    """Test extracting test status."""
    assert extract_test_status(sample_run_data) == "failed"
    assert extract_test_status({}) == "unknown"


def test_extract_failed_test_count(sample_run_data):
    """Test extracting failed test count."""
    assert extract_failed_test_count(sample_run_data) == 3
    assert extract_failed_test_count({}) == 0
    assert extract_failed_test_count({"failed_tests": []}) == 0


def test_find_latest_run_file():
    """Test finding the latest run file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)

        # Create some run files with different timestamps
        run_file1 = temp_path / "run_123.json"
        run_file2 = temp_path / "run_456.json"

        run_file1.write_text('{"test_status": "passed"}')
        run_file2.write_text('{"test_status": "failed"}')

        # Make run_file2 newer by touching it
        import time

        time.sleep(0.01)  # Small delay to ensure different timestamps
        run_file2.touch()

        # Change to the temp directory
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            latest = find_latest_run_file()
            assert latest.name == "run_456.json"
        finally:
            os.chdir(original_cwd)


def test_find_latest_run_file_no_files():
    """Test finding run files when none exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            with pytest.raises(FileNotFoundError, match="No run_.*json files found"):
                find_latest_run_file()
        finally:
            os.chdir(original_cwd)


def test_main_test_status(temp_run_file, capsys):
    """Test main function extracting test status."""
    main(["test_status", "--file", str(temp_run_file)])
    captured = capsys.readouterr()
    assert captured.out.strip() == "failed"


def test_main_failed_count(temp_run_file, capsys):
    """Test main function extracting failed test count."""
    main(["failed_count", "--file", str(temp_run_file)])
    captured = capsys.readouterr()
    assert captured.out.strip() == "3"


def test_main_invalid_file(capsys):
    """Test main function with invalid file."""
    with pytest.raises(SystemExit):
        main(["test_status", "--file", "nonexistent.json"])

    captured = capsys.readouterr()
    assert "Error:" in captured.err


def test_main_find_latest():
    """Test main function finding latest file automatically."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        run_file = temp_path / "run_123.json"
        run_file.write_text('{"test_status": "passed", "failed_tests": ["test1"]}')

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)

            # Test with capsys
            import sys
            from io import StringIO

            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()

            try:
                main(["test_status"])
                output = captured_output.getvalue()
                assert output.strip() == "passed"
            finally:
                sys.stdout = old_stdout

        finally:
            os.chdir(original_cwd)
