#!/usr/bin/env python3
"""
Simplified bisection data handling - Git operations done by GitHub Actions.

This script only handles data creation and file operations. All Git branch
switching, fetching, and pushing is handled by GitHub Actions workflow steps.
"""

import argparse
import json
from pathlib import Path

import track_packages


def create_run_data_file(
    packages: list[str], log_path: str | None, captured_versions_file: str | None
) -> str:
    """Create bisection data file for current run."""
    data = track_packages.create_bisect_data(packages, log_path, captured_versions_file)

    # Create filename based on run ID and timestamp
    filename = (
        f"run_{data['workflow_run_id']}_{data['timestamp'].replace(':', '-').replace('Z', '')}.json"
    )

    # Write the data file
    Path(filename).write_text(json.dumps(data, indent=2))

    print(f"Created run data file: {filename}")
    print(f"Test status: {data['test_status']}")
    print(f"Failed tests: {len(data.get('failed_tests', []))}")

    return filename


def find_last_successful_run(directory: str = ".") -> dict | None:
    """Find the most recent successful run from JSON files in current directory."""
    json_files = list(Path(directory).glob("run_*.json"))

    if not json_files:
        return None

    most_recent_success = None
    most_recent_timestamp = None

    for json_file in json_files:
        try:
            run_data = json.loads(json_file.read_text())

            # Check if this was a successful run
            if run_data.get("test_status") == "passed":
                timestamp = run_data.get("timestamp")
                if timestamp and (
                    most_recent_timestamp is None or timestamp > most_recent_timestamp
                ):
                    most_recent_timestamp = timestamp
                    most_recent_success = run_data

        except (json.JSONDecodeError, OSError):
            continue

    return most_recent_success


def generate_comparison(
    packages: list[str], log_path: str | None, captured_versions_file: str | None, branch_name: str
) -> None:
    """Generate bisection comparison from current run and historical data."""
    # Create current run data
    current_data = track_packages.create_bisect_data(packages, log_path, captured_versions_file)

    # Find last successful run from files in current directory (bisect branch)
    previous_data = find_last_successful_run()

    # Generate comparison
    comparison = track_packages.format_bisect_comparison(current_data, previous_data, branch_name)

    # Write comparison to file
    output_path = Path("bisect-comparison.txt")
    if comparison:
        output_path.write_text(comparison)
        print(f"Bisection comparison written to {output_path.absolute()}")
    else:
        print("No comparison generated (no failed tests)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Handle bisection data")
    parser.add_argument("--packages", required=True, help="Comma-separated list of packages")
    parser.add_argument("--log-path", help="Path to pytest log file")
    parser.add_argument("--captured-versions", help="Path to captured versions JSON file")
    parser.add_argument("--branch", default="bisect-data", help="Branch name for bisection data")

    # Action to perform
    parser.add_argument("--store-run", action="store_true", help="Store current run data")
    parser.add_argument(
        "--generate-comparison", action="store_true", help="Generate bisection comparison"
    )

    args = parser.parse_args()

    packages = [pkg.strip() for pkg in args.packages.split(",") if pkg.strip()]

    if args.store_run:
        create_run_data_file(packages, args.log_path, args.captured_versions)

    if args.generate_comparison:
        generate_comparison(packages, args.log_path, args.captured_versions, args.branch)


if __name__ == "__main__":
    main()
