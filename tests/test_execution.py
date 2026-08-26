from pathlib import Path

import pytest

from repofix.execution import DockerPytestExecutor, create_pytest_executor


def test_docker_executor_builds_a_restricted_container_command(monkeypatch, tmp_path):
    captured = {}

    def fake_run(tool_name, command, cwd, timeout_seconds, env):
        captured.update(command=command, cwd=cwd, timeout=timeout_seconds)
        from repofix.schemas import Observation

        return Observation(tool_name, "ok")

    monkeypatch.setattr("repofix.execution.find_docker_executable", lambda: "docker")
    monkeypatch.setattr("repofix.execution._run", fake_run)
    executor = DockerPytestExecutor("repofix-test:image")

    result = executor.run(tmp_path, ["-q", "tests"], 45)

    command = captured["command"]
    assert command[:2] == ["docker", "run"]
    assert ["--network", "none"] == command[command.index("--network") : command.index("--network") + 2]
    assert "--read-only" in command
    assert "--cap-drop" in command and "ALL" in command
    assert "no-new-privileges" in command
    assert "512m" in command
    assert "repofix-test:image" in command
    assert command[-2:] == ["-q", "tests"]
    assert result.metadata["execution_backend"] == "docker"
    assert result.metadata["workspace_mount"] == "readonly"


def test_unknown_execution_backend_is_rejected():
    with pytest.raises(ValueError, match="unknown execution backend"):
        create_pytest_executor("remote", "unused")
