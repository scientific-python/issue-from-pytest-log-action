#!/usr/bin/env python3
"""
Store bisection data as JSON file - Git operations handled by GitHub Actions.

This simplified approach creates the JSON data file and lets GitHub Actions
handle all Git operations for better transparency and debugging.
"""

import json
import sys
from pathlib import Path

import track_packages


def main():
    """Create bisection data file for GitHub Actions to commit."""
    if len(sys.argv) < 3:
        print("Usage: store_bisect_data.py <packages> <log_path> [captured_versions_file]")
        sys.exit(1)

    packages_str = sys.argv[1]
    log_path = sys.argv[2]
    captured_versions_file = sys.argv[3] if len(sys.argv) > 3 else None

    packages = [pkg.strip() for pkg in packages_str.split(",") if pkg.strip()]

    # Create bisection data
    data = track_packages.create_bisect_data(packages, log_path, captured_versions_file)

    # Create filename based on run ID and timestamp
    filename = (
        f"run_{data['workflow_run_id']}_{data['timestamp'].replace(':', '-').replace('Z', '')}.json"
    )

    # Write the data file
    Path(filename).write_text(json.dumps(data, indent=2))

    print(f"Created bisection data file: {filename}")
    print(f"Test status: {data['test_status']}")
    print(f"Failed tests: {len(data.get('failed_tests', []))}")


if __name__ == "__main__":
    main()
