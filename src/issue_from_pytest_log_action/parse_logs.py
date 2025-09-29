# type: ignore
import argparse
import functools
import json
import pathlib
import re
import sys
import textwrap
from dataclasses import dataclass

import more_itertools
from pytest import CollectReport, TestReport

test_collection_stage = "test collection session"
fe_bytes = "[\x40-\x5f]"
parameter_bytes = "[\x30-\x3f]"
intermediate_bytes = "[\x20-\x2f]"
final_bytes = "[\x40-\x7e]"
ansi_fe_escape_re = re.compile(
    rf"""
    \x1B # ESC
    (?:
      \[  # CSI
      {parameter_bytes}*
      {intermediate_bytes}*
      {final_bytes}
      | {fe_bytes}  # single-byte Fe
    )
    """,
    re.VERBOSE,
)


def strip_ansi(msg):
    """strip all ansi escape sequences"""
    return ansi_fe_escape_re.sub("", msg)


@dataclass
class SessionStart:
    pytest_version: str
    outcome: str = "status"

    @classmethod
    def _from_json(cls, json):
        json_ = json.copy()
        json_.pop("$report_type")
        return cls(**json_)


@dataclass
class SessionFinish:
    exitstatus: str
    outcome: str = "status"

    @classmethod
    def _from_json(cls, json):
        json_ = json.copy()
        json_.pop("$report_type")
        return cls(**json_)


@dataclass
class PreformattedReport:
    filepath: str
    name: str
    variant: str | None
    message: str

    def __post_init__(self):
        self.message = strip_ansi(self.message)


@dataclass
class CollectionError:
    name: str
    repr_: str


def parse_record(record):
    report_types = {
        "TestReport": TestReport,
        "CollectReport": CollectReport,
        "SessionStart": SessionStart,
        "SessionFinish": SessionFinish,
    }
    cls = report_types.get(record["$report_type"])
    if cls is None:
        raise ValueError(f"unknown report type: {record['$report_type']}")

    return cls._from_json(record)


nodeid_re = re.compile(r"(?P<filepath>.+?)::(?P<name>.+?)(?:\[(?P<variant>.+)\])?")


def parse_nodeid(nodeid):
    match = nodeid_re.fullmatch(nodeid)
    if match is None:
        raise ValueError(f"unknown test id: {nodeid}")

    return match.groupdict()


@functools.singledispatch
def preformat_report(report):
    parsed = parse_nodeid(report.nodeid)
    return PreformattedReport(message=str(report), **parsed)


@preformat_report.register
def _(report: TestReport):
    parsed = parse_nodeid(report.nodeid)
    if isinstance(report.longrepr, str):
        message = report.longrepr
    else:
        message = report.longrepr.reprcrash.message
    return PreformattedReport(message=message, **parsed)


@preformat_report.register
def _(report: CollectReport):
    if report.nodeid == "":
        return CollectionError(name=test_collection_stage, repr_=str(report.longrepr))

    if "::" not in report.nodeid:
        parsed = {
            "filepath": report.nodeid,
            "name": None,
            "variant": None,
        }
    else:
        parsed = parse_nodeid(report.nodeid)

    if isinstance(report.longrepr, str):
        message = report.longrepr.split("\n")[-1].removeprefix("E").lstrip()
    else:
        message = report.longrepr.reprcrash.message
    return PreformattedReport(message=message, **parsed)


def format_summary(report):
    if report.variant is not None:
        return f"{report.filepath}::{report.name}[{report.variant}]: {report.message}"
    elif report.name is not None:
        return f"{report.filepath}::{report.name}: {report.message}"
    else:
        return f"{report.filepath}: {report.message}"


def format_report(summaries, py_version):
    template = textwrap.dedent(
        """\
        <details><summary>Python {py_version} Test Summary</summary>

        ```
        {summaries}
        ```

        </details>
        """
    )
    # can't use f-strings because that would format *before* the dedenting
    message = template.format(summaries="\n".join(summaries), py_version=py_version)
    return message


def merge_variants(reports, max_chars, **formatter_kwargs):
    def format_variant_group(name, group):
        filepath, test_name, message = name

        n_variants = len(group)
        if n_variants != 1:
            return f"{filepath}::{test_name}[{n_variants} failing variants]: {message}"
        elif n_variants == 1 and group[0].variant is not None:
            report = more_itertools.one(group)
            return f"{filepath}::{test_name}[{report.variant}]: {message}"
        else:
            return f"{filepath}::{test_name}: {message}"

    bucket = more_itertools.bucket(reports, lambda r: (r.filepath, r.name, r.message))

    summaries = [format_variant_group(name, list(bucket[name])) for name in bucket]
    formatted = format_report(summaries, **formatter_kwargs)

    return formatted


def truncate(reports, max_chars, **formatter_kwargs):
    fractions = [0.95, 0.75, 0.5, 0.25, 0.1, 0.01]

    n_reports = len(reports)
    for fraction in fractions:
        n_selected = int(n_reports * fraction)
        selected_reports = reports[: int(n_reports * fraction)]
        report_messages = [format_summary(report) for report in selected_reports]
        summary = report_messages + [f"+ {n_reports - n_selected} failing tests"]
        formatted = format_report(summary, **formatter_kwargs)
        if len(formatted) <= max_chars:
            return formatted

    return None


def summarize(reports, **formatter_kwargs):
    summary = [f"{len(reports)} failing tests"]
    return format_report(summary, **formatter_kwargs)


def compressed_report(reports, max_chars, **formatter_kwargs):
    strategies = [
        merge_variants,
        # merge_test_files,
        # merge_tests,
        truncate,
    ]
    summaries = [format_summary(report) for report in reports]
    formatted = format_report(summaries, **formatter_kwargs)
    if len(formatted) <= max_chars:
        return formatted

    for strategy in strategies:
        formatted = strategy(reports, max_chars=max_chars, **formatter_kwargs)
        if formatted is not None and len(formatted) <= max_chars:
            return formatted

    return summarize(reports, **formatter_kwargs)


def format_collection_error(error, py_version, **formatter_kwargs):
    return textwrap.dedent(
        """\
        <details><summary>Python {py_version} Test Summary</summary>

        {name} failed:
        ```
        {traceback}
        ```

        </details>
        """
    ).format(py_version=py_version, name=error.name, traceback=error.repr_)


def include_bisection_info(message: str, bisect_file: str = "bisect-comparison.txt") -> str:
    """Include bisection information in the issue message if available."""
    bisect_path = pathlib.Path(bisect_file)
    if bisect_path.exists():
        bisect_content = bisect_path.read_text().strip()
        if bisect_content:
            return f"{bisect_content}\n{message}"
    return message


def main(argv=None):
    """Main entry point for parse_logs module."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("filepath", type=pathlib.Path)
    args = parser.parse_args(argv)

    py_version = ".".join(str(_) for _ in sys.version_info[:2])

    print("Parsing logs ...")

    lines = args.filepath.read_text().splitlines()
    parsed_lines = [json.loads(line) for line in lines]
    reports = [
        parse_record(data) for data in parsed_lines if data["$report_type"] != "WarningMessage"
    ]

    failed = [report for report in reports if report.outcome == "failed"]
    preformatted = [preformat_report(report) for report in failed]
    if len(preformatted) == 1 and isinstance(preformatted[0], CollectionError):
        message = format_collection_error(preformatted[0], py_version=py_version)
    else:
        message = compressed_report(preformatted, max_chars=65535, py_version=py_version)

    # Include bisection information if available
    message = include_bisection_info(message)

    output_file = pathlib.Path("pytest-logs.txt")
    print(f"Writing output file to: {output_file.absolute()}")
    output_file.write_text(message)


if __name__ == "__main__":
    main()
