from pathlib import Path
from types import SimpleNamespace

import pytest

from repofix.execution import (
    DockerPytestExecutor,
    LocalPytestExecutor,
    create_pytest_executor,
    sanitized_subprocess_environment,
)
from repofix.schemas import Observation


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


def test_docker_executor_force_removes_a_timed_out_container(monkeypatch, tmp_path):
    cleanup = {}
    monkeypatch.setattr("repofix.execution.find_docker_executable", lambda: "docker")
    monkeypatch.setattr(
        "repofix.execution._run",
        lambda *args: Observation("run_command", "timeout", False, metadata={"timed_out": True}),
    )
    monkeypatch.setattr(
        "repofix.execution.subprocess.run",
        lambda command, **kwargs: (
            cleanup.update(command=command)
            or SimpleNamespace(returncode=0, stdout="container", stderr="")
        ),
    )

    result = DockerPytestExecutor().run(tmp_path, ["-q"], 1)

    assert cleanup["command"][:3] == ["docker", "rm", "--force"]
    assert cleanup["command"][-1] == result.metadata["container_name"]
    assert result.metadata["cleanup_success"] is True


def test_docker_executor_preserves_timeout_when_cleanup_fails(monkeypatch, tmp_path):
    monkeypatch.setattr("repofix.execution.find_docker_executable", lambda: "docker")
    monkeypatch.setattr(
        "repofix.execution._run",
        lambda *args: Observation("run_command", "timeout", False, metadata={"timed_out": True}),
    )

    def fail_cleanup(*args, **kwargs):
        raise OSError("cleanup unavailable")

    monkeypatch.setattr("repofix.execution.subprocess.run", fail_cleanup)

    result = DockerPytestExecutor().run(tmp_path, ["-q"], 1)

    assert result.output == "timeout"
    assert result.metadata["timed_out"] is True
    assert result.metadata["cleanup_success"] is False
    assert "cleanup unavailable" in result.metadata["cleanup_error"]


def test_subprocess_environment_removes_provider_and_common_secrets(monkeypatch):
    monkeypatch.setenv("REPOFIX_API_KEY", "provider-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")
    monkeypatch.setenv("DATABASE_PASSWORD", "database-secret")
    monkeypatch.setenv("SAFE_TEST_VALUE", "visible")

    environment = sanitized_subprocess_environment()

    assert "REPOFIX_API_KEY" not in environment
    assert "GITHUB_TOKEN" not in environment
    assert "DATABASE_PASSWORD" not in environment
    assert environment["SAFE_TEST_VALUE"] == "visible"


def test_local_pytest_cannot_read_repofix_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOFIX_API_KEY", "must-not-leak")
    (tmp_path / "test_environment.py").write_text(
        "import os\n\ndef test_secret_is_absent():\n    assert 'REPOFIX_API_KEY' not in os.environ\n",
        encoding="utf-8",
    )

    result = LocalPytestExecutor().run(tmp_path, ["-q"], 20)

    assert result.success is True
    assert "1 passed" in result.output
