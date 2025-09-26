#!/usr/bin/env python3
"""
Generate bisection comparison using GitHub API instead of Git operations.

This approach uses the GitHub API to fetch previous run data from the branch,
avoiding complex Git subprocess operations.
"""

import json
import os
import sys
from pathlib import Path

import track_packages


def fetch_previous_data_via_api(repo: str, branch: str, token: str) -> dict | None:
    """Fetch the most recent successful run data via GitHub API."""
    import urllib.error
    import urllib.request

    try:
        # Get branch contents
        url = f"https://api.github.com/repos/{repo}/contents?ref={branch}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github.v3+json")

        with urllib.request.urlopen(req) as response:
            files = json.loads(response.read().decode())

        # Find JSON files
        json_files = [f for f in files if f["name"].endswith(".json")]

        if not json_files:
            return None

        # Check each file to find the most recent successful run
        most_recent_success = None
        most_recent_timestamp = None

        for file_info in json_files:
            try:
                # Fetch file content
                content_url = file_info["download_url"]
                with urllib.request.urlopen(content_url) as response:
                    run_data = json.loads(response.read().decode())

                # Check if this was a successful run
                if run_data.get("test_status") == "passed":
                    timestamp = run_data.get("timestamp")
                    if timestamp and (
                        most_recent_timestamp is None or timestamp > most_recent_timestamp
                    ):
                        most_recent_timestamp = timestamp
                        most_recent_success = run_data

            except (urllib.error.URLError, json.JSONDecodeError):
                continue

        return most_recent_success

    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def main():
    """Generate bisection comparison using GitHub API."""
    if len(sys.argv) < 4:
        print(
            "Usage: generate_bisect_comparison.py <packages> <log_path> <branch> [captured_versions_file]"
        )
        sys.exit(1)

    packages_str = sys.argv[1]
    log_path = sys.argv[2]
    branch = sys.argv[3]
    captured_versions_file = sys.argv[4] if len(sys.argv) > 4 else None

    packages = [pkg.strip() for pkg in packages_str.split(",") if pkg.strip()]

    # Create current run data
    current_data = track_packages.create_bisect_data(packages, log_path, captured_versions_file)

    # Get repository info from environment
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")

    if not repo or not token:
        print("Error: GITHUB_REPOSITORY and GITHUB_TOKEN environment variables required")
        sys.exit(1)

    # Fetch previous successful run data
    previous_data = fetch_previous_data_via_api(repo, branch, token)

    # Generate comparison
    comparison = track_packages.format_bisect_comparison(current_data, previous_data, branch)

    # Write comparison to file
    output_path = Path("bisect-comparison.txt")
    if comparison:
        output_path.write_text(comparison)
        print(f"Bisection comparison written to {output_path.absolute()}")
    else:
        print("No comparison generated (no failed tests)")


if __name__ == "__main__":
    main()
