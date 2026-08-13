"""testpilot-cli — the distributable CLI entrypoint (constitution
Principle II: CLI Interface), assembled here from the six per-domain
subcommand groups already built and already tested next to their own
feature phase (billing/projects/testcases/ai/run/reports — see each
module's own tests). This file is final wiring only, not where any
command's own logic lives.
"""

import typer

from testpilot.cli import ai, billing, projects, reports, run, testcases

app = typer.Typer(help="TestPilot AI administration CLI.")

app.add_typer(billing.app, name="billing")
app.add_typer(projects.app, name="projects")
app.add_typer(testcases.app, name="testcases")
app.add_typer(ai.app, name="ai")
app.add_typer(run.app, name="run")
app.add_typer(reports.app, name="reports")


if __name__ == "__main__":
    app()
