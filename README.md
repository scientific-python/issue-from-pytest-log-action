# issue-from-pytest-log

Create an issue for failed tests from a [pytest-reportlog](https://github.com/pytest-dev/pytest-reportlog) file or update an existing one if it already exists.

How this works:

1. `pytest-reportlog` writes a complete and machine-readable log of failed tests.
2. The action extracts the failed tests and creates a report while making sure that it fits into the character limits of github issue forms.
3. The action looks for existing open issues with the configured title and label
   a. if one exists: replace the old description with the report
   b. if there is none: open a new issue and insert the report

## Usage

To use the `issue-from-pytest-log` action in workflows, simply add a new step:

> [!WARNING]
> The action won't run properly unless the `issues: write` permission is requested as shown below.

```yaml
jobs:
  my-job:
    ...
    strategy:
      fail-fast: false
      ...

    permissions:
      issues: write

    ...

    - uses: actions/setup-python@v4
      with:
        python-version: "3.12"
        cache: pip

    ...

    - run: |
        pip install --upgrade pytest-reportlog

    ...

    - run: |
        pytest --report-log pytest-log.jsonl

    ...

    - uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43  # v1.3.0
      if: |
        failure()
        && ...
      with:
        log-path: pytest-log.jsonl
```

See [this repository](https://github.com/keewis/reportlog-test/issues) for example issues. For more realistic examples, see

- `xarray` ([workflow](https://github.com/pydata/xarray/blob/main/.github/workflows/upstream-dev-ci.yaml), [example issue](https://github.com/pydata/xarray/issues/6197))
- `dask` ([workflow](https://github.com/dask/dask/blob/main/.github/workflows/upstream.yml), [example issue](https://github.com/dask/dask/issues/10089))

## Options

### log path

required.

Use `log-path` to specify where the output of `pytest-reportlog` is.

### issue title

optional. Default: `⚠️ Nightly upstream-dev CI failed ⚠️`

In case you don't like the default title for new issues, this setting can be used to set a different one:

```yaml
- uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
  with:
    log-path: pytest-log.jsonl
    issue-title: "Nightly CI failed"
```

The title can also be parametrized, in which case a separate issue will be opened for each variation of the title.

### issue label

optional. Default: `CI`

The label to set on the new issue.

```yaml
- uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
  with:
    log-path: pytest-log.jsonl
    issue-label: "CI"
```

### assignees

optional

Any assignees to set on the new issue:

```yaml
- uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
  with:
    log-path: pytest-log.jsonl
    assignees: ["user1", "user2"]
```

Note that assignees must have the commit bit on the repository.

## Bisection Feature

The action can track package versions between successful and failed CI runs to help identify which dependency changes might have caused test failures.

### track-packages

optional

Comma-separated list of packages to track for bisection analysis. Use `"all"` to track all installed packages:

```yaml
- uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
  with:
    log-path: pytest-log.jsonl
    track-packages: "xarray,pandas,numpy"
```

Or track all packages:

```yaml
- uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
  with:
    log-path: pytest-log.jsonl
    track-packages: "all"
```

### python-command

optional. Default: `"python"`

Command to invoke Python in the test environment. This ensures package versions are captured from the same environment that ran the tests:

```yaml
- uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
  with:
    log-path: pytest-log.jsonl
    track-packages: "xarray,pandas,numpy"
    python-command: "python3"
```

### bisect-storage-method

optional. Default: `"branch"`

Storage method for bisection data. Currently only `"branch"` is supported.

### bisect-branch

optional. Default: `"bisect-data"`

Branch name for storing bisection data when using branch storage method.

### Setting up Bisection

To use the bisection feature, run the action with `track-packages` specified. The action will automatically store both package versions and test results for every run, and generate bisection analysis when tests fail.

#### Standard Python/pip Setup

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: write # Needed for bisection branch

    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0 # Needed for bisection branch operations

      - uses: actions/setup-python@v4
        with:
          python-version: "3.12"

      - run: |
          pip install --upgrade pytest-reportlog

      - run: |
          pytest --report-log pytest-log.jsonl

      # Track package versions and create issue if tests fail
      - name: Track packages and create issue if needed
        if: always() # Run regardless of test outcome to store data
        uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
        with:
          log-path: pytest-log.jsonl
          track-packages: "xarray,pandas,numpy"
          python-command: "python" # Default, can be omitted
```

#### Conda/Mamba Setup

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: conda-incubator/setup-miniconda@v2
        with:
          auto-update-conda: true
          python-version: "3.12"

      - name: Install dependencies
        shell: bash -l {0}
        run: |
          conda install pytest pytest-reportlog numpy pandas

      - name: Run tests
        shell: bash -l {0}
        run: |
          pytest --report-log pytest-log.jsonl

      - name: Track packages and create issue if needed
        if: always()
        uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
        with:
          log-path: pytest-log.jsonl
          track-packages: "numpy,pandas,pytest"
          python-command: "python" # Conda python is already in PATH
```

#### UV Setup

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v1

      - name: Run tests
        run: |
          uv run pytest --report-log pytest-log.jsonl

      - name: Track packages and create issue if needed
        if: always()
        uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
        with:
          log-path: pytest-log.jsonl
          track-packages: "all" # Track all packages
          python-command: "uv run python"
```

#### Poetry Setup

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v4
        with:
          python-version: "3.12"

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Run tests
        run: |
          poetry run pytest --report-log pytest-log.jsonl

      - name: Track packages and create issue if needed
        if: always()
        uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
        with:
          log-path: pytest-log.jsonl
          track-packages: "numpy,pandas,pytest"
          python-command: "poetry run python"
```

#### Pixi Setup

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: prefix-dev/setup-pixi@v0.3.0

      - name: Run tests
        run: |
          pixi run pytest --report-log pytest-log.jsonl

      - name: Track packages and create issue if needed
        if: always()
        uses: scientific-python/issue-from-pytest-log-action@f94477e45ef40e4403d7585ba639a9a3bcc53d43 # v1.3.0
        with:
          log-path: pytest-log.jsonl
          track-packages: "numpy,pandas,pytest"
          python-command: "pixi run python"
```

When enabled, the bisection feature will add comprehensive analysis to GitHub issues:

```
## tests/test_plotting.py::test_plot_basic

### Package changes since last pass
- matplotlib: 3.8.0 → 3.9.0
- numpy: 1.24.0 → 1.25.0

### Code changes since last pass
- a1b2c3d4 (Fix plotting bug in core module for edge cases...)
- → e5f6g7h8 (Update dependencies and refactor plotting tests...)
- Last passed in run #120 on 2024-01-15T10:30:00Z

## tests/test_io.py::test_read_netcdf[dataset1]

### Package changes since last pass
- xarray: 2024.01.0 → 2024.02.0
- netcdf4: 1.6.0 → 1.6.1

### Code changes since last pass
- f9a8b7c6 (Add netcdf4 compatibility layer for new datasets...)
- → e5f6g7h8 (Update dependencies and refactor plotting tests...)
- Last passed in run #118 on 2024-01-14T14:22:00Z

## tests/test_core.py::test_merge_datasets

### Analysis
- No recent successful run found for this test
```

This enhanced bisection feature helps identify:

1. **For each failing test**, exactly which dependencies and code changed since it last passed
2. **Precise correlation** between specific changes and test failures
3. **Historical context** with exact commits and timestamps
4. **Actionable debugging information** organized by failing test
