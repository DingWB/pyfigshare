# Changelog

All notable changes to this project will be documented here. Versions follow
[setuptools_scm](https://github.com/pypa/setuptools_scm) tags from git.

## Unreleased

### Added
- Argparse CLI (`figshare <subcommand>`) with 16 subcommands; `python -m pyfigshare`
  now works.
- `figshare set-token` writes `~/.figshare/token` with mode `0600`.
- `--overwrite` flag on `upload`: identical files (md5+size) are skipped, others
  are deleted and re-uploaded.
- Per-file part-level parallel uploads (`--upload-workers`) with retry +
  exponential backoff on 5xx / 429 / connection errors. Honours `Retry-After`.
- Multi-file parallelism via `--file-workers` for directory uploads.
- `--dry-run` prints `(path, remote_name, size, md5)` without touching figshare.
- `--failed-output` writes a TSV of failed `(path, error)` entries.
- `--progress` shows tqdm progress bars (optional dep: `pip install pyfigshare[progress]`).
- `-v` / `-q` shortcuts for log level on every subcommand.
- `FIGSHARE_TOKEN` env var is honoured everywhere as a fallback for `--token`.
- Persistent `requests.Session` with a connection pool sized to the worker
  count (avoids redundant TLS handshakes).
- `pytest` + `responses`-based test suite (`tests/`).
- `__all__` exported from `pyfigshare`.

### Changed
- `Figshare.__init__` no longer secretly writes the token to
  `~/.figshare/token`; use `figshare set-token` for that.
- `Figshare` no longer reconfigures loguru on import. The CLI sets the level
  explicitly.
- Mid-upload publish on quota threshold is now opt-in (`--mid-publish` /
  `mid_publish=True`); previously it would publish silently.
- `existed_files` now stores `(id, md5, size)` per remote file (was just `id`)
  so `--overwrite` can short-circuit when checksums match.
- HTTP error response bodies in logs are now redacted of the access token.
- Input validation: `chunk_size`, `upload_workers`, `max_retries` now raise
  `ValueError` on bad values instead of silently clamping.

### Removed
- `fire` dependency. Console script entry point unchanged
  (`figshare=pyfigshare:main`).
- `setup.py`. Packaging is fully PEP 621 via `pyproject.toml`.
- Legacy `pyfigshare/figshare_v2.py` (unused alternate implementation).
