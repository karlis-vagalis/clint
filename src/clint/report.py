from __future__ import annotations

import json
from io import StringIO
from typing import Any

from pydantic import BaseModel, ConfigDict
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .core import Cluster, Report, SortCategory, SortOrder, sort_clusters


class BlockOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    start_line: int
    end_line: int
    text: str
    tokens: int


class ClusterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    similarity: float
    exact: bool
    total_tokens: int
    estimated_redundant_tokens: int
    estimated_saving: float
    blocks: list[BlockOutput]


class ReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files_scanned: int
    blocks_scanned: int
    total_tokens: int
    exact_duplicate_percentage: float
    semantic_redundancy_percentage: float
    context_redundancy: float
    estimated_unique_tokens: int
    estimated_redundant_tokens: int
    estimated_context_token_savings: int
    clusters: list[ClusterOutput]


def cluster_output(cluster: Cluster, number: int) -> ClusterOutput:
    total_tokens = cluster.total_tokens
    redundant_tokens = cluster.redundant_tokens
    return ClusterOutput(
        number=number,
        similarity=round(cluster.similarity, 4),
        exact=cluster.exact,
        total_tokens=total_tokens,
        estimated_redundant_tokens=redundant_tokens,
        estimated_saving=redundant_tokens / total_tokens if total_tokens else 0,
        blocks=[
            BlockOutput(
                file=block.path,
                start_line=block.start_line,
                end_line=block.end_line,
                text=block.text,
                tokens=block.tokens,
            )
            for block in cluster.blocks
        ],
    )


def output_model(
    report: Report,
    limit: int | None = None,
    sort: tuple[SortOrder, SortCategory] = (
        SortOrder.DESC,
        SortCategory.ESTIMATED_SAVINGS,
    ),
) -> ReportOutput:
    ordered_clusters = sort_clusters(report.clusters, order=sort[0], category=sort[1])
    if limit is not None:
        ordered_clusters = ordered_clusters[:limit]
    return ReportOutput(
        files_scanned=report.files_scanned,
        blocks_scanned=report.blocks_scanned,
        total_tokens=report.total_tokens,
        exact_duplicate_percentage=report.exact_duplicate_percentage,
        semantic_redundancy_percentage=report.semantic_redundancy_percentage,
        context_redundancy=report.context_redundancy,
        estimated_unique_tokens=report.unique_tokens,
        estimated_redundant_tokens=report.redundant_tokens,
        estimated_context_token_savings=report.redundant_tokens,
        clusters=[
            cluster_output(cluster, index) for index, cluster in enumerate(ordered_clusters, 1)
        ],
    )


def as_dict(
    report: Report,
    limit: int | None = None,
    sort: tuple[SortOrder, SortCategory] = (
        SortOrder.DESC,
        SortCategory.ESTIMATED_SAVINGS,
    ),
) -> dict[str, Any]:
    return output_model(report, limit=limit, sort=sort).model_dump(mode="json")


def render(
    report: Report,
    limit: int | None = None,
    sort: tuple[SortOrder, SortCategory] = (
        SortOrder.DESC,
        SortCategory.ESTIMATED_SAVINGS,
    ),
) -> str:
    data = output_model(report, limit=limit, sort=sort)
    stream = StringIO()
    console = Console(
        file=stream,
        force_terminal=False,
        color_system=None,
        width=100,
        highlight=False,
    )
    console.print(Rule("clint · instruction redundancy report", style="bright_blue"))

    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")
    summary.add_row("Files scanned", str(data.files_scanned))
    summary.add_row("Blocks scanned", str(data.blocks_scanned))
    summary.add_row("Total word tokens", f"{data.total_tokens:,}")
    summary.add_row("Exact duplicate share", f"{data.exact_duplicate_percentage:.1%}")
    summary.add_row("Semantic redundancy", f"{data.semantic_redundancy_percentage:.1%}")
    summary.add_row("Estimated unique tokens", f"{data.estimated_unique_tokens:,}")
    summary.add_row("Estimated redundant tokens", f"{data.estimated_redundant_tokens:,}")
    summary.add_row("Potential context-token savings", f"{data.estimated_context_token_savings:,}")
    console.print(summary)

    for cluster in data.clusters:
        console.print()
        console.print(
            Rule(
                f"Cluster #{cluster.number} · similarity {cluster.similarity:.2f}"
                f" · {'exact' if cluster.exact else 'semantic'}",
                style="bright_blue",
            )
        )
        cluster_stats = Table(show_header=False, box=None, padding=(0, 2))
        cluster_stats.add_column("Metric", style="dim")
        cluster_stats.add_column("Value", justify="right")
        cluster_stats.add_row("Occurrences", str(len(cluster.blocks)))
        cluster_stats.add_row("Tokens in cluster", str(cluster.total_tokens))
        cluster_stats.add_row("Estimated redundant tokens", str(cluster.estimated_redundant_tokens))
        cluster_stats.add_row("Estimated savings", f"{cluster.estimated_saving:.1%}")
        console.print(cluster_stats)
        console.print()

        for index, block in enumerate(cluster.blocks):
            if index:
                console.print()
            if block.start_line == block.end_line:
                location = f"{block.file}:{block.start_line}"
            else:
                location = f"{block.file}:{block.start_line}-{block.end_line}"
            console.print(Text(location, style="bold cyan"))
            for offset, line in enumerate(block.text.splitlines()):
                console.print(Text(f"{block.start_line + offset:>5} │ {line}"))

    return stream.getvalue().rstrip()


def render_json(
    report: Report,
    limit: int | None = None,
    sort: tuple[SortOrder, SortCategory] = (
        SortOrder.DESC,
        SortCategory.ESTIMATED_SAVINGS,
    ),
) -> str:
    return json.dumps(as_dict(report, limit=limit, sort=sort), indent=2, ensure_ascii=False)
