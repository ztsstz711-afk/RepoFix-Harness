from .schemas import TestSnapshot
from .tools import ToolRuntime


class RepairEvaluator:
    def __init__(self, runtime: ToolRuntime, test_command: str = "pytest -q"):
        self.runtime = runtime
        self.test_command = test_command

    def run_tests(self) -> TestSnapshot:
        observation = self.runtime.execute("run_command", {"command": self.test_command})
        return TestSnapshot(
            success=observation.success,
            output=observation.output,
            duration_ms=observation.duration_ms,
            command=self.test_command,
            execution_backend=observation.metadata.get("execution_backend", "local"),
            metadata=dict(observation.metadata),
        )

    @staticmethod
    def changed_files(history: list[dict]) -> list[str]:
        files = set()
        for event in history:
            observation = event.get("observation", {})
            metadata = observation.get("metadata", {})
            if event.get("action", {}).get("name") == "apply_patch" and metadata.get("changed"):
                files.add(metadata["path"])
        return sorted(files)
