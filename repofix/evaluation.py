from .schemas import TestSnapshot
from .tools import ToolRuntime


class RepairEvaluator:
    def __init__(
        self,
        runtime: ToolRuntime,
        test_command: str = "pytest -q",
        final_test_command: str | None = None,
    ):
        self.runtime = runtime
        self.test_command = test_command
        self.final_test_command = final_test_command or test_command

    def run_tests(self, *, final: bool = False) -> TestSnapshot:
        command = self.final_test_command if final else self.test_command
        observation = self.runtime.execute("run_command", {"command": command})
        return TestSnapshot(
            success=observation.success,
            output=observation.output,
            duration_ms=observation.duration_ms,
            command=command,
            execution_backend=observation.metadata.get("execution_backend", "local"),
            metadata=dict(observation.metadata),
        )

    def run_final_tests(self) -> TestSnapshot:
        return self.run_tests(final=True)

    @staticmethod
    def changed_files(history: list[dict]) -> list[str]:
        files = set()
        for event in history:
            observation = event.get("observation", {})
            metadata = observation.get("metadata", {})
            if event.get("action", {}).get("name") == "apply_patch" and metadata.get("changed"):
                files.add(metadata["path"])
        return sorted(files)
