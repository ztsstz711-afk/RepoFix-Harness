import importlib.util
import shutil
import sys
from pathlib import Path

from .schemas import PreflightCheck, PreflightState
from .tools import ToolRuntime
from .execution import check_docker_ready


PROJECT_MARKERS = ("pyproject.toml", "setup.cfg", "setup.py", "requirements.txt")


class RepositoryPreflight:
    """Inspect local prerequisites without executing repository code or calling a model."""

    def __init__(
        self,
        repo: str,
        test_command: str,
        execution_backend: str = "local",
        docker_image: str = "repofix-pytest:latest",
        final_test_command: str | None = None,
    ):
        self.repo = Path(repo).resolve()
        self.test_command = test_command
        self.final_test_command = final_test_command or test_command
        self.execution_backend = execution_backend
        self.docker_image = docker_image

    def run(self) -> PreflightState:
        checks: list[PreflightCheck] = []
        if not self.repo.is_dir():
            return PreflightState(
                False,
                [PreflightCheck("repository", "fail", f"directory not found: {self.repo}")],
            )

        try:
            runtime = ToolRuntime(
                str(self.repo), execution_backend=self.execution_backend, docker_image=self.docker_image
            )
        except (ValueError, FileNotFoundError) as exc:
            return PreflightState(False, [PreflightCheck("execution_backend", "fail", str(exc))])
        checks.append(PreflightCheck("repository", "pass", str(self.repo)))
        checks.append(PreflightCheck("execution_backend", "pass", self.execution_backend))

        if self.execution_backend == "docker":
            try:
                docker_detail = check_docker_ready(self.docker_image)
            except (FileNotFoundError, RuntimeError) as exc:
                checks.append(PreflightCheck("docker_runtime", "fail", str(exc)))
            else:
                checks.append(PreflightCheck("docker_runtime", "pass", docker_detail))
                checks.append(PreflightCheck("pytest", "pass", f"provided by {self.docker_image}"))
        elif importlib.util.find_spec("pytest") is None:
            checks.append(PreflightCheck("pytest", "fail", f"pytest is not installed for {sys.executable}"))
        else:
            checks.append(PreflightCheck("pytest", "pass", f"available via {sys.executable}"))

        try:
            runtime.pytest_command(self.test_command)
        except (ValueError, PermissionError) as exc:
            checks.append(PreflightCheck("test_command", "fail", str(exc)))
        else:
            checks.append(PreflightCheck("test_command", "pass", self.test_command))
        try:
            runtime.pytest_command(self.final_test_command)
        except (PermissionError, ValueError) as exc:
            checks.append(PreflightCheck("final_test_command", "fail", str(exc)))
        else:
            checks.append(
                PreflightCheck("final_test_command", "pass", self.final_test_command)
            )

        python_files = self._visible_files("*.py", runtime)
        checks.append(
            PreflightCheck(
                "python_sources",
                "pass" if python_files else "warning",
                f"{len(python_files)} visible Python files",
            )
        )

        test_files = sorted(
            set(self._visible_files("test_*.py", runtime))
            | set(self._visible_files("*_test.py", runtime))
        )
        checks.append(
            PreflightCheck(
                "test_files",
                "pass" if test_files else "warning",
                f"{len(test_files)} conventional pytest files",
            )
        )

        markers = [name for name in PROJECT_MARKERS if (self.repo / name).is_file()]
        checks.append(
            PreflightCheck(
                "project_metadata",
                "pass" if markers else "warning",
                ", ".join(markers) if markers else "no standard project metadata found",
            )
        )

        git = shutil.which("git")
        checks.append(
            PreflightCheck(
                "git",
                "pass" if git else "warning",
                git or "git executable not found; git tools will be unavailable",
            )
        )
        checks.append(
            PreflightCheck(
                "git_repository",
                "pass" if (self.repo / ".git").exists() else "warning",
                "Git metadata found"
                if (self.repo / ".git").exists()
                else "target is not a Git worktree; git diff/status may be unavailable",
            )
        )
        return PreflightState(not any(check.status == "fail" for check in checks), checks)

    def _visible_files(self, pattern: str, runtime: ToolRuntime) -> list[Path]:
        return [
            path
            for path in self.repo.rglob(pattern)
            if path.is_file() and runtime.permissions.is_visible(path)
        ]
