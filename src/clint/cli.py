from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .core import AnalysisConfig, analyze
from .report import render, render_json

app = typer.Typer(
    help="Find redundant information in agent instruction files.", add_completion=False
)


@app.command()
def check(
    path: Annotated[Path, typer.Argument(help="File or directory to scan")],
    threshold: Annotated[
        float, typer.Option("--threshold", min=0.0, max=1.0, help="SemHash similarity threshold.")
    ] = 0.90,
    min_block_tokens: Annotated[
        int, typer.Option("--min-block-tokens", min=1, help="Ignore shorter blocks.")
    ] = 10,
    fail_above: Annotated[
        float | None,
        typer.Option(
            "--fail-above",
            min=0.0,
            max=1.0,
            help="Exit 1 when context redundancy exceeds this ratio.",
        ),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output machine-readable JSON.")
    ] = False,
    model: Annotated[str | None, typer.Option("--model", help="Model2Vec model name/path.")] = None,
    canonical_dir: Annotated[
        list[str] | None,
        typer.Option("--canonical-dir", help="Prefer this prefix for canonical blocks."),
    ] = None,
) -> None:
    if not path.exists():
        typer.echo(f"clint: path does not exist: {path}", err=True)
        raise typer.Exit(2)
    try:
        report = analyze(
            path,
            AnalysisConfig(
                threshold=threshold,
                min_block_tokens=min_block_tokens,
                model=model,
                canonical_paths=tuple(canonical_dir or []),
            ),
        )
    except (OSError, RuntimeError, ImportError) as exc:
        typer.echo(f"clint: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(render_json(report) if json_output else render(report))
    if fail_above is not None and report.context_redundancy > fail_above:
        raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
