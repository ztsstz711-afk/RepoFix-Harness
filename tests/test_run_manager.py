import json

import pytest

from repofix.run_manager import RunManager
from repofix.schemas import RunState
from repofix.storage import RunStore
from repofix.tools import ToolRuntime
from repofix.workspace import WorkspaceConflictError, WorkspaceJournal


def create_changed_run(repo, status="success"):
    state = RunState("repair task", str(repo), status=status, model="mock-model", step=3)
    journal = WorkspaceJournal(
        str(repo), repo / ".repofix" / "runs" / state.run_id / "workspace"
    )
    runtime = ToolRuntime(str(repo), journal=journal)
    result = runtime.execute("apply_patch", {"path": "a.py", "content": "changed\n"})
    assert result.success
    state.evaluation.changed_files = ["a.py"]
    RunStore(str(repo)).save(state)
    return state


def test_manager_lists_shows_and_rolls_back_run(tmp_path):
    (tmp_path / "a.py").write_bytes(b"original\n")
    state = create_changed_run(tmp_path)
    manager = RunManager(str(tmp_path))

    listed = manager.list_runs()
    shown = manager.show(state.run_id)
    restored = manager.rollback(state.run_id)

    assert listed[0]["run_id"] == state.run_id
    assert shown.task == "repair task"
    assert restored.evaluation.rollback_performed is True
    assert restored.evaluation.rollback_files == ["a.py"]
    assert (tmp_path / "a.py").read_bytes() == b"original\n"
    assert manager.show("latest").evaluation.rollback_performed is True


def test_manual_rollback_refuses_external_changes_without_force(tmp_path):
    (tmp_path / "a.py").write_bytes(b"original\n")
    state = create_changed_run(tmp_path)
    (tmp_path / "a.py").write_bytes(b"user edit\n")
    manager = RunManager(str(tmp_path))

    with pytest.raises(WorkspaceConflictError, match="changed after"):
        manager.rollback(state.run_id)
    assert (tmp_path / "a.py").read_bytes() == b"user edit\n"

    manager.rollback(state.run_id, force=True)
    assert (tmp_path / "a.py").read_bytes() == b"original\n"


def test_manual_rollback_cannot_repeat_without_new_agent_write(tmp_path):
    (tmp_path / "a.py").write_bytes(b"original\n")
    state = create_changed_run(tmp_path)
    manager = RunManager(str(tmp_path))
    manager.rollback(state.run_id)
    with pytest.raises(ValueError, match="already been rolled back"):
        manager.rollback(state.run_id)


def test_rolling_back_older_run_does_not_replace_latest_pointer(tmp_path):
    (tmp_path / "a.py").write_bytes(b"original\n")
    older = create_changed_run(tmp_path)
    latest = RunState("newer task", str(tmp_path), status="error")
    RunStore(str(tmp_path)).save(latest)

    RunManager(str(tmp_path)).rollback(older.run_id)

    assert RunStore(str(tmp_path)).load_latest().run_id == latest.run_id


def test_run_summary_is_json_serializable(tmp_path):
    state = RunState("task", str(tmp_path), status="success")
    summary = RunManager.summary(state)
    assert json.loads(json.dumps(summary))["run_id"] == state.run_id
