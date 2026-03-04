"""Example post-processing plugins for WhisperBatch.

These functions are intentionally small and dependency-free so they can be used as
reference implementations from `--postprocess-plugin`.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact_email_addresses(output_path: str, metadata: Dict[str, Any]) -> None:
    """Redact email-like strings from a transcription output file."""
    path = Path(output_path)
    text = path.read_text(encoding="utf-8")
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    path.write_text(redacted, encoding="utf-8")


def write_plugin_audit(output_path: str, metadata: Dict[str, Any]) -> None:
    """Write a sidecar audit file for plugin execution."""
    path = Path(output_path)
    audit_path = path.with_suffix(path.suffix + ".plugin_audit.json")
    payload = {
        "plugin": "write_plugin_audit",
        "source_path": metadata.get("source_path"),
        "output_path": metadata.get("output_path"),
        "model": metadata.get("model"),
        "task": metadata.get("task"),
        "language": metadata.get("language"),
        "processed_at": metadata.get("processed_at"),
        "output_format": metadata.get("output_format"),
    }
    audit_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

