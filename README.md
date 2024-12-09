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
> The action won't run properly unless either `issues: write` permissions are requested as shown below or the actions are granted read/write permissions in the repository settings.

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

    - uses: scientific-python/issue-from-pytest-log-action@main
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
- uses: scientific-python/issue-from-pytest-log-action@main
  with:
    log-path: pytest-log.jsonl
    issue-title: "Nightly CI failed"
```

The title can also be parametrized, in which case a separate issue will be opened for each variation of the title.

### issue label

optional. Default: `CI`

The label to set on the new issue.

```yaml
- uses: scientific-python/issue-from-pytest-log-action@main
  with:
    log-path: pytest-log.jsonl
    issue-label: "CI"
```

### assignees

optional

Any assignees to set on the new issue:

```yaml
- uses: scientific-python/issue-from-pytest-log-action@main
  with:
    log-path: pytest-log.jsonl
    assignees: ["user1", "user2"]
```

Note that assignees must have the commit bit on the repository.
