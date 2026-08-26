import json

import pytest

from repofix.tools import ToolRuntime
from repofix.workspace import WorkspaceJournal


def make_runtime(tmp_path, max_changed_files=5):
    journal = WorkspaceJournal(
        str(tmp_path), tmp_path / ".repofix" / "runs" / "test" / "workspace", max_changed_files
    )
    return ToolRuntime(str(tmp_path), journal=journal), journal


def test_journal_restores_existing_file_and_removes_created_file(tmp_path):
    original = tmp_path / "existing.py"
    original.write_text("original\n", encoding="utf-8")
    runtime, journal = make_runtime(tmp_path)

    assert runtime.execute("apply_patch", {"path": "existing.py", "content": "changed\n"}).success
    assert runtime.execute("apply_patch", {"path": "new.py", "content": "created\n"}).success
    restored = journal.rollback()

    assert restored == ["existing.py", "new.py"]
    assert original.read_text(encoding="utf-8") == "original\n"
    assert not (tmp_path / "new.py").exists()
    manifest = json.loads(journal.manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"]["existing.py"]["before_sha256"]
    assert manifest["files"]["existing.py"]["after_sha256"]
    assert manifest["files"]["new.py"]["existed"] is False
    assert manifest["rolled_back_at"]


def test_changed_file_limit_blocks_another_file(tmp_path):
    (tmp_path / "a.py").write_text("a\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("b\n", encoding="utf-8")
    runtime, journal = make_runtime(tmp_path, max_changed_files=1)

    first = runtime.execute("apply_patch", {"path": "a.py", "content": "changed a\n"})
    second = runtime.execute("apply_patch", {"path": "b.py", "content": "changed b\n"})

    assert first.success
    assert not second.success
    assert "changed file limit" in second.output
    assert journal.tracked_files() == ["a.py"]
    assert (tmp_path / "b.py").read_text(encoding="utf-8") == "b\n"


def test_same_file_can_be_edited_multiple_times_with_one_snapshot(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("original\n", encoding="utf-8")
    runtime, journal = make_runtime(tmp_path, max_changed_files=1)

    runtime.execute("apply_patch", {"path": "a.py", "content": "first\n"})
    runtime.execute("apply_patch", {"path": "a.py", "content": "second\n"})
    journal.rollback()

    assert path.read_text(encoding="utf-8") == "original\n"


def test_unchanged_write_does_not_consume_file_limit(tmp_path):
    (tmp_path / "a.py").write_bytes(b"same\n")
    (tmp_path / "b.py").write_text("old\n", encoding="utf-8")
    runtime, journal = make_runtime(tmp_path, max_changed_files=1)

    unchanged = runtime.execute("apply_patch", {"path": "a.py", "content": "same\n"})
    changed = runtime.execute("apply_patch", {"path": "b.py", "content": "new\n"})

    assert unchanged.metadata["changed"] is False
    assert changed.success
    assert journal.tracked_files() == ["b.py"]


def test_missing_backup_is_detected_before_any_file_is_restored(tmp_path):
    (tmp_path / "a.py").write_bytes(b"original a\n")
    (tmp_path / "b.py").write_bytes(b"original b\n")
    runtime, journal = make_runtime(tmp_path)
    runtime.execute("apply_patch", {"path": "a.py", "content": "changed a\n"})
    runtime.execute("apply_patch", {"path": "b.py", "content": "changed b\n"})
    missing_name = journal.manifest["files"]["b.py"]["backup"]
    (journal.backup_dir / missing_name).unlink()

    with pytest.raises(FileNotFoundError, match="backup missing"):
        journal.rollback(force=True)

    assert (tmp_path / "a.py").read_bytes() == b"changed a\n"
    assert (tmp_path / "b.py").read_bytes() == b"changed b\n"
