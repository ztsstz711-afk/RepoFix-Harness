import shutil
import subprocess
import sys

import pytest

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


def test_list_prioritizes_shallow_source_paths_and_bounds_large_trees(tmp_path):
    source = tmp_path / "src" / "package" / "parser.py"
    source.parent.mkdir(parents=True)
    source.write_text("def parse(): pass\n", encoding="utf-8")
    data = tmp_path / "tests" / "data" / "external" / "fixtures"
    data.mkdir(parents=True)
    for number in range(300):
        (data / f"fixture_{number:03}.toml").write_text("value = 1\n", encoding="utf-8")

    result = ToolRuntime(str(tmp_path)).execute("list", {})

    assert len(result.output) <= 4_000
    assert "src\\package\\parser.py" in result.output or "src/package/parser.py" in result.output
    assert "files omitted" in result.output
    assert result.metadata["total_files"] == 301
    assert result.metadata["shown_files"] < result.metadata["total_files"]
    assert result.metadata["output_truncated"] is True
    assert result.metadata["ordering"] == "shallow_paths_first"


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
    assert result.metadata["mode"] == "full_file"


def test_apply_patch_replaces_one_unique_block(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    result = ToolRuntime(str(tmp_path)).execute(
        "apply_patch",
        {
            "path": "a.py",
            "old_text": "    return a - b",
            "new_text": "    return a + b",
        },
    )

    assert result.success
    assert result.metadata["mode"] == "localized"
    assert path.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"


def test_apply_patch_rejects_missing_or_ambiguous_old_text_without_writing(tmp_path):
    path = tmp_path / "a.py"
    original = "value = 1\nvalue = 1\n"
    path.write_text(original, encoding="utf-8")
    runtime = ToolRuntime(str(tmp_path))

    missing = runtime.execute(
        "apply_patch", {"path": "a.py", "old_text": "value = 2", "new_text": "value = 3"}
    )
    ambiguous = runtime.execute(
        "apply_patch", {"path": "a.py", "old_text": "value = 1", "new_text": "value = 3"}
    )

    assert not missing.success
    assert "not found" in missing.output
    assert not ambiguous.success
    assert "ambiguous" in ambiguous.output
    assert path.read_text(encoding="utf-8") == original


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


def test_tool_output_keeps_head_and_tail_when_truncated(tmp_path):
    content = "HEAD\n" + "x" * 500 + "\nTAIL\n"
    (tmp_path / "large.py").write_text(content, encoding="utf-8")
    result = ToolRuntime(str(tmp_path), max_output_chars=100).execute("read", {"path": "large.py"})
    assert len(result.output) <= 100
    assert "HEAD" in result.output
    assert "TAIL" in result.output
    assert "chars omitted" in result.output
    assert result.metadata["output_truncated"] is True
    assert result.metadata["output_chars"] > len(result.output)


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_git_tools_disable_repository_configured_external_processes(tmp_path):
    def git(*arguments):
        subprocess.run(["git", *arguments], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "RepoFix Test")
    (tmp_path / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".gitattributes").write_text("*.py diff=evil\n", encoding="utf-8")
    marker = tmp_path / "external-process-ran.txt"
    script = tmp_path / "evil.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    git("add", "a.py", ".gitattributes")
    git("commit", "-m", "baseline")
    command = f'"{sys.executable}" "{script}"'
    git("config", "diff.evil.command", command)
    git("config", "core.fsmonitor", command)
    (tmp_path / "a.py").write_text("VALUE = 2\n", encoding="utf-8")

    runtime = ToolRuntime(str(tmp_path))
    diff = runtime.execute("git_diff", {})
    status = runtime.execute("git_status", {})

    assert diff.success is True
    assert "VALUE = 2" in diff.output
    assert status.success is True
    assert "a.py" in status.output
    assert not marker.exists()
    assert diff.metadata["environment_scrubbed"] is True
