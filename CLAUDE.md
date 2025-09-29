# Issue from pytest log action

## Project Goals

This GitHub Action creates GitHub issues from pytest failures and provides **bisection analysis** to identify which package version changes may have caused test failures. It's particularly useful for monitoring upstream dependency changes in CI pipelines.

## Key Features

- **Automated Issue Creation**: Parses pytest-reportlog files and creates/updates GitHub issues for failures
- **Package Version Tracking**: Captures package versions from the test environment using any Python package manager (pip, conda, uv, poetry, pixi)
- **Bisection Analysis**: Compares current failures with historical successful runs to identify version changes
- **Git Commit Hash Extraction**: Extracts commit hashes from nightly wheels and setuptools_scm packages for precise tracking
- **Per-Test Analysis**: Shows when each failing test last passed and what changed since then

## Project Structure

```
├── src/issue_from_pytest_log_action/     # Main Python package
│   ├── capture_versions.py               # Extract package versions & git info
│   ├── simple_bisect.py                  # Bisection data handling
│   └── track_packages.py                 # Package comparison & GitHub links
├── tests/                                 # Comprehensive test suite (59 tests)
│   ├── test_version_extraction.py        # Core version handling tests
│   ├── test_nightly_wheels.py           # Scientific Python nightly wheel support
│   └── test_version_string_parsing.py   # Git hash extraction from version strings
├── action.yaml                          # GitHub Action definition
├── parse_logs.py                        # Legacy pytest log parser
└── .github/workflows/test.yml           # CI testing workflow
```

## How It Works

1. **Test Environment Analysis**: Captures package versions from the same environment that ran tests
2. **Git Operations**: Uses GitHub Actions steps to manage the bisection data branch
3. **Historical Comparison**: Compares current failures with the last successful run
4. **Rich Reporting**: Generates markdown reports with GitHub diff links and git commit info

## Nightly Wheel Support

The action can extract git commit hashes from various version string patterns:

- `2.1.0.dev0+123.gabc123d` → `abc123d`
- `1.5.0+gdef456a789` → `def456a789`
- Scientific Python nightly wheels from `pypi.anaconda.org/scientific-python-nightly-wheels/simple`

## Usage Example

```yaml
- name: Create issue from pytest failures
  uses: ianhi/issue-from-pytest-log-action@bisect
  with:
    log-path: pytest-log.jsonl
    track-packages: "numpy,pandas,xarray"
    python-command: "uv run python"
```

## Development

- **Package Management**: Uses `uv` for dependency management
- **Testing**: Run `uv run pytest tests/` (59 comprehensive tests)
- **Linting**: Pre-commit hooks with ruff, mypy, and actionlint
- **Installation**: `pip install .` installs the `issue-from-pytest-log-action` package

## Key Files to Understand

- `action.yaml`: The main GitHub Action interface
- `src/issue_from_pytest_log_action/capture_versions.py`: Version extraction logic
- `src/issue_from_pytest_log_action/track_packages.py`: Bisection comparison logic
- `tests/`: Comprehensive test coverage for all functionality
