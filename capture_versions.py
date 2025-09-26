#!/usr/bin/env python3
"""
Capture package versions from the test environment.

This script captures package versions using the specified Python command
to ensure we get versions from the same environment that ran the tests.
"""
import json
import os
import sys


def main():
    """Main function to capture package versions."""
    packages_input = os.environ.get('TRACK_PACKAGES', '').strip()
    if not packages_input:
        print("No packages specified for tracking, skipping package capture")
        return

    packages = [pkg.strip() for pkg in packages_input.split(',')]
    versions = {}

    # Try importlib.metadata first (Python 3.8+)
    try:
        import importlib.metadata as metadata
        if len(packages) == 1 and packages[0].lower() == 'all':
            print('Capturing all installed packages...')
            for dist in metadata.distributions():
                versions[dist.name] = dist.version
        else:
            print(f'Capturing specific packages: {packages}')
            for pkg in packages:
                if pkg:
                    try:
                        versions[pkg] = metadata.version(pkg)
                        print(f'  {pkg}: {versions[pkg]}')
                    except Exception as e:
                        versions[pkg] = None
                        print(f'  {pkg}: not found ({e})')
    except ImportError:
        print('importlib.metadata not available, trying pkg_resources...')
        # Fallback to pkg_resources
        try:
            import pkg_resources
            if len(packages) == 1 and packages[0].lower() == 'all':
                print('Capturing all installed packages...')
                for dist in pkg_resources.working_set:
                    versions[dist.project_name] = dist.version
            else:
                print(f'Capturing specific packages: {packages}')
                for pkg in packages:
                    if pkg:
                        try:
                            versions[pkg] = pkg_resources.get_distribution(pkg).version
                            print(f'  {pkg}: {versions[pkg]}')
                        except Exception as e:
                            versions[pkg] = None
                            print(f'  {pkg}: not found ({e})')
        except ImportError:
            print('ERROR: No package detection method available')
            versions = {'error': 'No package detection method available'}

    # Save captured versions
    capture_data = {
        'python_version': '.'.join(map(str, sys.version_info[:3])),
        'python_executable': sys.executable,
        'packages': versions,
        'capture_method': 'importlib.metadata' if 'importlib.metadata' in sys.modules else 'pkg_resources'
    }

    with open('captured-package-versions.json', 'w') as f:
        json.dump(capture_data, f, indent=2)

    print(f'Captured {len(versions)} package versions')


if __name__ == '__main__':
    main()
