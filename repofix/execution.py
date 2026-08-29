import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .schemas import Observation


SENSITIVE_ENV_MARKERS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "ACCESS_KEY",
)


def sanitized_subprocess_environment() -> dict[str, str]:
    safe = {}
    for name, value in os.environ.items():
        upper = name.upper()
        if upper.startswith("REPOFIX_") or any(marker in upper for marker in SENSITIVE_ENV_MARKERS):
            continue
        safe[name] = value
    safe["PYTHONDONTWRITEBYTECODE"] = "1"
    return safe


def local_pytest_environment(repo: Path) -> dict[str, str]:
    """Build an isolated import path for root- and src-layout repositories."""
    safe = sanitized_subprocess_environment()
    candidates = [repo / "src", repo]
    safe["PYTHONPATH"] = os.pathsep.join(str(path) for path in candidates if path.is_dir())
    return safe


class PytestExecutor(Protocol):
    name: str

    def run(self, repo: Path, arguments: list[str], timeout_seconds: int) -> Observation: ...


class LocalPytestExecutor:
    name = "local"

    def run(self, repo: Path, arguments: list[str], timeout_seconds: int) -> Observation:
        env = local_pytest_environment(repo)
        observation = _run(
            "run_command",
            [sys.executable, "-m", "pytest", *arguments],
            repo,
            timeout_seconds,
            env,
        )
        observation.metadata["execution_backend"] = self.name
        observation.metadata["environment_scrubbed"] = True
        return observation


class DockerPytestExecutor:
    name = "docker"

    def __init__(self, image: str = "repofix-pytest:latest"):
        self.image = image
        self.docker = find_docker_executable()

    def run(self, repo: Path, arguments: list[str], timeout_seconds: int) -> Observation:
        mount = f"type=bind,source={repo},target=/workspace,readonly"
        container_name = f"repofix-{uuid4().hex[:12]}"
        command = [
            self.docker,
            "run",
            "--rm",
            "--name",
            container_name,
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
            "--env",
            "PYTHONPATH=/workspace/src:/workspace",
            self.image,
            "python",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            *arguments,
        ]
        observation = _run(
            "run_command",
            command,
            repo,
            timeout_seconds,
            sanitized_subprocess_environment(),
        )
        if observation.metadata.get("timed_out"):
            try:
                cleanup = subprocess.run(
                    [self.docker, "rm", "--force", container_name],
                    text=True,
                    capture_output=True,
                    timeout=10,
                    env=sanitized_subprocess_environment(),
                )
                cleanup_detail = (cleanup.stderr or cleanup.stdout).strip()
                observation.metadata["cleanup_success"] = (
                    cleanup.returncode == 0 or "No such container" in cleanup_detail
                )
                if cleanup.returncode != 0:
                    observation.metadata["cleanup_error"] = cleanup_detail[:500]
            except (OSError, subprocess.SubprocessError) as exc:
                observation.metadata["cleanup_success"] = False
                observation.metadata["cleanup_error"] = f"{type(exc).__name__}: {exc}"[:500]
        observation.metadata.update(
            {
                "execution_backend": self.name,
                "docker_image": self.image,
                "network": "none",
                "workspace_mount": "readonly",
                "container_name": container_name,
                "environment_scrubbed": True,
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


def check_docker_ready(image: str, timeout_seconds: int = 15) -> str:
    docker = find_docker_executable()
    env = sanitized_subprocess_environment()
    env["PATH"] = str(Path(docker).parent) + os.pathsep + env.get("PATH", "")
    checks = (
        [docker, "version", "--format", "{{.Server.Version}}"],
        [docker, "image", "inspect", image, "--format", "{{.Id}}"],
        [
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            image,
            "python",
            "-m",
            "pytest",
            "--version",
        ],
    )
    outputs = []
    labels = ("Docker daemon", f"Docker image {image}", "container pytest")
    for label, command in zip(labels, checks):
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{label} readiness check timed out") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:500]
            raise RuntimeError(f"{label} is not ready: {detail}")
        outputs.append(result.stdout.strip())
    return "; ".join(outputs)


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
