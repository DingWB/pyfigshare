# pyfigshare

[![PyPI version](https://img.shields.io/pypi/v/pyfigshare.svg)](https://pypi.org/project/pyfigshare/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyfigshare.svg)](https://pypi.org/project/pyfigshare/)
[![License](https://img.shields.io/pypi/l/pyfigshare.svg)](https://github.com/DingWB/pyfigshare/blob/main/LICENSE)

A small Python package and command-line tool for interacting with the
[figshare](https://figshare.com) API: upload files / folders to private
articles, list and download public/private articles, manage quota, and so on.

Highlights:

- Robust uploads with **per-file part-level parallelism** plus optional
  **multi-file parallelism**, and automatic **retry with exponential backoff**
  on transient errors (5xx / 429 / network). Honours `Retry-After`.
- Smart `--overwrite`: identical files (same md5+size) are skipped, different
  files replace the remote one.
- Modern **`argparse` CLI** with discoverable subcommands (no more `fire`).
- Safe destructive operations: every `delete-*` command requires `--yes`.
- Library-friendly: importing `pyfigshare` does **not** mutate your loguru
  configuration or write any files.

## Installation

```bash
pip install pyfigshare
# or from source
pip uninstall -y pyfigshare && pip install git+https://github.com/DingWB/pyfigshare.git
```

Requirements: Python 3.8+, `pandas`, `requests`, `loguru`. For progress bars
(`--progress`), also install `tqdm`. For running the test suite, install
`pytest` and `responses`.

## Setting up your token

Create a personal token at
[figshare → profile → Applications → Create Personal Token](https://figshare.com),
then use any of:

```bash
# 1. preferred: store it in ~/.figshare/token (chmod 600)
figshare set-token --token YOUR_TOKEN

# 2. pipe it
echo YOUR_TOKEN | figshare set-token

# 3. environment variable (per-shell)
export FIGSHARE_TOKEN=YOUR_TOKEN
figshare list-articles

# 4. pass --token to every command
figshare list-articles --token YOUR_TOKEN
```

Resolution order: `--token` flag → `FIGSHARE_TOKEN` env var → `~/.figshare/token`.

`set-token` writes the token to `~/.figshare/token` with permissions `0600`.
If that file already exists with looser permissions, every CLI run will print a
warning.

## Quick start

```bash
# 1. upload a directory to a new (or existing) article called "test1"
figshare upload -i ./test_data --title test1

# 2. upload a glob with 8 parallel part-uploads, overwriting changed files,
#    and don't auto-publish
figshare upload -i "./MajorType/*.allc" \
    --title MajorType -d "MajorType allc files" \
    --upload_workers 8 --overwrite --no_publish

# 3. download a public article
figshare download 9273710 -o ./downloaded

# 4. how full is my private quota?
figshare quota
```

## CLI reference

```text
figshare <subcommand> [options]
figshare --help
figshare <subcommand> --help
```

| Subcommand          | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `upload`            | Upload file / dir / glob to an article (creates if missing). |
| `download`          | Download all files in an article (`--cpu`, `--folder`).      |
| `list-files`        | List files in an article (TSV; `-o` to write to file).       |
| `list-articles`     | List your private articles (`--json`).                       |
| `search`            | Search articles by title (`--private`, `--json`).            |
| `create-article`    | Create an empty private article, prints the new id.          |
| `publish`           | Publish a private article.                                   |
| `delete-article`    | Delete an article. Requires `--yes`.                         |
| `delete-file`       | Delete a single file. Requires `--yes`.                      |
| `delete-folder`     | Delete files under a remote folder. Requires `--yes`.        |
| `delete-all-files`  | Delete every file in an article. Requires `--yes`.           |
| `quota`             | Print used / max private quota in GB.                        |
| `account`           | Print account info as JSON.                                  |
| `get-article`       | Print article metadata as JSON.                              |
| `set-token`         | Save token to `~/.figshare/token` with `chmod 600`.          |
| `version`           | Print package version.                                       |

Common options on every API-using subcommand:

- `--token TOKEN` — override `~/.figshare/token`.
- `--level {DEBUG,INFO,WARNING,ERROR,CRITICAL}` — log level.

### `upload` options

| Flag                       | Default        | Meaning |
| -------------------------- | -------------- | ------- |
| `-i, --input_path`         | `./`           | File, directory, or quoted glob (`"./data/*.csv"`). |
| `-t, --title`              | `title`        | Article title; created if it doesn't exist. |
| `-d, --description`        | `description`  | Used only when creating the article. |
| `-o, --output`             | `figshare.tsv` | TSV with `(name, file_id, url)` for uploaded files. |
| `--target_folder`          | `None`         | Optional remote folder prefix for all uploaded files. |
| `--overwrite`              | off            | Replace remote files of the same name; identical (md5+size) files are still skipped. |
| `--no_publish`             | off            | Do not publish the article when finished. |
| `--threshold`              | `18`           | Quota threshold in GB; only honoured with `--mid_publish`. |
| `--mid_publish`            | off            | Auto-publish article mid-run if quota crosses `--threshold` (irreversible). |
| `--chunk_size`             | `20`           | Local md5/size hashing chunk in MB. |
| `-w, --upload_workers`     | `4`            | **Threads** uploading parts of a single file in parallel (inner pool). |
| `-W, --file_workers`       | `1`            | **Threads** uploading different files concurrently (outer pool); only used when input is a directory. |
| `--max_retries`            | `5`            | Retries per part on 5xx / 429 / connection errors (exp. backoff, honours `Retry-After`). |
| `--dry_run`                | off            | Print `(path, remote_name, size, md5)` without contacting figshare. |
| `--failed_output PATH`     | none           | Write failed `(path, error)` rows to this TSV. |
| `--progress`               | off            | Show tqdm progress bars (requires `pip install tqdm`). |

Every API-using subcommand also supports `-v` (DEBUG) and `-q` (WARNING) log
shortcuts, and reads `FIGSHARE_TOKEN` from the environment as a fallback for
`--token`.

## Python API

```python
from pyfigshare import Figshare, upload, list_files, download

fs = Figshare(token=None,             # or read from ~/.figshare/token
              private=True,
              chunk_size=20,           # MB read chunk for md5
              upload_workers=8,        # threads per file (part-level parallelism)
              max_retries=5)

# create / find article and upload
article_id = fs.create_article(title="my dataset", description="...")
fs.check_files(article_id)             # populate the existed-files cache
fs.upload(article_id, "./data", overwrite=True, file_workers=4)  # 4 files at a time
fs.publish(article_id)

# inspect
print(fs.get_used_quota_private(), "GB used")
for f in fs.list_files(article_id, show=False):
    print(f["name"], f["id"])

# download a public article in parallel (uses processes, not threads)
download(9273710, private=False, outdir="./out", cpu=4)
```

## Notes on uploads

### Concurrency model

Uploads use **two nested layers of threads** (`ThreadPoolExecutor`); processes
are *not* used because the bottleneck is network I/O, not CPU.

- `upload_workers` (inner): threads that PUT the parts of a single file in
  parallel. They share one `requests.Session` so the TLS handshake is reused
  across part PUTs.
- `file_workers` (outer): threads that upload *different files* concurrently
  when the input is a directory. Ignored for single-file uploads.

Total in-flight HTTP PUTs is roughly `file_workers * upload_workers`. Setting
either value too high can trigger figshare's rate limit (HTTP 429); the client
honours `Retry-After` and exponentially backs off, but throughput rarely
improves past a few dozen concurrent connections. A reasonable starting point
for large jobs is `-w 8 -W 4`.

> **Note:** `download(..., cpu=N)` is different — it uses
> `ProcessPoolExecutor` (true processes), since each file is fetched
> independently with `urllib.request.urlretrieve` and there is no shared
> session to benefit from threads.

### Other behaviour

- Failed parts retry with exponential backoff + jitter, and respect the
  server's `Retry-After` header on 429 responses. Non-retriable HTTP errors
  (auth, bad request, etc.) bail out immediately.
- The `existed_files` cache stores `(id, md5, size)` per remote file so that
  `--overwrite` can skip uploads when local and remote checksums match.
- Mid-run `publish` is opt-in via `--mid_publish`. Without it, exceeding the
  20 GB private quota will fail the upload — split your data across multiple
  articles, or pass `--mid_publish --threshold 18` to keep the old behaviour.
- Use `--dry_run` first to see exactly what would be sent.

## Development

```bash
git clone https://github.com/DingWB/pyfigshare
cd pyfigshare
pip install -e .
pip install pytest responses   # for tests
pytest
```

## Links

- figshare API docs: <https://docs.figshare.com>
- API how-to: <https://help.figshare.com/article/how-to-use-the-figshare-api>
