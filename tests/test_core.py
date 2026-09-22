from pathlib import Path

from clint.core import AnalysisConfig, analyze, normalize, parse_file


def test_normalize_is_stable() -> None:
    assert normalize("Never FORCE-push!") == "never force-push"


def test_parser_preserves_location_and_ignores_references(tmp_path: Path) -> None:
    path = tmp_path / "rules.md"
    path.write_text(
        "# Git\n\nNever force push unless explicitly requested by the user.\n\nSee [GIT-04].\n"
    )
    blocks = parse_file(path, tmp_path, 5)
    assert len(blocks) == 1
    assert blocks[0].heading == "Git"
    assert blocks[0].start_line == 3


def test_analysis_finds_exact_duplicate_and_metrics(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "Preserve formatting when editing existing documents in this repository.\n"
    )
    (tmp_path / "b.md").write_text(
        "Preserve formatting when editing existing documents in this repository.\n"
    )
    report = analyze(tmp_path, AnalysisConfig(min_block_tokens=3, threshold=0.9))
    assert report.files_scanned == 2
    assert len(report.clusters) == 1
    assert report.exact_duplicate_tokens > 0
    assert report.context_redundancy > 0
