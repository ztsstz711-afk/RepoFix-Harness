from repofix.tools import ToolRuntime

def test_read_and_search(tmp_path):
    (tmp_path / "a.py").write_text("def hello(): pass\n", encoding="utf-8")
    t = ToolRuntime(str(tmp_path)); assert "hello" in t.execute("search", {"query": "hello"}).output
    assert "def hello" in t.execute("read", {"path": "a.py"}).output

def test_path_cannot_escape(tmp_path):
    t = ToolRuntime(str(tmp_path))
    result = t.execute("read", {"path": "../outside.txt"})
    assert not result.success
