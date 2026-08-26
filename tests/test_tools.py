from repofix.tools import ToolRuntime

def test_read_and_search(tmp_path):
    (tmp_path / "a.py").write_text("def hello(): pass\n", encoding="utf-8")
    t = ToolRuntime(str(tmp_path)); assert "hello" in t.execute("search", {"query": "hello"}).output
    assert "def hello" in t.execute("read", {"path": "a.py"}).output

def test_path_cannot_escape(tmp_path):
    t = ToolRuntime(str(tmp_path))
    result = t.execute("read", {"path": "../outside.txt"})
    assert not result.success


def test_list_hides_control_directories(tmp_path):
    (tmp_path / "visible.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / ".repofix").mkdir()
    (tmp_path / ".repofix" / "trace.json").write_text("{}", encoding="utf-8")
    output = ToolRuntime(str(tmp_path)).execute("list", {}).output
    assert "visible.py" in output
    assert ".repofix" not in output


def test_read_supports_line_ranges(tmp_path):
    (tmp_path / "a.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    result = ToolRuntime(str(tmp_path)).execute(
        "read", {"path": "a.py", "start_line": 2, "end_line": 3}
    )
    assert result.output == "two\nthree"


def test_write_to_control_directory_is_denied(tmp_path):
    result = ToolRuntime(str(tmp_path)).execute(
        "apply_patch", {"path": ".git/config", "content": "unsafe"}
    )
    assert not result.success
    assert "control directories" in result.output


def test_apply_patch_records_content_hashes(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("old\n", encoding="utf-8")
    result = ToolRuntime(str(tmp_path)).execute(
        "apply_patch", {"path": "a.py", "content": "new\n"}
    )
    assert result.success
    assert result.metadata["changed"] is True
    assert result.metadata["before_sha256"] != result.metadata["after_sha256"]


def test_non_pytest_command_is_denied(tmp_path):
    result = ToolRuntime(str(tmp_path)).execute(
        "run_command", {"command": "python dangerous.py"}
    )
    assert not result.success
    assert "only pytest" in result.output


def test_pytest_cannot_target_parent_directory(tmp_path):
    result = ToolRuntime(str(tmp_path)).execute(
        "run_command", {"command": "pytest ../other_repo"}
    )
    assert not result.success
    assert "inside the repository" in result.output
