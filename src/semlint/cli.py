from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer
from typer._click import Context
from typer.core import TyperArgument, TyperCommand, TyperGroup, TyperOption
from typer.main import get_command

from .core import (
    AnalysisConfig,
    SortCategory,
    SortOrder,
    SplitMode,
    analyze,
)
from .report import render, render_json

app = typer.Typer(
    help="Find redundant information in agent instruction files.", add_completion=False
)
discovery_app = typer.Typer(help="Agent-facing CLI capability discovery.", add_completion=False)
self_app = typer.Typer(help="CLI capability discovery for agent clients.", add_completion=False)


def _parameter_type(parameter: TyperArgument | TyperOption) -> str:
    choices = getattr(parameter.type, "choices", None)
    if choices is not None:
        return "|".join(str(choice) for choice in choices)
    type_name = getattr(parameter.type, "name", None)
    return str(type_name or parameter.type)


def _command_entry(
    command: TyperCommand | TyperGroup,
    command_path: str,
) -> dict[str, Any]:
    arguments = [param for param in command.params if isinstance(param, TyperArgument)]
    options = [param for param in command.params if isinstance(param, TyperOption)]
    usage_parts = [command_path]
    for parameter in arguments:
        name = (parameter.name or "ARG").upper().replace("_", "-")
        if parameter.name == "paths":
            name = "PATH"
        part = f"<{name}>"
        if parameter.nargs == -1:
            part += "..."
        usage_parts.append(part if parameter.required else f"[{part}]")
    for parameter in options:
        long_flag = next((option for option in parameter.opts if option.startswith("--")), None)
        short_flag = next(
            (
                option
                for option in parameter.opts
                if option.startswith("-") and not option.startswith("--")
            ),
            None,
        )
        flag = (
            f"{short_flag}/{long_flag}"
            if short_flag and long_flag
            else long_flag or parameter.opts[0]
        )
        value_types = getattr(parameter.type, "types", None)
        if value_types:
            value_parts = []
            for index, value_type in enumerate(value_types):
                choices = getattr(value_type, "choices", None)
                label = "|".join(str(choice) for choice in choices) if choices else ""
                if not label:
                    label = "order" if index == 0 else "category"
                value_parts.append(f"<{label}>")
            value = " " + " ".join(value_parts)
        elif parameter.is_flag:
            value = ""
        else:
            value = f" <{(parameter.name or 'VALUE').replace('_', '-')}>"
        part = f"{flag}{value}"
        usage_parts.append(part if parameter.required else f"[{part}]")
    usage = " ".join(usage_parts)
    params: list[dict[str, Any]] = []
    for param in command.params:
        record: dict[str, Any] = {
            "name": param.name,
            "kind": "option" if isinstance(param, TyperOption) else "argument",
            "required": param.required,
            "multiple": isinstance(param, TyperArgument) and param.nargs == -1,
            "help": getattr(param, "help", None),
        }
        if isinstance(param, TyperOption):
            record["flags"] = list(param.opts)
            record["type"] = _parameter_type(param)
            choices = getattr(param.type, "choices", None)
            if choices is not None:
                record["choices"] = list(choices)
            if param.default is not None:
                record["default"] = param.default
        elif isinstance(param, TyperArgument):
            record["type"] = _parameter_type(param)
        params.append(record)
    return {
        "command": usage,
        "description": command.help or "",
        "parameters": params,
    }


def discover_commands() -> list[dict[str, Any]]:
    """Describe executable commands from the registered Typer/Click tree."""
    scan_command = get_command(app)
    entries = [_command_entry(cast(TyperCommand | TyperGroup, scan_command), "semlint")]
    root = get_command(discovery_app)
    root_context = Context(root, info_name="semlint")

    def visit(group: TyperGroup, prefix: str, parent: Context) -> None:
        for name, command in group.commands.items():
            command_path = f"{prefix} {name}"
            context = Context(command, info_name=command_path, parent=parent)
            if isinstance(command, TyperGroup):
                visit(command, command_path, context)
            elif isinstance(command, TyperCommand):
                entries.append(_command_entry(command, command_path))

    if isinstance(root, TyperGroup):
        visit(root, "semlint", root_context)
    return entries


@self_app.command("list")
def list_commands() -> None:
    """List each available command and its usage in a single line."""
    for command in discover_commands():
        description = " ".join(command["description"].split())
        suffix = f" - {description}" if description else ""
        typer.echo(f"{command['command']}{suffix}")


discovery_app.add_typer(self_app, name="self")


@app.command()
def scan(
    paths: Annotated[
        list[Path],
        typer.Argument(help="One or more files, directories, or glob patterns to scan."),
    ],
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            "-t",
            min=0.0,
            max=1.0,
            help="SemHash similarity threshold.",
        ),
    ] = 0.90,
    min_block_tokens: Annotated[
        int, typer.Option("--min-block-tokens", min=1, help="Ignore shorter blocks.")
    ] = 10,
    split_mode: Annotated[
        SplitMode,
        typer.Option("--split", help="Block splitting mode: auto, paragraph, or markdown."),
    ] = SplitMode.AUTO,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="Maximum number of clusters to display.")
    ] = None,
    fail_above: Annotated[
        float | None,
        typer.Option(
            "--fail-above",
            min=0.0,
            max=1.0,
            help="Exit 1 when context redundancy exceeds this ratio.",
        ),
    ] = None,
    output: Annotated[
        Literal["text", "json"],
        typer.Option("--output", help="Output format: text or json."),
    ] = "text",
    model: Annotated[str | None, typer.Option("--model", help="Model2Vec model name/path.")] = None,
    sort: Annotated[
        tuple[SortOrder, SortCategory],
        typer.Option(
            "--sort",
            "-s",
            help="Sort clusters by asc/desc and occurrences, similarity, or estimated-savings.",
        ),
    ] = (SortOrder.DESC, SortCategory.ESTIMATED_SAVINGS),
) -> None:
    """Scan paths, directories, or glob patterns for redundant instruction blocks."""
    try:
        report = analyze(
            paths,
            AnalysisConfig(
                threshold=threshold,
                min_block_tokens=min_block_tokens,
                split_mode=split_mode,
                model=model,
            ),
        )
    except (OSError, RuntimeError, ImportError) as exc:
        typer.echo(f"semlint: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        render_json(report, limit=limit, sort=sort)
        if output == "json"
        else render(report, limit=limit, sort=sort)
    )
    if fail_above is not None and report.context_redundancy > fail_above:
        raise typer.Exit(1)


def main() -> None:
    import sys

    args = sys.argv[1:]
    if args and args[0] == "self":
        discovery_app(args=args)
    else:
        app(args=args)


if __name__ == "__main__":
    main()
