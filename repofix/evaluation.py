from .schemas import TestSnapshot
from .tools import ToolRuntime


class RepairEvaluator:
    def __init__(self, runtime: ToolRuntime):
        self.runtime = runtime

    def run_tests(self) -> TestSnapshot:
        observation = self.runtime.execute("run_command", {"command": "pytest -q"})
        return TestSnapshot(
            success=observation.success,
            output=observation.output,
            duration_ms=observation.duration_ms,
        )

    def changed_files(self) -> list[str]:
        observation = self.runtime.execute("git_status", {})
        if not observation.success:
            return []
        files = []
        for line in observation.output.splitlines():
            if len(line) >= 4:
                files.append(line[3:].strip())
        return files
