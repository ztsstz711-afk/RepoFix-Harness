from repofix.preflight import RepositoryPreflight


def check(report, name):
    return next(item for item in report.checks if item.name == name)


def test_preflight_reports_repository_shape_without_executing_tests(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "test_module.py").write_text("def test_value(): assert True\n", encoding="utf-8")

    report = RepositoryPreflight(str(tmp_path), "pytest -q test_module.py").run()

    assert report.success is True
    assert check(report, "test_command").status == "pass"
    assert check(report, "python_sources").message == "2 visible Python files"
    assert check(report, "test_files").message == "1 conventional pytest files"
    assert check(report, "project_metadata").message == "pyproject.toml"
    assert check(report, "git_repository").status == "warning"


def test_preflight_rejects_non_pytest_command(tmp_path):
    report = RepositoryPreflight(str(tmp_path), "python dangerous.py").run()

    assert report.success is False
    assert check(report, "test_command").status == "fail"
    assert "only pytest" in check(report, "test_command").message


def test_preflight_treats_unusual_repository_shape_as_warning(tmp_path):
    report = RepositoryPreflight(str(tmp_path), "pytest -q").run()

    assert report.success is True
    assert check(report, "python_sources").status == "warning"
    assert check(report, "test_files").status == "warning"
    assert check(report, "project_metadata").status == "warning"


def test_preflight_reports_missing_pytest(monkeypatch, tmp_path):
    monkeypatch.setattr("repofix.preflight.importlib.util.find_spec", lambda name: None)

    report = RepositoryPreflight(str(tmp_path), "pytest -q").run()

    assert report.success is False
    assert check(report, "pytest").status == "fail"
