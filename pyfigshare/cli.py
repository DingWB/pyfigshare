# -*- coding: utf-8 -*-
"""Argparse-based command-line interface for pyfigshare.

Replaces the previous ``fire``-based CLI. Usage::

    figshare <subcommand> [options]
    figshare --help
    figshare <subcommand> --help
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from loguru import logger

from .figshare import (
    Figshare,
    _set_log_level,
    upload as upload_func,
    list_files as list_files_func,
    download as download_func,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Arguments shared by every subcommand."""
    p.add_argument("--token", default=None,
                   help="Figshare API token. Falls back to FIGSHARE_TOKEN env var or ~/.figshare/token.")
    p.add_argument("--level", default=None,
                   choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                   help="Log level (default: INFO; overridden by -v / -q).")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Shortcut for --level DEBUG.")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="Shortcut for --level WARNING.")


def _resolve_level(args) -> str:
    if getattr(args, "verbose", False):
        return "DEBUG"
    if getattr(args, "quiet", False):
        return "WARNING"
    return getattr(args, "level", None) or "INFO"


def _make_client(args, *, private: bool = True, **overrides) -> Figshare:
    """Construct a ``Figshare`` client from parsed CLI args."""
    _set_log_level(_resolve_level(args))
    token = args.token or os.environ.get("FIGSHARE_TOKEN")
    kwargs = {"token": token, "private": private}
    kwargs.update(overrides)
    return Figshare(**kwargs)


def _print_json(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


# --------------------------------------------------------------------------- #
# Subcommand handlers
# --------------------------------------------------------------------------- #
def cmd_upload(args: argparse.Namespace) -> int:
    upload_func(
        input_path=args.input_path,
        title=args.title,
        description=args.description,
        token=args.token or os.environ.get("FIGSHARE_TOKEN"),
        output=args.output,
        publish=args.publish,
        threshold=args.threshold,
        chunk_size=args.chunk_size,
        level=_resolve_level(args),
        target_folder=args.target_folder,
        overwrite=args.overwrite,
        upload_workers=args.upload_workers,
        max_retries=args.max_retries,
        file_workers=args.file_workers,
        mid_publish=args.mid_publish,
        dry_run=args.dry_run,
        failed_output=args.failed_output,
        progress=args.progress,
    )
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    download_func(
        article_id=args.article_id,
        private=args.private,
        outdir=args.outdir,
        cpu=args.cpu,
        folder=args.folder,
    )
    return 0


def cmd_list_files(args: argparse.Namespace) -> int:
    list_files_func(
        article_id=args.article_id,
        private=args.private,
        version=args.version,
        output=args.output,
    )
    return 0


def cmd_list_articles(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    articles = fs.list_articles(show=False)
    if args.json:
        _print_json(articles)
        return 0
    sys.stdout.write("id\ttitle\turl\n")
    for a in articles:
        sys.stdout.write(f"{a.get('id')}\t{a.get('title','')}\t{a.get('url','')}\n")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=args.private)
    res = fs.search_articles(private=args.private, title=args.title)
    if args.json:
        _print_json(res)
        return 0
    sys.stdout.write("id\ttitle\n")
    for a in res:
        sys.stdout.write(f"{a.get('id')}\t{a.get('title','')}\n")
    return 0


def cmd_create_article(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    article_id = fs.create_article(
        title=args.title,
        description=args.description or args.title,
    )
    sys.stdout.write(f"{article_id}\n")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    result = fs.publish(args.article_id)
    if args.json:
        _print_json(result)
    else:
        sys.stdout.write(f"published article_id={args.article_id}\n")
    return 0


def cmd_delete_article(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    if not args.yes:
        sys.stderr.write(
            f"About to DELETE article {args.article_id}. Pass --yes to confirm.\n"
        )
        return 2
    fs.delete_article(args.article_id)
    sys.stdout.write(f"deleted article_id={args.article_id}\n")
    return 0


def cmd_delete_file(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    if not args.yes:
        sys.stderr.write(
            f"About to DELETE file {args.file_id} from article {args.article_id}. "
            "Pass --yes to confirm.\n"
        )
        return 2
    fs.delete_file(args.article_id, args.file_id)
    sys.stdout.write(f"deleted file_id={args.file_id}\n")
    return 0


def cmd_delete_folder(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    if not args.yes:
        sys.stderr.write(
            f"About to DELETE all files under '{args.folder}/' in article "
            f"{args.article_id}. Pass --yes to confirm.\n"
        )
        return 2
    fs.delete_folder(args.article_id, args.folder)
    return 0


def cmd_delete_all_files(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    if not args.yes:
        sys.stderr.write(
            f"About to DELETE ALL files in article {args.article_id}. "
            "Pass --yes to confirm.\n"
        )
        return 2
    fs.delete_all_files(args.article_id)
    return 0


def cmd_quota(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    used = fs.get_used_quota_private()
    sys.stdout.write(f"used_private_quota_GB={used:.3f}\n")
    sys.stdout.write(f"max_private_quota_GB={fs.max_quota}\n")
    return 0


def cmd_account(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=True)
    info = fs.get_account_info()
    _print_json(info)
    return 0


def cmd_get_article(args: argparse.Namespace) -> int:
    fs = _make_client(args, private=args.private)
    info = fs.get_article(args.article_id, version=args.version, private=args.private)
    _print_json(info)
    return 0


def cmd_set_token(args: argparse.Namespace) -> int:
    """Write a token to ~/.figshare/token with mode 0600."""
    token = args.token
    if token is None:
        token = os.environ.get("FIGSHARE_TOKEN")
    if token is None:
        token = sys.stdin.readline().strip()
    if not token:
        sys.stderr.write("error: empty token\n")
        return 2
    path = os.path.expanduser("~/.figshare/token")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(token)
    try:
        os.chmod(path, 0o600)
    except OSError as e:
        sys.stderr.write(f"warning: chmod 600 failed on {path}: {e}\n")
    sys.stdout.write(f"wrote token to {path}\n")
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    try:
        from . import __version__
    except Exception:  # pragma: no cover
        __version__ = "unknown"
    sys.stdout.write(f"pyfigshare {__version__}\n")
    return 0


# --------------------------------------------------------------------------- #
# Parser construction
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="figshare",
        description="Command-line interface for the figshare API (pyfigshare).",
    )
    parser.add_argument("-V", "--version", action="store_true",
                        help="Print version and exit.")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # upload
    p = sub.add_parser("upload", help="Upload files or directories to a figshare article.")
    _add_common_args(p)
    p.add_argument("-i", "--input-path", default="./",
                   help='File, directory, or glob pattern (quote globs, e.g. "./data/*.csv").')
    p.add_argument("-t", "--title", default="title",
                   help="Article title; created if it does not already exist.")
    p.add_argument("-d", "--description", default="description",
                   help="Article description (used only when the article is created).")
    p.add_argument("-o", "--output", default="figshare.tsv",
                   help="TSV file listing uploaded files (default: figshare.tsv).")
    p.add_argument("--target-folder", default=None,
                   help="Optional remote folder prefix to place files under.")
    p.add_argument("--overwrite", action="store_true",
                   help="Overwrite remote files with the same name (md5 match is still skipped).")
    p.add_argument("--no-publish", dest="publish", action="store_false",
                   help="Do NOT publish the article when uploading is finished.")
    p.set_defaults(publish=True)
    p.add_argument("--threshold", type=int, default=18,
                   help="Quota threshold in GB; publish mid-run if exceeded (default: 18).")
    p.add_argument("--chunk-size", type=int, default=20,
                   help="Local read chunk size in MB used for md5/size hashing (default: 20).")
    p.add_argument("-w", "--upload-workers", type=int, default=4,
                   help="Threads used to upload parts of a single file in parallel (default: 4).")
    p.add_argument("-W", "--file-workers", type=int, default=1,
                   help="Concurrent files when input is a directory (default: 1).")
    p.add_argument("--max-retries", type=int, default=5,
                   help="Retries per part on transient errors (default: 5).")
    p.add_argument("--mid-publish", action="store_true",
                   help="Auto-publish article mid-run if used quota crosses --threshold (irreversible).")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be uploaded (path, size, md5) without contacting figshare.")
    p.add_argument("--failed-output", default=None,
                   help="If set, write a TSV of failed (path, error) entries here.")
    p.add_argument("--progress", action="store_true",
                   help="Show tqdm progress bars (requires `pip install pyfigshare[progress]`).")
    p.set_defaults(func=cmd_upload)

    # download
    p = sub.add_parser("download", help="Download all files in a figshare article.")
    _add_common_args(p)
    p.add_argument("article_id", type=int, help="Figshare article ID.")
    p.add_argument("-o", "--outdir", default="./", help="Output directory.")
    p.add_argument("--private", action="store_true",
                   help="Treat as a private article (requires token).")
    p.add_argument("--cpu", type=int, default=1,
                   help="Number of parallel download workers (default: 1).")
    p.add_argument("--folder", default=None,
                   help="Only download files under this top-level folder.")
    p.set_defaults(func=cmd_download)

    # list-files
    p = sub.add_parser("list-files", help="List files in an article.")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("--private", action="store_true")
    p.add_argument("--version", type=int, default=None,
                   help="Article version (public articles only).")
    p.add_argument("-o", "--output", default=None,
                   help="Write to a TSV file instead of stdout.")
    p.set_defaults(func=cmd_list_files)

    # list-articles
    p = sub.add_parser("list-articles", help="List your private articles.")
    _add_common_args(p)
    p.add_argument("--json", action="store_true", help="Output raw JSON.")
    p.set_defaults(func=cmd_list_articles)

    # search
    p = sub.add_parser("search", help="Search articles by title.")
    _add_common_args(p)
    p.add_argument("title", help="Title to search for.")
    p.add_argument("--private", action="store_true",
                   help="Search private articles instead of public.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    # create-article
    p = sub.add_parser("create-article", help="Create a new (empty) private article.")
    _add_common_args(p)
    p.add_argument("title")
    p.add_argument("-d", "--description", default=None)
    p.set_defaults(func=cmd_create_article)

    # publish
    p = sub.add_parser("publish", help="Publish a private article.")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_publish)

    # delete-article
    p = sub.add_parser("delete-article", help="Delete a private article (irreversible).")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("--yes", action="store_true", help="Confirm destructive action.")
    p.set_defaults(func=cmd_delete_article)

    # delete-file
    p = sub.add_parser("delete-file", help="Delete a single file from an article.")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("file_id", type=int)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete_file)

    # delete-folder
    p = sub.add_parser("delete-folder",
                       help="Delete all files whose name starts with FOLDER/.")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("folder")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete_folder)

    # delete-all-files
    p = sub.add_parser("delete-all-files",
                       help="Delete every file in an article (irreversible).")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_delete_all_files)

    # quota
    p = sub.add_parser("quota", help="Show used / max private quota in GB.")
    _add_common_args(p)
    p.set_defaults(func=cmd_quota)

    # account
    p = sub.add_parser("account", help="Print account info as JSON.")
    _add_common_args(p)
    p.set_defaults(func=cmd_account)

    # get-article
    p = sub.add_parser("get-article", help="Fetch article metadata as JSON.")
    _add_common_args(p)
    p.add_argument("article_id", type=int)
    p.add_argument("--private", action="store_true")
    p.add_argument("--version", type=int, default=None)
    p.set_defaults(func=cmd_get_article)

    # set-token
    p = sub.add_parser(
        "set-token",
        help="Save a token to ~/.figshare/token with mode 0600.",
    )
    p.add_argument("--token", default=None,
                   help="Token value (else read FIGSHARE_TOKEN env, else stdin).")
    p.add_argument("--level", default="WARNING",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    p.set_defaults(func=cmd_set_token)

    # version
    p = sub.add_parser("version", help="Print pyfigshare version.")
    p.set_defaults(func=cmd_version)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False) and not getattr(args, "command", None):
        return cmd_version(args)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        return 130
    except Exception as e:
        logger.exception(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
