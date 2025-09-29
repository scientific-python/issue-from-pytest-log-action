#!/usr/bin/env python3
"""
Capture package versions from the test environment.

This script captures package versions using the specified Python command
to ensure we get versions from the same environment that ran the tests.
"""

import json
import os
import sys


def extract_git_hash_from_version(version_string: str) -> str | None:
    """Extract git hash from version string (e.g., '2.1.0.dev0+123.gabc123d')."""
    import re

    # Common patterns for git hashes in version strings
    patterns = [
        r"\.g([a-f0-9]{7,40})",  # .gabc123d or .gabc123def456...
        r"\+g([a-f0-9]{7,40})",  # +gabc123d
        r"g([a-f0-9]{7,40})",  # gabc123d (less specific, used last)
    ]

    for pattern in patterns:
        match = re.search(pattern, version_string, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_git_info(package_name: str) -> dict:
    """Extract git revision and other VCS info from a package."""
    git_info = {}

    try:
        import importlib

        # Try to import the package to check for version attributes
        pkg = importlib.import_module(package_name.replace("-", "_"))

        # Check for git revision in various locations
        revision_attrs = [
            "__git_revision__",
            "version.git_revision",
            "_version.get_versions",
            "__version_info__.git_revision",
        ]

        for attr_path in revision_attrs:
            try:
                obj = pkg
                for part in attr_path.split("."):
                    obj = getattr(obj, part)

                if callable(obj):
                    result = obj()
                    if isinstance(result, dict):
                        git_info.update(result)
                    else:
                        git_info["git_revision"] = str(result)
                else:
                    git_info["git_revision"] = str(obj)
                break
            except AttributeError:
                continue

        # Check for full version info
        if hasattr(pkg, "version") and hasattr(pkg.version, "full_version"):
            git_info["full_version"] = pkg.version.full_version

        # If we haven't found a git revision yet, try to extract from version string
        if "git_revision" not in git_info and hasattr(pkg, "__version__"):
            version_hash = extract_git_hash_from_version(pkg.__version__)
            if version_hash:
                git_info["git_revision"] = version_hash
                git_info["source"] = "version_string"

    except (ImportError, AttributeError):
        pass

    # Also try to extract from importlib.metadata if available
    if not git_info:
        try:
            import importlib.metadata as metadata

            dist = metadata.distribution(package_name)
            version = dist.version

            # Check if the version string contains a git hash
            version_hash = extract_git_hash_from_version(version)
            if version_hash:
                git_info["git_revision"] = version_hash
                git_info["source"] = "metadata_version"
                git_info["full_version"] = version

        except Exception:
            pass

    return git_info


def main():
    """Main function to capture package versions."""
    packages_input = os.environ.get("TRACK_PACKAGES", "").strip()
    if not packages_input:
        print("No packages specified for tracking, skipping package capture")
        return

    packages = [pkg.strip() for pkg in packages_input.split(",")]
    versions = {}

    # Try importlib.metadata first (Python 3.8+)
    try:
        import importlib.metadata as metadata

        if len(packages) == 1 and packages[0].lower() == "all":
            print("Capturing all installed packages...")
            for dist in metadata.distributions():
                pkg_info = {"version": dist.version, "git_info": extract_git_info(dist.name)}
                versions[dist.name] = pkg_info
        else:
            print(f"Capturing specific packages: {packages}")
            for pkg in packages:
                if pkg:
                    try:
                        pkg_version = metadata.version(pkg)
                        git_info = extract_git_info(pkg)

                        pkg_info = {"version": pkg_version, "git_info": git_info}
                        versions[pkg] = pkg_info

                        print(f"  {pkg}: {pkg_version}")
                        if git_info:
                            for key, value in git_info.items():
                                print(f"    {key}: {value}")
                    except Exception as e:
                        versions[pkg] = None
                        print(f"  {pkg}: not found ({e})")
    except ImportError:
        print("importlib.metadata not available, trying pkg_resources...")
        # Fallback to pkg_resources
        try:
            import pkg_resources  # type: ignore[import-not-found]

            if len(packages) == 1 and packages[0].lower() == "all":
                print("Capturing all installed packages...")
                for dist in pkg_resources.working_set:
                    pkg_info = {
                        "version": dist.version,
                        "git_info": extract_git_info(dist.project_name),
                    }
                    versions[dist.project_name] = pkg_info
            else:
                print(f"Capturing specific packages: {packages}")
                for pkg in packages:
                    if pkg:
                        try:
                            pkg_version = pkg_resources.get_distribution(pkg).version
                            git_info = extract_git_info(pkg)

                            pkg_info = {"version": pkg_version, "git_info": git_info}
                            versions[pkg] = pkg_info

                            print(f"  {pkg}: {pkg_version}")
                            if git_info:
                                for key, value in git_info.items():
                                    print(f"    {key}: {value}")
                        except Exception as e:
                            versions[pkg] = None
                            print(f"  {pkg}: not found ({e})")
        except ImportError:
            print("ERROR: No package detection method available")
            versions = {"error": "No package detection method available"}

    # Save captured versions
    capture_data = {
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "python_executable": sys.executable,
        "packages": versions,
        "capture_method": (
            "importlib.metadata" if "importlib.metadata" in sys.modules else "pkg_resources"
        ),
    }

    with open("captured-package-versions.json", "w") as f:
        json.dump(capture_data, f, indent=2)

    print(f"Captured {len(versions)} package versions")


if __name__ == "__main__":
    main()
