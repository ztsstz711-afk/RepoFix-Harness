from repofix.schemas import Action
from repofix.stability import RepeatedActionGuard


def event(action: Action, changed: bool = False) -> dict:
    return {
        "action": {"name": action.name, "arguments": action.arguments, "rationale": action.rationale},
        "observation": {"metadata": {"changed": changed}},
    }


def test_third_identical_action_is_stalled():
    action = Action("read", {"path": "a.py"})
    guard = RepeatedActionGuard(max_identical_actions=2)
    assert guard.reason([event(action), event(action)], action) is not None


def test_real_patch_resets_repetition_window():
    action = Action("read", {"path": "a.py"})
    patch = Action("apply_patch", {"path": "a.py", "content": "new"})
    history = [event(action), event(action), event(patch, changed=True), event(action)]
    assert RepeatedActionGuard(2).reason(history, action) is None


def test_finish_is_never_blocked():
    action = Action("finish", {"summary": "done"})
    assert RepeatedActionGuard(1).reason([event(action)], action) is None
