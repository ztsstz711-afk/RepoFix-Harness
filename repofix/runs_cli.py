import argparse
import json

from .run_manager import RunManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and recover RepoFix runs")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list saved runs")
    show = commands.add_parser("show", help="show one saved run")
    show.add_argument("run_id", help="run ID or latest")
    rollback = commands.add_parser("rollback", help="restore files from one run")
    rollback.add_argument("run_id", help="run ID or latest")
    rollback.add_argument("--force", action="store_true", help="overwrite files changed after the run")
    args = parser.parse_args()

    manager = RunManager(args.repo)
    try:
        if args.command == "list":
            result = manager.list_runs()
            if args.json:
                print(json.dumps(result, indent=2))
            elif not result:
                print("No RepoFix runs found.")
            else:
                for item in result:
                    print(
                        f"{item['run_id']} status={item['status']} steps={item['steps']} "
                        f"files={len(item['changed_files'])} rollback={item['rollback_performed']} "
                        f"task={item['task']}"
                    )
        elif args.command == "show":
            state = manager.show(args.run_id)
            result = state.to_dict()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                item = manager.summary(state)
                print(json.dumps(item, indent=2))
        else:
            state = manager.rollback(args.run_id, force=args.force)
            print(
                f"run={state.run_id} restored={','.join(state.evaluation.rollback_files)} "
                f"post_rollback_pytest={state.evaluation.post_rollback.success}"
            )
    except (FileNotFoundError, ValueError, PermissionError, RuntimeError) as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
