import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


class WorkspaceConflictError(RuntimeError):
    pass


class WorkspaceJournal:
    """Capture each file once before its first Agent write and restore it safely."""

    def __init__(self, repo: str, artifact_dir: Path, max_changed_files: int = 5):
        if max_changed_files < 0:
            raise ValueError("max_changed_files must be zero or positive")
        self.repo = Path(repo).resolve()
        self.root = artifact_dir.resolve()
        self.backup_dir = self.root / "backups"
        self.manifest_path = self.root / "manifest.json"
        self.max_changed_files = max_changed_files
        self.manifest = self._load_manifest()

    def capture(self, path: Path) -> None:
        resolved = path.resolve()
        relative = resolved.relative_to(self.repo).as_posix()
        files = self.manifest["files"]
        if relative in files:
            if self.manifest.pop("rolled_back_at", None):
                self._save_manifest()
            return
        if self.max_changed_files and len(files) >= self.max_changed_files:
            raise PermissionError(
                f"changed file limit reached ({len(files)}/{self.max_changed_files})"
            )

        existed = resolved.is_file()
        backup_name = sha256(relative.encode("utf-8")).hexdigest() + ".bin"
        before_hash = None
        if existed:
            content = resolved.read_bytes()
            before_hash = sha256(content).hexdigest()
            self._atomic_write_bytes(self.backup_dir / backup_name, content)
        files[relative] = {
            "existed": existed,
            "backup": backup_name if existed else None,
            "before_sha256": before_hash,
            "after_sha256": None,
        }
        self._save_manifest()

    def record_after(self, path: Path, after_hash: str) -> None:
        relative = path.resolve().relative_to(self.repo).as_posix()
        if relative not in self.manifest["files"]:
            raise ValueError(f"path was not captured before write: {relative}")
        self.manifest["files"][relative]["after_sha256"] = after_hash
        self._save_manifest()

    def rollback(self, force: bool = False) -> list[str]:
        if self.manifest.get("rolled_back_at"):
            raise ValueError("workspace journal has already been rolled back")
        targets = self._preflight_rollback(force)
        restored = []
        for relative, entry, target in targets:
            if entry["existed"]:
                content = (self.backup_dir / entry["backup"]).read_bytes()
                self._atomic_write_bytes(target, content)
            elif target.exists():
                if not target.is_file():
                    raise PermissionError(f"rollback target is not a file: {relative}")
                target.unlink()
            restored.append(relative)
        self.manifest["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        self._save_manifest()
        return sorted(restored)

    def _preflight_rollback(self, force: bool) -> list[tuple[str, dict, Path]]:
        targets = []
        conflicts = []
        for relative, entry in self.manifest["files"].items():
            target = (self.repo / relative).resolve()
            if target != self.repo and self.repo not in target.parents:
                raise PermissionError(f"unsafe journal path: {relative}")
            if entry["existed"]:
                backup = self.backup_dir / entry["backup"]
                if not backup.is_file():
                    raise FileNotFoundError(f"workspace backup missing: {relative}")
            if target.exists() and not target.is_file():
                conflicts.append(relative)
            else:
                current_hash = sha256(target.read_bytes()).hexdigest() if target.is_file() else None
                expected_hash = entry.get("after_sha256")
                already_absent_created_file = not entry["existed"] and not target.exists()
                if expected_hash is None or (
                    current_hash != expected_hash and not already_absent_created_file
                ):
                    conflicts.append(relative)
            targets.append((relative, entry, target))
        if conflicts and not force:
            names = ", ".join(sorted(conflicts))
            raise WorkspaceConflictError(
                f"files changed after the Agent run or lack end hashes: {names}; use --force to override"
            )
        return targets

    def tracked_files(self) -> list[str]:
        return sorted(self.manifest["files"])

    def has_pending_changes(self) -> bool:
        return bool(self.manifest["files"]) and not self.manifest.get("rolled_back_at")

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "files": {}}
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("files"), dict):
            raise ValueError("invalid workspace journal manifest")
        return data

    def _save_manifest(self) -> None:
        content = json.dumps(self.manifest, indent=2).encode("utf-8")
        self._atomic_write_bytes(self.manifest_path, content)

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
