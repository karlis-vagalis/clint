from typer.testing import CliRunner

from clint.cli import discover_commands, discovery_app


def test_capability_listing_is_generated_from_cli_definitions() -> None:
    commands = discover_commands()
    by_command = {command["command"]: command for command in commands}

    scan_usage = (
        "clint <PATH> [--threshold <threshold>] [--min-block-tokens <min-block-tokens>] "
        "[--limit <limit>] [--fail-above <fail-above>] [--output <output>] [--model <model>]"
    )
    assert scan_usage in by_command
    assert "clint self list" in by_command
    scan_options = {
        parameter["name"]: parameter for parameter in by_command[scan_usage]["parameters"]
    }
    assert scan_options["limit"]["flags"] == ["--limit"]
    assert scan_options["output"]["choices"] == ["text", "json"]
    assert "0x" not in scan_options["path"]["type"]


def test_self_list_prints_one_full_command_per_line() -> None:
    result = CliRunner().invoke(discovery_app, ["self", "list"])

    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("clint <PATH> [--threshold <threshold>]")
    assert " - Scan a file" in lines[0]
    assert lines[1].startswith("clint self list")
