"""
app/utils/artifacts.py
======================
Artifact helpers for returning AI-generated code with user-friendly names.
"""

from __future__ import annotations

import os
import re
import time
import zipfile
from typing import Any

from werkzeug.utils import secure_filename

LANG_EXTENSIONS: dict[str, str] = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "html": ".html", "css": ".css",
    "java": ".java", "c": ".c",
    "cpp": ".cpp", "c++": ".cpp", "csharp": ".cs",
    "go": ".go", "rust": ".rs", "ruby": ".rb",
    "php": ".php", "sql": ".sql", "swift": ".swift",
    "kotlin": ".kt", "dart": ".dart", "r": ".r",
    "bash": ".sh", "sh": ".sh", "shell": ".sh",
    "json": ".json", "yaml": ".yml", "yml": ".yml",
    "xml": ".xml", "markdown": ".md", "md": ".md",
    "txt": ".txt", "text": ".txt", "": ".txt",
}

_NAME_PATTERNS = [
    r'(?:save as|named|called|file name|filename|name it|zip name|project name)\s+["“]?([^"”\n]+)',
    r'["“]([^"”\n]+\.(?:zip|py|js|ts|tsx|jsx|html|css|json|md|txt|sql|csv|yml|yaml|xml))["”]',
]


def _clean_name(value: str, fallback: str = "download") -> str:
    value = (value or "").strip().strip("`'\"")
    value = value.split("/download", 1)[0].strip()
    cleaned = secure_filename(os.path.basename(value))
    return cleaned or fallback


def extract_requested_artifact_name(message: str) -> str | None:
    if not message:
        return None
    for pattern in _NAME_PATTERNS:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return _clean_name(match.group(1))
    return None


def _guess_extension(block: dict[str, Any]) -> str:
    return LANG_EXTENSIONS.get((block.get("language") or "").lower(), ".txt")


def _usable_blocks(code_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable: list[dict[str, Any]] = []
    for i, block in enumerate(code_blocks):
        lang = (block.get("language") or "").lower()
        if lang in {"output", "terminal", "console"}:
            continue
        code = block.get("code") or ""
        if not code.strip():
            continue
        filename = block.get("filename")
        if not filename and code.count("\n") >= 5:
            filename = f"main{_guess_extension(block)}"
        if filename:
            block = dict(block)
            block["filename"] = filename
            usable.append(block)
    return usable


def build_code_download_artifact(code_blocks: list[dict[str, Any]], requested_name: str | None = None) -> dict[str, Any] | None:
    blocks = _usable_blocks(code_blocks)
    if not blocks:
        return None

    requested_name = _clean_name(requested_name or "", fallback="") or None
    timestamp = int(time.time())

    # Single-file response: return the exact filename whenever possible.
    if len(blocks) == 1:
        block = blocks[0]
        original_name = _clean_name(block.get("filename") or "", fallback="main")
        ext = os.path.splitext(original_name)[1] or _guess_extension(block)
        if requested_name and not requested_name.lower().endswith(".zip"):
            final_name = requested_name
            if not os.path.splitext(final_name)[1]:
                final_name += ext
        else:
            final_name = original_name
        if "/" not in (block.get("filename") or "") and "\\" not in (block.get("filename") or ""):
            path = os.path.join("/tmp", final_name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(block.get("code") or "")
            return {
                "kind": "file",
                "filename": final_name,
                "path": path,
                "url": f"/download-generated/{final_name}",
                "files": [final_name],
            }

    # Multi-file (or nested path) response: create a properly named zip.
    if requested_name and requested_name.lower().endswith(".zip"):
        zip_name = requested_name
    elif requested_name:
        base = os.path.splitext(requested_name)[0]
        zip_name = f"{base}.zip"
    else:
        top_names = [os.path.normpath(b["filename"]).split(os.sep)[0] for b in blocks if b.get("filename")]
        base = _clean_name(top_names[0] if top_names else "project", fallback="project")
        zip_name = f"{os.path.splitext(base)[0]}.zip"

    zip_name = _clean_name(zip_name, fallback=f"project_{timestamp}.zip")
    zip_path = os.path.join("/tmp", zip_name)
    used_names: set[str] = set()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, block in enumerate(blocks, start=1):
            raw_name = (block.get("filename") or f"file_{i}{_guess_extension(block)}").replace("\\", "/")
            zip_member = raw_name.strip("/")
            if not zip_member:
                zip_member = f"file_{i}{_guess_extension(block)}"
            candidate = zip_member
            suffix = 2
            while candidate in used_names:
                stem, ext = os.path.splitext(zip_member)
                candidate = f"{stem}_{suffix}{ext}"
                suffix += 1
            used_names.add(candidate)
            zf.writestr(candidate, block.get("code") or "")

    return {
        "kind": "zip",
        "filename": zip_name,
        "path": zip_path,
        "url": f"/download-generated/{zip_name}",
        "files": sorted(used_names),
    }
