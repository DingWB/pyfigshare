"""Basic tests for pyfigshare. Uses `responses` to mock the figshare HTTP API.

Run with: `pytest -q`
"""
import hashlib
import json
import os
from pathlib import Path
from unittest import mock

import pytest
import responses

from pyfigshare.figshare import Figshare


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_token(tmp_path, monkeypatch):
    """Point ~/.figshare at a temp dir so tests don't touch real config."""
    home = tmp_path / "home"
    (home / ".figshare").mkdir(parents=True)
    (home / ".figshare" / "token").write_text("fake-token")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FIGSHARE_TOKEN", raising=False)
    return "fake-token"


@pytest.fixture
def fs(fake_token):
    return Figshare(token="fake-token", upload_workers=1, max_retries=0)


# --------------------------------------------------------------------------- #
# __init__ validation
# --------------------------------------------------------------------------- #
def test_init_rejects_bad_chunk_size(fake_token):
    with pytest.raises(ValueError):
        Figshare(token="t", chunk_size=0)


def test_init_rejects_bad_workers(fake_token):
    with pytest.raises(ValueError):
        Figshare(token="t", upload_workers=0)


def test_init_rejects_bad_retries(fake_token):
    with pytest.raises(ValueError):
        Figshare(token="t", max_retries=-1)


def test_init_requires_token(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("FIGSHARE_TOKEN", raising=False)
    with pytest.raises(ValueError):
        Figshare(token=None)


def test_init_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("FIGSHARE_TOKEN", "from-env")
    fs = Figshare(token=None)
    assert fs.token == "from-env"


def test_init_does_not_write_token_file(monkeypatch, tmp_path):
    """Library must not silently persist a passed-in token."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FIGSHARE_TOKEN", raising=False)
    Figshare(token="explicit")
    assert not (home / ".figshare" / "token").exists()


# --------------------------------------------------------------------------- #
# md5 / size helper
# --------------------------------------------------------------------------- #
def test_get_file_check_data(fs, tmp_path):
    p = tmp_path / "data.bin"
    payload = b"hello\nworld\n"
    p.write_bytes(payload)
    md5, size = fs.get_file_check_data(str(p))
    assert size == len(payload)
    assert md5 == hashlib.md5(payload).hexdigest()


# --------------------------------------------------------------------------- #
# initiate_new_upload: skip / md5-skip / overwrite
# --------------------------------------------------------------------------- #
def _make_local_file(tmp_path, name, content=b"abc"):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_initiate_skips_when_existing_and_no_overwrite(fs, tmp_path):
    p = _make_local_file(tmp_path, "f.txt")
    fs.existed_files = {"f.txt": {"id": 1, "md5": "different", "size": 999}}
    assert fs.initiate_new_upload(123, str(p), overwrite=False) is None


def test_initiate_skips_identical_md5_on_overwrite(fs, tmp_path):
    payload = b"identical-payload"
    p = _make_local_file(tmp_path, "f.txt", payload)
    md5 = hashlib.md5(payload).hexdigest()
    fs.existed_files = {"f.txt": {"id": 1, "md5": md5, "size": len(payload)}}
    assert fs.initiate_new_upload(123, str(p), overwrite=True) is None


@responses.activate
def test_initiate_overwrite_deletes_then_creates(fs, tmp_path):
    payload = b"new content"
    p = _make_local_file(tmp_path, "f.txt", payload)
    fs.existed_files = {"f.txt": {"id": 7, "md5": "old", "size": 1}}

    responses.add(
        responses.DELETE,
        "https://api.figshare.com/v2/account/articles/123/files/7",
        status=204,
    )
    responses.add(
        responses.POST,
        "https://api.figshare.com/v2/account/articles/123/files",
        json={"location": "https://api.figshare.com/v2/account/articles/123/files/8"},
        status=201,
    )
    responses.add(
        responses.GET,
        "https://api.figshare.com/v2/account/articles/123/files/8",
        json={"id": 8, "name": "f.txt", "upload_url": "https://upload/svc"},
        status=200,
    )

    info = fs.initiate_new_upload(123, str(p), overwrite=True)
    assert info["id"] == 8
    assert "f.txt" not in fs.existed_files


def test_initiate_returns_false_for_empty_file(fs, tmp_path):
    p = _make_local_file(tmp_path, "empty.txt", b"")
    assert fs.initiate_new_upload(123, str(p)) is False


# --------------------------------------------------------------------------- #
# Retry behaviour on parts
# --------------------------------------------------------------------------- #
@responses.activate
def test_part_retries_on_5xx_then_succeeds(fake_token):
    fs = Figshare(token="t", upload_workers=1, max_retries=3, retry_backoff=0.0)
    url = "https://upload/svc/1"
    responses.add(responses.PUT, url, status=503)
    responses.add(responses.PUT, url, status=503)
    responses.add(responses.PUT, url, status=200)
    fs._put_part_with_retry(url, b"x", part_no=1)
    assert len(responses.calls) == 3


@responses.activate
def test_part_does_not_retry_on_4xx(fake_token):
    fs = Figshare(token="t", upload_workers=1, max_retries=3, retry_backoff=0.0)
    url = "https://upload/svc/1"
    responses.add(responses.PUT, url, status=403)
    with pytest.raises(Exception):
        fs._put_part_with_retry(url, b"x", part_no=1)
    assert len(responses.calls) == 1


# --------------------------------------------------------------------------- #
# check_files populates the cache as a dict-of-dicts
# --------------------------------------------------------------------------- #
@responses.activate
def test_check_files_populates_cache(fake_token):
    fs = Figshare(token="t", upload_workers=1, max_retries=0)
    responses.add(
        responses.GET,
        "https://api.figshare.com/v2/account/articles/42",
        json={
            "files": [
                {"id": 1, "name": "a.txt", "computed_md5": "aa", "size": 10},
                {"id": 2, "name": "b/c.txt", "supplied_md5": "bb", "size": 20},
            ],
        },
        status=200,
    )
    fs.check_files(42)
    assert fs.existed_files == {
        "a.txt": {"id": 1, "md5": "aa", "size": 10},
        "b/c.txt": {"id": 2, "md5": "bb", "size": 20},
    }
