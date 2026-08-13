"""T238: the distributable `testpilot-cli` entrypoint — final assembly of
the six already-built, already-tested per-domain subcommand groups
(billing/projects/testcases/ai/run/reports) into one Typer app, per the
constitution's CLI Interface principle. Each subcommand group's own logic
is already covered by its own dedicated test file (test_billing_cli.py
etc.) — this file only proves the wiring itself: that `testpilot-cli`
actually resolves (pyproject.toml's `[project.scripts]` entry points at
`testpilot.cli.main:app`, which did not exist before this task — running
the installed `testpilot-cli` console script raised
`ModuleNotFoundError: No module named 'testpilot.cli.main'`) and that
every documented subcommand group is reachable through it, matching
quickstart.md Section 13's own literal invocation
(`testpilot-cli billing set-plan <org_id> free --max-projects=1`).
"""

from typer.testing import CliRunner

from testpilot.cli.main import app

runner = CliRunner()


def test_top_level_help_lists_every_subcommand_group():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in ("billing", "projects", "testcases", "ai", "run", "reports"):
        assert group in result.output


def test_billing_subcommand_group_is_reachable_matching_quickstart_section_13():
    # quickstart.md Section 13's literal invocation shape:
    # `testpilot-cli billing set-plan <org_id> free --max-projects=1`
    result = runner.invoke(app, ["billing", "--help"])
    assert result.exit_code == 0
    assert "set-plan" in result.output


def test_projects_subcommand_group_is_reachable():
    result = runner.invoke(app, ["projects", "--help"])
    assert result.exit_code == 0


def test_testcases_subcommand_group_is_reachable():
    result = runner.invoke(app, ["testcases", "--help"])
    assert result.exit_code == 0


def test_ai_subcommand_group_is_reachable():
    result = runner.invoke(app, ["ai", "--help"])
    assert result.exit_code == 0


def test_run_subcommand_group_is_reachable():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_reports_subcommand_group_is_reachable():
    result = runner.invoke(app, ["reports", "--help"])
    assert result.exit_code == 0
