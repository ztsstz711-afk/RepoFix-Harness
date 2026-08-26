import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

from .schemas import Observation


class PytestExecutor(Protocol):
    name: str

    def run(self, repo: Path, arguments: list[str], timeout_seconds: int) -> Observation: ...


class LocalPytestExecutor:
    name = "local"

    def run(self, repo: Path, arguments: list[str], timeout_seconds: int) -> Observation:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return _run(
            "run_command",
            [sys.executable, "-m", "pytest", *arguments],
            repo,
            timeout_seconds,
            env,
        )


class DockerPytestExecutor:
    name = "docker"

    def __init__(self, image: str = "repofix-pytest:latest"):
        self.image = image
        self.docker = find_docker_executable()

    def run(self, repo: Path, arguments: list[str], timeout_seconds: int) -> Observation:
        mount = f"type=bind,source={repo},target=/workspace,readonly"
        command = [
            self.docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--mount",
            mount,
            "--workdir",
            "/workspace",
            "--user",
            "65534:65534",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "512m",
            "--cpus",
            "1.0",
            "--pids-limit",
            "256",
            self.image,
            "python",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            *arguments,
        ]
        observation = _run("run_command", command, repo, timeout_seconds, os.environ.copy())
        observation.metadata.update(
            {
                "execution_backend": self.name,
                "docker_image": self.image,
                "network": "none",
                "workspace_mount": "readonly",
            }
        )
        return observation


def create_pytest_executor(backend: str, docker_image: str) -> PytestExecutor:
    if backend == "local":
        return LocalPytestExecutor()
    if backend == "docker":
        return DockerPytestExecutor(docker_image)
    raise ValueError(f"unknown execution backend: {backend}")


def find_docker_executable() -> str:
    executable = shutil.which("docker")
    if executable:
        return executable
    if os.name == "nt":
        candidate = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "DockerDesktop"
            / "resources"
            / "bin"
            / "docker.exe"
        )
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError("Docker CLI not found; install Docker Desktop and open a new terminal")


def _run(
    tool_name: str,
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    env: dict[str, str],
) -> Observation:
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return Observation(
            tool_name,
            output + f"\ncommand timed out after {timeout_seconds}s",
            False,
            int((time.perf_counter() - started) * 1000),
            {"timed_out": True},
        )
    return Observation(
        tool_name,
        process.stdout + process.stderr,
        process.returncode == 0,
        int((time.perf_counter() - started) * 1000),
        {"return_code": process.returncode, "timed_out": False},
    )
