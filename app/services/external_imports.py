"""
app/services/external_imports.py
================================
Public-link import helpers for the v2.5 attachment sheet.

Supported sources:
- Google Drive public/shared file links
- GitHub blob/raw/archive/release/repository links
"""

from __future__ import annotations

import os
import re
from typing import Tuple
from urllib.parse import parse_qs, unquote, urlparse

import requests
from werkzeug.utils import secure_filename

DEFAULT_TIMEOUT = 45


def _safe_name(name: str, fallback: str = "downloaded-file") -> str:
    cleaned = secure_filename(os.path.basename((name or "").strip()))
    return cleaned or fallback


def _filename_from_headers(resp: requests.Response) -> str | None:
    cd = resp.headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.IGNORECASE)
    if match:
        return _safe_name(unquote(match.group(1)))
    return None


def _read_limited(resp: requests.Response, max_size: int) -> bytes:
    data = bytearray()
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        data.extend(chunk)
        if len(data) > max_size:
            raise ValueError(f"File too large. Max supported size is {max_size // (1024 * 1024)} MB.")
    return bytes(data)


def _google_drive_file_id(url: str) -> str | None:
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
        r"/uc\?export=download&id=([a-zA-Z0-9_-]+)",
        r"/open\?id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _download_google_drive(url: str, max_size: int) -> Tuple[bytes, str, str]:
    file_id = _google_drive_file_id(url)
    if not file_id:
        raise ValueError("Unsupported Google Drive link. Please use a share link to a file, not a folder.")

    session = requests.Session()
    base = "https://drive.google.com/uc?export=download"
    resp = session.get(base, params={"id": file_id}, timeout=DEFAULT_TIMEOUT, stream=True)
    resp.raise_for_status()

    confirm_token = None
    for key, value in resp.cookies.items():
        if key.startswith("download_warning"):
            confirm_token = value
            break

    if confirm_token:
        resp.close()
        resp = session.get(
            base,
            params={"id": file_id, "confirm": confirm_token},
            timeout=DEFAULT_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
    filename = _filename_from_headers(resp) or f"google-drive-{file_id}"
    payload = _read_limited(resp, max_size)
    return payload, filename, content_type


def _github_repo_zip_url(owner: str, repo: str) -> tuple[str, str]:
    meta = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        timeout=DEFAULT_TIMEOUT,
        headers={"Accept": "application/vnd.github+json"},
    )
    meta.raise_for_status()
    data = meta.json()
    branch = data.get("default_branch") or "main"
    return f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}", f"{repo}-{branch}.zip"


def _normalize_github(url: str) -> tuple[str, str | None]:
    parsed = urlparse(url)
    if parsed.netloc == "raw.githubusercontent.com":
        return url, None

    if parsed.netloc != "github.com":
        raise ValueError("Unsupported GitHub URL.")

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 5 and parts[2] == "blob":
        owner, repo, _, branch = parts[:4]
        rest = "/".join(parts[4:])
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rest}"
        return raw, os.path.basename(rest)

    if len(parts) >= 4 and parts[2] == "raw":
        owner, repo = parts[:2]
        rest = "/".join(parts[3:])
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{rest}"
        return raw, os.path.basename(rest)

    if len(parts) >= 4 and parts[2] == "releases" and parts[3] == "download":
        return url, os.path.basename(parts[-1])

    if len(parts) >= 4 and parts[2] == "archive":
        return url, os.path.basename(parts[-1])

    if len(parts) >= 2:
        owner, repo = parts[:2]
        zip_url, suggested = _github_repo_zip_url(owner, repo.removesuffix('.git'))
        return zip_url, suggested

    raise ValueError("Unsupported GitHub URL.")


def _download_github(url: str, max_size: int) -> Tuple[bytes, str, str]:
    final_url, suggested_name = _normalize_github(url)
    resp = requests.get(final_url, timeout=DEFAULT_TIMEOUT, stream=True, allow_redirects=True)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
    filename = _filename_from_headers(resp) or suggested_name or os.path.basename(urlparse(resp.url).path) or "github-download"
    payload = _read_limited(resp, max_size)
    return payload, _safe_name(filename), content_type


def download_external_file(provider: str, url: str, max_size: int) -> Tuple[bytes, str, str]:
    provider = (provider or "").strip().lower()
    if provider == "gdrive":
        return _download_google_drive(url, max_size)
    if provider == "github":
        return _download_github(url, max_size)
    raise ValueError("Unsupported provider.")
