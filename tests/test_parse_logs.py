"""Tests for parse_logs module."""

import json
import pathlib
import tempfile
import textwrap

import pytest

from issue_from_pytest_log_action.parse_logs import (
    CollectionError,
    PreformattedReport,
    SessionFinish,
    SessionStart,
    compressed_report,
    format_collection_error,
    format_report,
    format_summary,
    include_bisection_info,
    main,
    merge_variants,
    parse_nodeid,
    parse_record,
    strip_ansi,
    summarize,
    truncate,
)


class TestStripAnsi:
    """Test ANSI escape sequence stripping."""

    def test_strip_ansi_no_sequences(self):
        """Test text without ANSI sequences."""
        text = "Normal text"
        assert strip_ansi(text) == "Normal text"

    def test_strip_ansi_with_color_sequences(self):
        """Test stripping color sequences."""
        text = "\x1b[31mRed text\x1b[0m"
        assert strip_ansi(text) == "Red text"

    def test_strip_ansi_with_cursor_sequences(self):
        """Test stripping cursor movement sequences."""
        text = "\x1b[2J\x1b[HClear screen"
        assert strip_ansi(text) == "Clear screen"

    def test_strip_ansi_complex_sequences(self):
        """Test stripping complex ANSI sequences."""
        text = "\x1b[1;31;40mBold red on black\x1b[0m"
        assert strip_ansi(text) == "Bold red on black"


class TestSessionStart:
    """Test SessionStart dataclass."""

    def test_session_start_creation(self):
        """Test creating SessionStart from JSON."""
        data = {"$report_type": "SessionStart", "pytest_version": "7.4.0"}
        session = SessionStart._from_json(data)
        assert session.pytest_version == "7.4.0"
        assert session.outcome == "status"

    def test_session_start_with_custom_outcome(self):
        """Test SessionStart with custom outcome."""
        data = {"$report_type": "SessionStart", "pytest_version": "7.4.0", "outcome": "custom"}
        session = SessionStart._from_json(data)
        assert session.pytest_version == "7.4.0"
        assert session.outcome == "custom"


class TestSessionFinish:
    """Test SessionFinish dataclass."""

    def test_session_finish_creation(self):
        """Test creating SessionFinish from JSON."""
        data = {"$report_type": "SessionFinish", "exitstatus": "0"}
        session = SessionFinish._from_json(data)
        assert session.exitstatus == "0"
        assert session.outcome == "status"


class TestPreformattedReport:
    """Test PreformattedReport dataclass."""

    def test_preformatted_report_creation(self):
        """Test creating PreformattedReport."""
        report = PreformattedReport(
            filepath="test.py", name="test_func", variant="param1", message="Test failed"
        )
        assert report.filepath == "test.py"
        assert report.name == "test_func"
        assert report.variant == "param1"
        assert report.message == "Test failed"

    def test_preformatted_report_strips_ansi(self):
        """Test that PreformattedReport strips ANSI sequences."""
        report = PreformattedReport(
            filepath="test.py",
            name="test_func",
            variant=None,
            message="\x1b[31mRed error message\x1b[0m",
        )
        assert report.message == "Red error message"


class TestParseNodeid:
    """Test nodeid parsing."""

    def test_parse_nodeid_simple(self):
        """Test parsing simple nodeid."""
        result = parse_nodeid("test_file.py::test_function")
        assert result == {"filepath": "test_file.py", "name": "test_function", "variant": None}

    def test_parse_nodeid_with_variant(self):
        """Test parsing nodeid with variant."""
        result = parse_nodeid("test_file.py::test_function[param1]")
        assert result == {"filepath": "test_file.py", "name": "test_function", "variant": "param1"}

    def test_parse_nodeid_complex_variant(self):
        """Test parsing nodeid with complex variant."""
        result = parse_nodeid("test_file.py::test_function[param1-value2]")
        assert result == {
            "filepath": "test_file.py",
            "name": "test_function",
            "variant": "param1-value2",
        }

    def test_parse_nodeid_invalid(self):
        """Test parsing invalid nodeid."""
        with pytest.raises(ValueError, match="unknown test id"):
            parse_nodeid("invalid_nodeid")


class TestParseRecord:
    """Test record parsing."""

    def test_parse_record_session_start(self):
        """Test parsing SessionStart record."""
        record = {"$report_type": "SessionStart", "pytest_version": "7.4.0"}
        result = parse_record(record)
        assert isinstance(result, SessionStart)
        assert result.pytest_version == "7.4.0"

    def test_parse_record_session_finish(self):
        """Test parsing SessionFinish record."""
        record = {"$report_type": "SessionFinish", "exitstatus": "0"}
        result = parse_record(record)
        assert isinstance(result, SessionFinish)
        assert result.exitstatus == "0"

    def test_parse_record_unknown_type(self):
        """Test parsing unknown record type."""
        record = {"$report_type": "UnknownType", "data": "value"}
        with pytest.raises(ValueError, match="unknown report type"):
            parse_record(record)


class TestFormatSummary:
    """Test summary formatting."""

    def test_format_summary_with_variant(self):
        """Test formatting summary with variant."""
        report = PreformattedReport(
            filepath="test.py", name="test_func", variant="param1", message="Failed"
        )
        result = format_summary(report)
        assert result == "test.py::test_func[param1]: Failed"

    def test_format_summary_without_variant(self):
        """Test formatting summary without variant."""
        report = PreformattedReport(
            filepath="test.py", name="test_func", variant=None, message="Failed"
        )
        result = format_summary(report)
        assert result == "test.py::test_func: Failed"

    def test_format_summary_no_name(self):
        """Test formatting summary without function name."""
        report = PreformattedReport(filepath="test.py", name=None, variant=None, message="Failed")
        result = format_summary(report)
        assert result == "test.py: Failed"


class TestFormatReport:
    """Test report formatting."""

    def test_format_report_basic(self):
        """Test basic report formatting."""
        summaries = ["test1.py::test_func: Failed", "test2.py::test_other: Error"]
        result = format_report(summaries, "3.9")

        expected = textwrap.dedent("""\
        <details><summary>Python 3.9 Test Summary</summary>

        ```
        test1.py::test_func: Failed
        test2.py::test_other: Error
        ```

        </details>
        """)
        assert result == expected

    def test_format_report_empty(self):
        """Test report formatting with no summaries."""
        result = format_report([], "3.9")
        expected = textwrap.dedent("""\
        <details><summary>Python 3.9 Test Summary</summary>

        ```

        ```

        </details>
        """)
        assert result == expected


class TestMergeVariants:
    """Test variant merging functionality."""

    def test_merge_variants_single_variant(self):
        """Test merging with single variant."""
        reports = [
            PreformattedReport(
                filepath="test.py", name="test_func", variant="param1", message="Failed"
            )
        ]
        result = merge_variants(reports, max_chars=1000, py_version="3.9")
        assert "test.py::test_func[param1]: Failed" in result

    def test_merge_variants_multiple_variants(self):
        """Test merging multiple variants of same test."""
        reports = [
            PreformattedReport(
                filepath="test.py", name="test_func", variant="param1", message="Failed"
            ),
            PreformattedReport(
                filepath="test.py", name="test_func", variant="param2", message="Failed"
            ),
        ]
        result = merge_variants(reports, max_chars=1000, py_version="3.9")
        assert "test.py::test_func[2 failing variants]: Failed" in result

    def test_merge_variants_no_variant(self):
        """Test merging with no variants."""
        reports = [
            PreformattedReport(filepath="test.py", name="test_func", variant=None, message="Failed")
        ]
        result = merge_variants(reports, max_chars=1000, py_version="3.9")
        assert "test.py::test_func: Failed" in result


class TestTruncate:
    """Test truncation functionality."""

    def test_truncate_fits_all(self):
        """Test truncation when all reports fit."""
        reports = [
            PreformattedReport(
                filepath="test.py", name="test_func1", variant=None, message="Failed"
            ),
            PreformattedReport(
                filepath="test.py", name="test_func2", variant=None, message="Failed"
            ),
        ]
        result = truncate(reports, max_chars=10000, py_version="3.9")
        assert result is not None
        # truncate function always tries fractions, so check for the actual behavior
        # With 2 reports and 95% fraction, we get 1 report + summary
        assert "test.py::test_func1: Failed" in result
        assert "+ 1 failing tests" in result

    def test_truncate_needs_truncation(self):
        """Test truncation when reports need to be truncated."""
        reports = [
            PreformattedReport(
                filepath="test.py", name=f"test_func{i}", variant=None, message="Failed"
            )
            for i in range(100)
        ]
        result = truncate(reports, max_chars=500, py_version="3.9")
        assert result is not None
        assert "failing tests" in result

    def test_truncate_too_large(self):
        """Test truncation when even smallest result is too large."""
        reports = [
            PreformattedReport(
                filepath="very_long_filename_that_exceeds_limits.py",
                name="very_long_function_name_that_also_exceeds_limits",
                variant=None,
                message="Very long error message that makes everything too large for limits",
            )
            for i in range(10)
        ]
        result = truncate(reports, max_chars=50, py_version="3.9")
        assert result is None


class TestSummarize:
    """Test summarize functionality."""

    def test_summarize_multiple_reports(self):
        """Test summarizing multiple reports."""
        reports = [
            PreformattedReport(
                filepath="test.py", name="test_func1", variant=None, message="Failed"
            ),
            PreformattedReport(
                filepath="test.py", name="test_func2", variant=None, message="Failed"
            ),
            PreformattedReport(
                filepath="test.py", name="test_func3", variant=None, message="Failed"
            ),
        ]
        result = summarize(reports, py_version="3.9")
        assert "3 failing tests" in result

    def test_summarize_single_report(self):
        """Test summarizing single report."""
        reports = [
            PreformattedReport(filepath="test.py", name="test_func", variant=None, message="Failed")
        ]
        result = summarize(reports, py_version="3.9")
        assert "1 failing tests" in result


class TestCompressedReport:
    """Test compressed report functionality."""

    def test_compressed_report_fits_all(self):
        """Test compressed report when all fits."""
        reports = [
            PreformattedReport(filepath="test.py", name="test_func", variant=None, message="Failed")
        ]
        result = compressed_report(reports, max_chars=10000, py_version="3.9")
        assert "test.py::test_func: Failed" in result

    def test_compressed_report_needs_compression(self):
        """Test compressed report with compression needed."""
        reports = [
            PreformattedReport(
                filepath="test.py", name=f"test_func{i}", variant=None, message="Failed"
            )
            for i in range(100)
        ]
        result = compressed_report(reports, max_chars=500, py_version="3.9")
        assert result is not None
        assert "failing tests" in result


class TestFormatCollectionError:
    """Test collection error formatting."""

    def test_format_collection_error(self):
        """Test formatting collection error."""
        error = CollectionError(
            name="test collection session", repr_="ImportError: No module named 'missing'"
        )
        result = format_collection_error(error, py_version="3.9")

        assert "Python 3.9 Test Summary" in result
        assert "test collection session failed:" in result
        assert "ImportError: No module named 'missing'" in result


class TestIncludeBisectionInfo:
    """Test bisection info inclusion."""

    def test_include_bisection_info_no_file(self):
        """Test when bisection file doesn't exist."""
        message = "Original message"
        result = include_bisection_info(message, bisect_file="nonexistent.txt")
        assert result == "Original message"

    def test_include_bisection_info_with_file(self):
        """Test when bisection file exists."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Bisection info: Package X changed from v1.0 to v2.0")
            bisect_file = f.name

        try:
            message = "Original message"
            result = include_bisection_info(message, bisect_file=bisect_file)
            expected = "Bisection info: Package X changed from v1.0 to v2.0\nOriginal message"
            assert result == expected
        finally:
            pathlib.Path(bisect_file).unlink()

    def test_include_bisection_info_empty_file(self):
        """Test when bisection file is empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            bisect_file = f.name

        try:
            message = "Original message"
            result = include_bisection_info(message, bisect_file=bisect_file)
            assert result == "Original message"
        finally:
            pathlib.Path(bisect_file).unlink()


class TestMain:
    """Test main function."""

    def test_main_with_test_data(self):
        """Test main function with test data."""
        # Create test log data with proper TestReport fields
        test_data = [
            {"$report_type": "SessionStart", "pytest_version": "7.4.0"},
            {
                "$report_type": "TestReport",
                "nodeid": "test_example.py::test_failing",
                "outcome": "failed",
                "location": ("test_example.py", 10, "test_failing"),
                "keywords": {},
                "when": "call",
                "longrepr": "AssertionError: Expected True",
            },
            {"$report_type": "SessionFinish", "exitstatus": "1"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                json.dump(item, f)
                f.write("\n")
            log_file = f.name

        try:
            # Test main function
            main([log_file])

            # Check output file was created
            output_file = pathlib.Path("pytest-logs.txt")
            assert output_file.exists()

            content = output_file.read_text()
            assert "test_example.py::test_failing" in content
            assert "AssertionError: Expected True" in content

        finally:
            pathlib.Path(log_file).unlink()
            output_file = pathlib.Path("pytest-logs.txt")
            if output_file.exists():
                output_file.unlink()

    def test_main_with_collection_error(self):
        """Test main function with collection error."""
        test_data = [
            {
                "$report_type": "CollectReport",
                "nodeid": "",
                "outcome": "failed",
                "result": [],  # Required field for CollectReport
                "longrepr": "ImportError: No module named 'missing_module'",
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                json.dump(item, f)
                f.write("\n")
            log_file = f.name

        try:
            main([log_file])

            output_file = pathlib.Path("pytest-logs.txt")
            assert output_file.exists()

            content = output_file.read_text()
            assert "test collection session failed:" in content
            assert "ImportError: No module named 'missing_module'" in content

        finally:
            pathlib.Path(log_file).unlink()
            output_file = pathlib.Path("pytest-logs.txt")
            if output_file.exists():
                output_file.unlink()
