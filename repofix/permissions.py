from pathlib import Path


CONTROL_DIRECTORIES = {".git", ".repofix", ".venv", "venv", "__pycache__", ".pytest_cache"}


class PermissionPolicy:
    def __init__(self, repo: Path):
        self.repo = repo.resolve()

    def resolve(self, relative_path: str) -> Path:
        path = (self.repo / relative_path).resolve()
        if path != self.repo and self.repo not in path.parents:
            raise PermissionError("path escapes repository")
        return path

    def ensure_readable(self, relative_path: str) -> Path:
        path = self.resolve(relative_path)
        self._deny_control_path(path)
        return path

    def ensure_writable(self, relative_path: str) -> Path:
        path = self.resolve(relative_path)
        self._deny_control_path(path)
        if path == self.repo:
            raise PermissionError("cannot overwrite repository root")
        return path

    def is_visible(self, path: Path) -> bool:
        try:
            relative = path.resolve().relative_to(self.repo)
        except ValueError:
            return False
        return not any(part in CONTROL_DIRECTORIES for part in relative.parts)

    def ensure_pytest_arguments(self, arguments: list[str]) -> None:
        denied_options = {"-p", "--rootdir", "--confcutdir"}
        for argument in arguments:
            value = argument.split("=", 1)[-1]
            if argument.split("=", 1)[0] in denied_options:
                raise PermissionError(f"pytest option denied: {argument}")
            if ".." in Path(value).parts or Path(value).is_absolute():
                raise PermissionError("pytest path must stay inside the repository")

    def _deny_control_path(self, path: Path) -> None:
        relative = path.relative_to(self.repo)
        if any(part in CONTROL_DIRECTORIES for part in relative.parts):
            raise PermissionError("access to repository control directories is denied")
