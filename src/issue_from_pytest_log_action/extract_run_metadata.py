#!/usr/bin/env python3
"""Extract metadata from bisection run JSON files for commit messages."""

import argparse
import json
import pathlib
import sys
from typing import Any


def find_latest_run_file() -> pathlib.Path:
    """Find the most recent run_*.json file in the current directory."""
    current_dir = pathlib.Path(".")
    run_files = list(current_dir.glob("run_*.json"))

    if not run_files:
        raise FileNotFoundError("No run_*.json files found in current directory")

    # Sort by modification time and return the most recent
    return max(run_files, key=lambda f: f.stat().st_mtime)


def load_run_data(file_path: pathlib.Path) -> dict[str, Any]:
    """Load and parse the run JSON data."""
    try:
        with file_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to load run data from {file_path}: {e}")


def extract_test_status(data: dict[str, Any]) -> str:
    """Extract the test status from run data."""
    return data.get("test_status", "unknown")


def extract_failed_test_count(data: dict[str, Any]) -> int:
    """Extract the count of failed tests from run data."""
    failed_tests = data.get("failed_tests", [])
    return len(failed_tests)


def main(argv=None):
    """Main entry point for extract_run_metadata command."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Extract metadata from bisection run JSON files")
    parser.add_argument(
        "field", choices=["test_status", "failed_count"], help="Field to extract from the run data"
    )
    parser.add_argument(
        "--file",
        type=pathlib.Path,
        help="Specific run file to read (default: find latest run_*.json)",
    )

    args = parser.parse_args(argv)

    try:
        # Find the run file
        if args.file:
            run_file = args.file
        else:
            run_file = find_latest_run_file()

        # Load the data
        data = load_run_data(run_file)

        # Extract the requested field
        if args.field == "test_status":
            result = extract_test_status(data)
        elif args.field == "failed_count":
            result = extract_failed_test_count(data)

        print(result)

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
