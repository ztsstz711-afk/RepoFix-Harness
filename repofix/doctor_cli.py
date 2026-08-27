import argparse
import json
from dataclasses import asdict

from .config import Settings
from .preflight import RepositoryPreflight


def main() -> int:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(
        description="Check a Python repository before spending model requests"
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--test-command", default=settings.test_command)
    parser.add_argument("--final-test-command", default=settings.final_test_command)
    parser.add_argument(
        "--execution-backend", choices=("local", "docker"), default=settings.execution_backend
    )
    parser.add_argument("--docker-image", default=settings.docker_image)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = RepositoryPreflight(
        args.repo,
        args.test_command,
        args.execution_backend,
        args.docker_image,
        args.final_test_command,
    ).run()
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        for check in report.checks:
            print(f"[{check.status.upper():7}] {check.name}: {check.message}")
        print(f"preflight={'passed' if report.success else 'failed'}")
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
