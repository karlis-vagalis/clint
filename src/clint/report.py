from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from .core import Cluster, Report


class BlockOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    start_line: int
    end_line: int
    heading: str | None
    text: str
    tokens: int
    rule_id: str | None


class ClusterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    similarity: float
    exact: bool
    canonical: str
    total_tokens: int
    canonical_tokens: int
    redundant_tokens: int
    potential_saving: float
    blocks: list[BlockOutput]
    suggested_action: str


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
    return ClusterOutput(
        number=number,
        similarity=round(cluster.similarity, 4),
        exact=cluster.exact,
        canonical=cluster.canonical.location,
        total_tokens=total_tokens,
        canonical_tokens=cluster.canonical.tokens,
        redundant_tokens=cluster.redundant_tokens,
        potential_saving=cluster.redundant_tokens / total_tokens if total_tokens else 0,
        blocks=[
            BlockOutput(
                file=block.path,
                start_line=block.start_line,
                end_line=block.end_line,
                heading=block.heading,
                text=block.text,
                tokens=block.tokens,
                rule_id=block.rule_id,
            )
            for block in cluster.blocks
        ],
        suggested_action="Keep canonical; replace other occurrences with references.",
    )


def output_model(report: Report) -> ReportOutput:
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
            cluster_output(cluster, index) for index, cluster in enumerate(report.clusters, 1)
        ],
    )


def as_dict(report: Report) -> dict[str, Any]:
    return output_model(report).model_dump(mode="json")


def render(report: Report) -> str:
    data = output_model(report)
    lines = [
        "clint — instruction redundancy report",
        "=" * 40,
        f"Files scanned:                 {data.files_scanned}",
        f"Blocks scanned:                {data.blocks_scanned}",
        f"Total tokens:                  {data.total_tokens}",
        f"Exact duplicate percentage:    {data.exact_duplicate_percentage:.1%}",
        f"Semantic redundancy percentage: {data.semantic_redundancy_percentage:.1%}",
        f"Estimated unique tokens:        {data.estimated_unique_tokens}",
        f"Estimated redundant tokens:     {data.estimated_redundant_tokens}",
        f"Potential context-token saving: {data.estimated_context_token_savings}",
    ]
    for cluster in data.clusters:
        lines.extend(["", f"Cluster #{cluster.number}", f"Similarity: {cluster.similarity:.2f}"])
        for block in cluster.blocks:
            lines.extend([f"\n{block.file}:{block.start_line}-{block.end_line}", f'"{block.text}"'])
        lines.extend(
            [
                "",
                f"Total tokens:      {cluster.total_tokens}",
                f"Canonical tokens:  {cluster.canonical_tokens}",
                f"Redundant tokens:  {cluster.redundant_tokens}",
                f"Potential saving:  {cluster.potential_saving:.1%}",
                f"Suggested canonical: {cluster.canonical}",
                f"Suggested action: {cluster.suggested_action}",
            ]
        )
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(as_dict(report), indent=2, ensure_ascii=False)
