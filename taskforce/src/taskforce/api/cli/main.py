"""Taskforce CLI entry point."""

import typer

app = typer.Typer(
    name="taskforce",
    help="Production-grade multi-agent orchestration framework",
    add_completion=False,
)


@app.command()
def version():
    """Show Taskforce version."""
    from taskforce import __version__
    typer.echo(f"Taskforce version {__version__}")


if __name__ == "__main__":
    app()

