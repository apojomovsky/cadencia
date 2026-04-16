"""Context document discovery and reading with frontmatter validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Required fields per document type
_REQUIRED: dict[str, list[str]] = {
    "transcript": ["type", "date", "title", "participants", "topic"],
    "email": ["type", "date", "title", "participants", "subject"],
    "process": ["type", "date", "title", "applies_to"],
    "spreadsheet": ["type", "date", "title", "description"],
    "reference": ["type", "date", "title", "source"],
}


@dataclass
class ContextDocSummary:
    filename: str
    valid: bool
    metadata: dict[str, Any]
    missing_fields: list[str]


@dataclass
class ContextDoc:
    filename: str
    valid: bool
    metadata: dict[str, Any]
    missing_fields: list[str]
    content: str


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Return (metadata_dict, body). Body is everything after the closing ---."""
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return {}, raw
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == "---":
            end = i
            break
    if end is None:
        return {}, raw
    meta: dict[str, Any] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    body = "".join(lines[end + 1 :]).lstrip("\n")
    return meta, body


def _missing_fields(meta: dict[str, Any]) -> list[str]:
    doc_type = meta.get("type", "").lower()
    required = _REQUIRED.get(doc_type, ["type", "date", "title"])
    return [f for f in required if not meta.get(f)]


def list_context_docs(context_dir: str) -> list[ContextDocSummary]:
    """Return metadata summaries for all files under context_dir."""
    results: list[ContextDocSummary] = []
    if not os.path.isdir(context_dir):
        return results
    for entry in sorted(os.scandir(context_dir), key=lambda e: e.name):
        if not entry.is_file():
            continue
        try:
            raw = entry.path
            with open(raw, encoding="utf-8", errors="replace") as fh:
                content = fh.read(65536)
        except OSError:
            continue
        meta, _ = _parse_frontmatter(content)
        missing = _missing_fields(meta)
        results.append(
            ContextDocSummary(
                filename=entry.name,
                valid=len(missing) == 0,
                metadata=meta,
                missing_fields=missing,
            )
        )
    return results


def read_context_doc(context_dir: str, filename: str) -> ContextDoc:
    """Read a single context document and return its metadata and body."""
    # Prevent path traversal
    safe_name = os.path.basename(filename)
    path = os.path.join(context_dir, safe_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Context document not found: {safe_name}")
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    meta, body = _parse_frontmatter(raw)
    missing = _missing_fields(meta)
    return ContextDoc(
        filename=safe_name,
        valid=len(missing) == 0,
        metadata=meta,
        missing_fields=missing,
        content=body,
    )
