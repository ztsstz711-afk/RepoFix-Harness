import subprocess
from pathlib import Path

import pytest

from repofix.execution import check_docker_ready, find_docker_executable
from repofix.tools import ToolRuntime


def require_docker():
    try:
        check_docker_ready("repofix-pytest:latest")
    except (FileNotFoundError, RuntimeError) as exc:
        pytest.skip(str(exc))


def test_real_docker_backend_enforces_security_boundaries(monkeypatch):
    require_docker()
    monkeypatch.setenv("REPOFIX_API_KEY", "must-not-reach-container")
    repo = Path(__file__).resolve().parents[1] / "examples" / "sandbox_probe_repo"

    result = ToolRuntime(
        str(repo), execution_backend="docker", command_timeout_seconds=30
    ).execute("run_command", {"command": "pytest -q"})

    assert result.success is True
    assert "4 passed" in result.output
    assert result.metadata["network"] == "none"
    assert result.metadata["workspace_mount"] == "readonly"
    assert not (repo / "forbidden-write.txt").exists()


def test_real_docker_timeout_removes_the_container(tmp_path):
    require_docker()
    (tmp_path / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(20)\n",
        encoding="utf-8",
    )
    result = ToolRuntime(
        str(tmp_path), execution_backend="docker", command_timeout_seconds=1
    ).execute("run_command", {"command": "pytest -q"})

    assert result.success is False
    assert result.metadata["timed_out"] is True
    assert result.metadata["cleanup_success"] is True
    name = result.metadata["container_name"]
    process = subprocess.run(
        [find_docker_executable(), "ps", "--all", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert process.returncode == 0
    assert process.stdout.strip() == ""
