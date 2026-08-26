from repofix.schemas import RunState
from repofix.storage import RunStore


def test_run_store_preserves_each_run_and_latest_pointer(tmp_path):
    store = RunStore(str(tmp_path))
    first = RunState("first", str(tmp_path), status="success")
    second = RunState("second", str(tmp_path), status="error")
    store.save(first)
    store.save(second)
    assert (tmp_path / ".repofix" / "runs" / first.run_id / "result.json").exists()
    assert (tmp_path / ".repofix" / "runs" / second.run_id / "result.json").exists()
    assert store.load_latest().run_id == second.run_id


def test_run_state_loads_rollback_evaluation(tmp_path):
    state = RunState("task", str(tmp_path), status="verification_failed")
    state.evaluation.rollback_performed = True
    state.evaluation.rollback_files = ["a.py"]
    store = RunStore(str(tmp_path))
    store.save(state)
    loaded = store.load_latest()
    assert loaded.evaluation.rollback_performed is True
    assert loaded.evaluation.rollback_files == ["a.py"]
