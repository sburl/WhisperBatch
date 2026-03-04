#!/usr/bin/env python3
"""CI secret scanner for obvious credential-like patterns."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
IGNORE_FILES = {
    ".DS_Store",
    ".gitignore",
    "requirements.txt",
}

PATTERNS = {
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_pat": re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "github_oauth": re.compile(r"\bgho_[A-Za-z0-9]{36}\b"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    "api_key_generic": re.compile(r"(?i)\b(api[_-]?key|token|secret)[\"'=:\\s]{0,5}[A-Za-z0-9]{24,}\b"),
}


def _should_skip(path: pathlib.Path) -> bool:
    if any(part in IGNORE_DIRS for part in path.parts):
        return True
    if path.name in IGNORE_FILES:
        return True
    return False


def _scan_file(path: pathlib.Path) -> list[tuple[int, str, str, str]]:
    hits = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    lines = text.splitlines()
    for line_num, line in enumerate(lines, start=1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                hits.append((line_num, label, pattern.pattern, line.strip()))
    return hits


def main() -> int:
    matches = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or _should_skip(path):
            continue
        for line_num, label, pattern, line in _scan_file(path):
            matches.append((path, line_num, label, pattern, line))

    if not matches:
        print("No secrets detected.")
        return 0

    print("Potential secrets found:")
    for path, line_num, label, pattern, line in matches:
        print(f"{path}:{line_num}: {label} ({pattern})")
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
