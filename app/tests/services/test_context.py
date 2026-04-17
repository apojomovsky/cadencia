import pytest

from cadencia.services.context import list_context_docs, read_context_doc, write_context_doc

VALID_DOC = """\
---
type: reference
date: 2026-04-17
title: Test Doc
source: unit-test
---

Body content here.
"""


def test_write_and_read_context(tmp_path: object) -> None:
    ctx_dir = str(tmp_path)
    doc = write_context_doc(ctx_dir, "test.md", VALID_DOC)

    assert doc.filename == "test.md"
    assert doc.valid is True
    assert doc.missing_fields == []
    assert "Body content here." in doc.content


def test_write_context_no_overwrite_by_default(tmp_path: object) -> None:
    ctx_dir = str(tmp_path)
    write_context_doc(ctx_dir, "test.md", VALID_DOC)

    with pytest.raises(FileExistsError):
        write_context_doc(ctx_dir, "test.md", VALID_DOC)


def test_write_context_overwrite(tmp_path: object) -> None:
    ctx_dir = str(tmp_path)
    write_context_doc(ctx_dir, "test.md", VALID_DOC)

    updated = VALID_DOC.replace("Body content here.", "Updated body.")
    doc = write_context_doc(ctx_dir, "test.md", updated, overwrite=True)

    assert "Updated body." in doc.content


def test_write_context_invalid_extension(tmp_path: object) -> None:
    with pytest.raises(ValueError, match=".md"):
        write_context_doc(str(tmp_path), "test.txt", VALID_DOC)


def test_write_context_path_traversal(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="path separators"):
        write_context_doc(str(tmp_path), "../evil.md", VALID_DOC)


def test_write_context_appears_in_list(tmp_path: object) -> None:
    ctx_dir = str(tmp_path)
    write_context_doc(ctx_dir, "alpha.md", VALID_DOC)
    write_context_doc(ctx_dir, "beta.md", VALID_DOC)

    docs = list_context_docs(ctx_dir)
    names = [d.filename for d in docs]
    assert "alpha.md" in names
    assert "beta.md" in names
