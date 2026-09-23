from pathlib import Path

from clint.core import AnalysisConfig, Block, Cluster, Report, analyze
from clint.report import as_dict, render


def test_text_report_shows_separated_cluster_and_source_line_numbers(tmp_path: Path) -> None:
    text = "Preserve formatting when editing existing documents in this repository.\n"
    (tmp_path / "a.md").write_text(text)
    (tmp_path / "b.md").write_text(text)
    report = analyze(tmp_path, AnalysisConfig(min_block_tokens=3))

    output = render(report)

    assert "Cluster #1" in output
    assert "a.md:1" in output
    assert "    1 │ Preserve formatting" in output
    assert "Estimated savings" in output
    assert "Suggested" not in output


def test_cluster_limit_shows_largest_redundancy_first() -> None:
    small = Cluster(
        blocks=[
            Block("small.md", 1, 1, None, "short text", 2),
            Block("small-copy.md", 1, 1, None, "short text", 2),
        ],
        similarity=0.95,
    )
    large = Cluster(
        blocks=[
            Block("large.md", 1, 1, None, "a longer piece of instruction text", 6),
            Block("large-copy.md", 1, 1, None, "a longer piece of instruction text", 6),
        ],
        similarity=0.91,
    )
    report = Report(4, 4, 16, 0, [small, large])

    data = as_dict(report, limit=1)

    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["blocks"][0]["file"] == "large.md"
    assert data["total_tokens"] == 16
    assert data["estimated_redundant_tokens"] == 8


def test_json_report_has_no_canonical_or_suggested_actions(tmp_path: Path) -> None:
    text = "Preserve formatting when editing existing documents in this repository.\n"
    (tmp_path / "a.md").write_text(text)
    (tmp_path / "b.md").write_text(text)
    report = analyze(tmp_path, AnalysisConfig(min_block_tokens=3))

    data = as_dict(report)

    assert data["clusters"][0]["blocks"][0]["start_line"] == 1
    assert "canonical" not in data["clusters"][0]
    assert "suggested_action" not in data["clusters"][0]
