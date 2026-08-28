from repofix.cli import build_parser
from repofix.config import Settings


def test_cli_supports_human_quiet_and_json_output_modes(monkeypatch):
    monkeypatch.delenv("REPOFIX_API_KEY", raising=False)
    parser = build_parser(Settings.from_env())

    normal = parser.parse_args(["--repo", "repo", "--task", "fix"])
    quiet = parser.parse_args(
        ["--repo", "repo", "--task", "fix", "--quiet"]
    )
    json_output = parser.parse_args(
        ["--repo", "repo", "--task", "fix", "--json"]
    )

    assert normal.quiet is False and normal.json is False
    assert quiet.quiet is True and quiet.json is False
    assert json_output.quiet is False and json_output.json is True
