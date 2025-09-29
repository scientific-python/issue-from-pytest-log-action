"""
Package version tracking for bisection analysis.

This module handles tracking package versions between CI runs to help identify
which dependency changes might have caused test failures.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime
from typing import Any

# Package metadata for generating GitHub links
PACKAGE_METADATA = {
    "numpy": {"github": "numpy/numpy", "type": "releases"},
    "pandas": {"github": "pandas-dev/pandas", "type": "releases"},
    "matplotlib": {"github": "matplotlib/matplotlib", "type": "releases"},
    "scipy": {"github": "scipy/scipy", "type": "releases"},
    "scikit-learn": {"github": "scikit-learn/scikit-learn", "type": "releases"},
    "requests": {"github": "psf/requests", "type": "releases"},
    "django": {"github": "django/django", "type": "releases"},
    "flask": {"github": "pallets/flask", "type": "releases"},
    "pytest": {"github": "pytest-dev/pytest", "type": "releases"},
    "hypothesis": {"github": "HypothesisWorks/hypothesis", "type": "releases"},
    "xarray": {"github": "pydata/xarray", "type": "releases"},
    "dask": {"github": "dask/dask", "type": "releases"},
    "jupyterlab": {"github": "jupyterlab/jupyterlab", "type": "releases"},
    "notebook": {"github": "jupyter/notebook", "type": "releases"},
    "ipython": {"github": "ipython/ipython", "type": "releases"},
    "tensorflow": {"github": "tensorflow/tensorflow", "type": "releases"},
    "torch": {"github": "pytorch/pytorch", "type": "releases"},
    "fastapi": {"github": "tiangolo/fastapi", "type": "releases"},
    "pydantic": {"github": "pydantic/pydantic", "type": "releases"},
    "sqlalchemy": {"github": "sqlalchemy/sqlalchemy", "type": "releases"},
    "black": {"github": "psf/black", "type": "releases"},
    "mypy": {"github": "python/mypy", "type": "releases"},
    "ruff": {"github": "astral-sh/ruff", "type": "releases"},
}


def generate_package_diff_link(package_name: str, old_version: str, new_version: str) -> str | None:
    """Generate a GitHub diff link for package version changes."""
    if package_name not in PACKAGE_METADATA:
        return None

    metadata = PACKAGE_METADATA[package_name]
    repo = metadata["github"]

    if metadata["type"] == "releases":
        # Try different tag formats common in Python packages
        tag_formats = [
            f"v{old_version}...v{new_version}",  # v1.0.0...v1.1.0
            f"{old_version}...{new_version}",  # 1.0.0...1.1.0
            f"release-{old_version}...release-{new_version}",  # release-1.0.0...release-1.1.0
        ]

        # Return the first format (most common)
        return f"https://github.com/{repo}/compare/{tag_formats[0]}"

    return None


def get_all_installed_packages() -> dict[str, str | None]:
    """Get all installed packages and their versions."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
        packages_data = json.loads(result.stdout)
        return {pkg["name"]: pkg["version"] for pkg in packages_data}
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def get_package_version(package_name: str) -> str | None:
    """Get the version of an installed package."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except (subprocess.CalledProcessError, IndexError):
        pass
    return None


def get_current_package_versions(
    packages: list[str], captured_versions_file: str | None = None
) -> dict[str, Any]:
    """Get current versions of specified packages with git info if available."""
    # First try to read from captured versions file if provided
    if captured_versions_file and os.path.exists(captured_versions_file):
        try:
            with open(captured_versions_file) as f:
                captured_data = json.load(f)
                captured_packages = captured_data.get("packages", {})

                if len(packages) == 1 and packages[0].lower() == "all":
                    return captured_packages  # type: ignore[return-value]

                # Return only the requested packages from captured data
                versions = {}
                for package in packages:
                    versions[package] = captured_packages.get(package)
                return versions
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read captured versions file {captured_versions_file}: {e}")
            print("Falling back to direct package detection...")

    # Fallback to direct detection (original behavior) - returns simple version strings
    if len(packages) == 1 and packages[0].lower() == "all":
        return get_all_installed_packages()

    versions = {}
    for package in packages:
        versions[package] = get_package_version(package)
    return versions


def extract_failed_tests_from_log(log_path: str) -> list[str]:
    """Extract failed test nodeids from pytest log file."""
    failed_tests = []
    try:
        with open(log_path) as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if (
                        record.get("$report_type") in ["TestReport", "CollectReport"]
                        and record.get("outcome") == "failed"
                        and record.get("nodeid")
                    ):
                        failed_tests.append(record["nodeid"])
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return failed_tests


def get_git_info() -> dict[str, str]:
    """Get current Git commit information."""
    try:
        # Get current commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit_hash = commit_result.stdout.strip()

        # Get commit message
        message_result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit_message = message_result.stdout.strip()

        # Get commit author and date
        author_result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%an <%ae>"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit_author = author_result.stdout.strip()

        date_result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%ci"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit_date = date_result.stdout.strip()

        return {
            "commit_hash": commit_hash,
            "commit_hash_short": commit_hash[:8],
            "commit_message": commit_message,
            "commit_author": commit_author,
            "commit_date": commit_date,
        }
    except subprocess.CalledProcessError:
        return {
            "commit_hash": "unknown",
            "commit_hash_short": "unknown",
            "commit_message": "unknown",
            "commit_author": "unknown",
            "commit_date": "unknown",
        }


def create_bisect_data(
    packages: list[str],
    log_path: str | None = None,
    captured_versions_file: str | None = None,
    workflow_run_id: str | None = None,
) -> dict:
    """Create bisection data for current environment."""
    if workflow_run_id is None:
        workflow_run_id = os.environ.get("GITHUB_RUN_ID", "unknown")

    failed_tests = []
    if log_path and os.path.exists(log_path):
        failed_tests = extract_failed_tests_from_log(log_path)

    # Get package versions - prefer captured versions, fall back to direct detection
    package_versions = get_current_package_versions(packages, captured_versions_file)

    # Get Python version - prefer from captured data if available
    python_version = ".".join(str(v) for v in sys.version_info[:3])
    if captured_versions_file and os.path.exists(captured_versions_file):
        try:
            with open(captured_versions_file) as f:
                captured_data = json.load(f)
                if "python_version" in captured_data:
                    python_version = captured_data["python_version"]
        except (json.JSONDecodeError, OSError):
            pass  # Use default python_version

    return {
        "workflow_run_id": workflow_run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "python_version": python_version,
        "packages": package_versions,
        "failed_tests": failed_tests,
        "test_status": "failed" if failed_tests else "passed",
        "git": get_git_info(),
    }


def store_bisect_data_to_branch(data: dict, branch_name: str) -> bool:
    """Store bisection data to a Git branch."""
    try:
        # Create filename based on run ID and timestamp
        filename = f"run_{data['workflow_run_id']}_{data['timestamp'].replace(':', '-').replace('Z', '')}.json"

        # Configure git user if not already set (needed for GitHub Actions)
        try:
            subprocess.run(["git", "config", "user.name"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
            subprocess.run(
                [
                    "git",
                    "config",
                    "user.email",
                    "github-actions[bot]@users.noreply.github.com",
                ],
                check=True,
            )

        # Check if branch exists remotely
        branch_exists_result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch_name],
            capture_output=True,
            text=True,
        )
        branch_exists = bool(branch_exists_result.stdout.strip())

        # Store current branch to restore later
        current_branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        original_branch = (
            current_branch_result.stdout.strip() if current_branch_result.returncode == 0 else None
        )

        try:
            if branch_exists:
                # Fetch and checkout existing branch
                subprocess.run(["git", "fetch", "origin", branch_name], check=True)

                # Check if local branch exists
                local_branch_exists = (
                    subprocess.run(
                        ["git", "rev-parse", "--verify", branch_name],
                        capture_output=True,
                    ).returncode
                    == 0
                )

                if local_branch_exists:
                    subprocess.run(["git", "checkout", branch_name], check=True)
                    subprocess.run(["git", "reset", "--hard", f"origin/{branch_name}"], check=True)
                else:
                    subprocess.run(
                        ["git", "checkout", "-b", branch_name, f"origin/{branch_name}"],
                        check=True,
                    )
            else:
                # Create new orphan branch
                subprocess.run(["git", "checkout", "--orphan", branch_name], check=True)
                # Remove any existing files from the new branch
                subprocess.run(["git", "rm", "-rf", "."], capture_output=True, check=False)

            # Write the data file
            pathlib.Path(filename).write_text(json.dumps(data, indent=2))

            # Add and commit the file
            subprocess.run(["git", "add", filename], check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Add run data for {data['workflow_run_id']} ({data['test_status']})",
                ],
                check=True,
            )

            # Push the branch (create remote branch if it doesn't exist)
            if branch_exists:
                subprocess.run(["git", "push", "origin", branch_name], check=True)
            else:
                subprocess.run(["git", "push", "-u", "origin", branch_name], check=True)

        finally:
            # Restore original branch if possible
            if original_branch and original_branch != branch_name:
                try:
                    subprocess.run(
                        ["git", "checkout", original_branch],
                        check=True,
                        capture_output=True,
                    )
                except subprocess.CalledProcessError:
                    # If we can't restore, at least try to get back to main/master
                    for fallback_branch in ["main", "master"]:
                        try:
                            subprocess.run(
                                ["git", "checkout", fallback_branch],
                                check=True,
                                capture_output=True,
                            )
                            break
                        except subprocess.CalledProcessError:
                            continue

        return True
    except subprocess.CalledProcessError as e:
        print(f"Error storing bisect data to branch '{branch_name}': {e}")
        print(
            f"Make sure the repository has proper permissions and the branch name '{branch_name}' is valid"
        )
        return False
    except Exception as e:
        print(f"Unexpected error storing bisect data: {e}")
        return False


def retrieve_last_successful_run(branch_name: str) -> dict | None:
    """Retrieve the most recent successful run data from a Git branch."""
    try:
        # Check if branch exists remotely
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch_name],
            capture_output=True,
            text=True,
            check=True,
        )

        if not result.stdout.strip():
            return None

        # Fetch the branch
        subprocess.run(["git", "fetch", "origin", f"{branch_name}:{branch_name}"], check=True)

        # List all JSON files in the branch
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch_name],
            capture_output=True,
            text=True,
            check=True,
        )

        json_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".json")]

        if not json_files:
            return None

        # Check each file to find the most recent successful run
        most_recent_success = None
        most_recent_timestamp = None

        for filename in json_files:
            try:
                # Get the file content
                file_result = subprocess.run(
                    ["git", "show", f"{branch_name}:{filename}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                run_data = json.loads(file_result.stdout)

                # Check if this was a successful run
                if run_data.get("test_status") == "passed":
                    timestamp = run_data.get("timestamp")
                    if timestamp and (
                        most_recent_timestamp is None or timestamp > most_recent_timestamp
                    ):
                        most_recent_timestamp = timestamp
                        most_recent_success = run_data

            except (subprocess.CalledProcessError, json.JSONDecodeError):
                continue

        return most_recent_success

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def find_last_successful_run_for_tests(
    branch_name: str, failed_tests: list[str]
) -> dict[str, dict | None]:
    """Find the last successful run for each currently failing test."""
    test_last_success: dict[str, dict | None] = {}

    try:
        # Get all run files
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch_name],
            capture_output=True,
            text=True,
            check=True,
        )

        json_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".json")]

        # Get all run data and sort by timestamp (newest first)
        all_runs = []
        for filename in json_files:
            try:
                file_result = subprocess.run(
                    ["git", "show", f"{branch_name}:{filename}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                run_data = json.loads(file_result.stdout)
                all_runs.append(run_data)
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                continue

        # Sort by timestamp (newest first)
        all_runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # For each currently failing test, find its last successful run
        for test in failed_tests:
            test_last_success[test] = None
            for run in all_runs:
                # If this test wasn't in the failed list for this run, it passed
                if test not in run.get("failed_tests", []):
                    test_last_success[test] = run
                    break

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        # Initialize with None for all tests if we can't retrieve data
        for test in failed_tests:
            test_last_success[test] = None

    return test_last_success


def extract_version_string(package_info: dict | str | None) -> str | None:
    """Extract version string from package info (handles both old and new formats)."""
    if package_info is None:
        return None
    if isinstance(package_info, str):
        return package_info
    if isinstance(package_info, dict):
        return package_info.get("version")
    return None


def extract_git_revision(package_info: dict | str | None) -> str | None:
    """Extract git revision from package info if available."""
    if isinstance(package_info, dict) and "git_info" in package_info:
        git_info = package_info["git_info"]
        return git_info.get("git_revision")
    return None


def format_version_with_git(package_info: dict | str | None) -> str:
    """Format version string with git revision if available."""
    version = extract_version_string(package_info)
    if version is None:
        return "(missing)"

    git_revision = extract_git_revision(package_info)
    if git_revision:
        # Show first 8 characters of git hash
        short_hash = git_revision[:8]
        return f"{version} ({short_hash})"
    return version


def get_package_changes(current_packages: dict, previous_packages: dict) -> list[str]:
    """Get list of package changes between two runs."""
    changes = []
    all_packages = set(current_packages.keys()) | set(previous_packages.keys())

    for package in sorted(all_packages):
        current_info = current_packages.get(package)
        previous_info = previous_packages.get(package)

        current_version = extract_version_string(current_info)
        previous_version = extract_version_string(previous_info)

        if current_version is None and previous_version is None:
            continue
        elif current_version is None:
            prev_display = format_version_with_git(previous_info)
            changes.append(f"- {package}: {prev_display} → (removed)")
        elif previous_version is None:
            curr_display = format_version_with_git(current_info)
            changes.append(f"- {package}: (new) → {curr_display}")
        elif current_version != previous_version or extract_git_revision(
            current_info
        ) != extract_git_revision(previous_info):
            # Version changed OR git revision changed
            prev_display = format_version_with_git(previous_info)
            curr_display = format_version_with_git(current_info)

            # Try to generate a GitHub diff link for version changes
            if current_version != previous_version:
                diff_link = generate_package_diff_link(package, previous_version, current_version)
                if diff_link:
                    changes.append(f"- [{package}: {prev_display} → {curr_display}]({diff_link})")
                else:
                    changes.append(f"- {package}: {prev_display} → {curr_display}")
            else:
                # Only git revision changed (nightly build case)
                changes.append(
                    f"- {package}: {prev_display} → {curr_display} (git revision changed)"
                )

    return changes


def format_bisect_comparison(
    current_data: dict, previous_data: dict | None, branch_name: str
) -> str | None:
    """Format bisection comparison for display in GitHub issue."""
    failed_tests = current_data.get("failed_tests", [])
    if not failed_tests:
        return None

    test_last_success = find_last_successful_run_for_tests(branch_name, failed_tests)
    current_packages = current_data["packages"]
    current_git = current_data.get("git", {})

    test_sections = []

    for test in failed_tests:
        last_success = test_last_success.get(test)

        # Create section for this failing test
        test_section = [f"## {test}"]

        if last_success:
            # Get changes since this test last passed
            last_success_packages = last_success.get("packages", {})
            last_success_git = last_success.get("git", {})

            # Package changes since last pass
            package_changes = get_package_changes(current_packages, last_success_packages)
            if package_changes:
                test_section.append("### Package changes since last pass")
                test_section.extend(package_changes)
            else:
                test_section.append("### Package changes since last pass")
                test_section.append("- No package changes detected")

            # Code changes since last pass
            if current_git.get("commit_hash") != last_success_git.get("commit_hash"):
                prev_commit = last_success_git.get("commit_hash_short", "unknown")
                curr_commit = current_git.get("commit_hash_short", "unknown")
                prev_msg = last_success_git.get("commit_message", "")[:60] + (
                    "..." if len(last_success_git.get("commit_message", "")) > 60 else ""
                )
                curr_msg = current_git.get("commit_message", "")[:60] + (
                    "..." if len(current_git.get("commit_message", "")) > 60 else ""
                )

                test_section.append("### Code changes since last pass")
                test_section.append(f"- {prev_commit} ({prev_msg})")
                test_section.append(f"- → {curr_commit} ({curr_msg})")
                test_section.append(
                    f"- Last passed in run #{last_success['workflow_run_id']} on {last_success['timestamp']}"
                )
            else:
                test_section.append("### Code changes since last pass")
                test_section.append("- No code changes detected")
                test_section.append(
                    f"- Last passed in run #{last_success['workflow_run_id']} on {last_success['timestamp']}"
                )
        else:
            test_section.append("### Analysis")
            test_section.append("- No recent successful run found for this test")

        test_sections.append("\n".join(test_section))

    if test_sections:
        return "\n\n".join(test_sections) + "\n\n"

    return None


def main():
    parser = argparse.ArgumentParser(description="Track package versions for bisection")
    parser.add_argument(
        "--packages",
        required=True,
        help="Comma-separated list of packages to track",
    )
    parser.add_argument(
        "--log-path",
        help="Path to pytest log file",
    )
    parser.add_argument(
        "--captured-versions",
        help="Path to captured package versions JSON file",
    )
    parser.add_argument(
        "--store-run",
        action="store_true",
        help="Store current run data (both packages and test results)",
    )
    parser.add_argument(
        "--generate-comparison",
        action="store_true",
        help="Generate comparison with last successful run",
    )
    parser.add_argument(
        "--branch",
        default="bisect-data",
        help="Branch name for storing bisection data",
    )
    parser.add_argument(
        "--output-file",
        default="bisect-comparison.txt",
        help="Output file for bisection comparison",
    )

    args = parser.parse_args()

    packages = [pkg.strip() for pkg in args.packages.split(",") if pkg.strip()]

    if args.store_run:
        # Store current run data (packages + test results)
        data = create_bisect_data(packages, args.log_path, args.captured_versions)
        success = store_bisect_data_to_branch(data, args.branch)
        if success:
            print(
                f"Successfully stored run data to branch '{args.branch}' (status: {data['test_status']})"
            )
        else:
            print("Failed to store run data", file=sys.stderr)
            sys.exit(1)

    if args.generate_comparison:
        # Generate comparison with last successful run
        current_data = create_bisect_data(packages, args.log_path, args.captured_versions)
        previous_data = retrieve_last_successful_run(args.branch)

        comparison = format_bisect_comparison(current_data, previous_data, args.branch)

        output_path = pathlib.Path(args.output_file)
        if comparison:
            output_path.write_text(comparison)
            print(f"Bisection comparison written to {output_path.absolute()}")
        else:
            output_path.write_text("")
            print("No bisection data to display")


if __name__ == "__main__":
    main()
