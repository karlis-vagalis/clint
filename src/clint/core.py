from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import field
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict
from pydantic.dataclasses import dataclass

WORD_RE = re.compile(r"[\w][\w'-]*", re.UNICODE)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?$")
REFERENCE_RE = re.compile(r"^\s*(?:see|refer to)\s+\[[A-Z][A-Z0-9_-]*\]\.?\s*$", re.I)


@dataclass(frozen=True)
class Block:
    path: str
    start_line: int
    end_line: int
    heading: str | None
    text: str
    tokens: int
    rule_id: str | None = None

    @property
    def location(self) -> str:
        return f"{self.path}:{self.start_line}-{self.end_line}"


@dataclass(frozen=True)
class AnalysisConfig:
    threshold: float = 0.90
    min_block_tokens: int = 10
    extensions: frozenset[str] = frozenset({".md", ".txt"})
    model: str | None = None


@dataclass
class Cluster:
    blocks: list[Block]
    similarity: float
    exact: bool = False

    @property
    def total_tokens(self) -> int:
        return sum(block.tokens for block in self.blocks)

    @property
    def redundant_tokens(self) -> int:
        return self.total_tokens - min(block.tokens for block in self.blocks)


@dataclass
class Report:
    files_scanned: int
    blocks_scanned: int
    total_tokens: int
    exact_duplicate_tokens: int
    clusters: list[Cluster] = field(default_factory=list)

    @property
    def redundant_tokens(self) -> int:
        return sum(cluster.redundant_tokens for cluster in self.clusters)

    @property
    def unique_tokens(self) -> int:
        return max(0, self.total_tokens - self.redundant_tokens)

    @property
    def context_redundancy(self) -> float:
        return self.redundant_tokens / self.total_tokens if self.total_tokens else 0.0

    @property
    def exact_duplicate_percentage(self) -> float:
        return self.exact_duplicate_tokens / self.total_tokens if self.total_tokens else 0.0

    @property
    def semantic_redundancy_percentage(self) -> float:
        return self.context_redundancy


def normalize(text: str) -> str:
    return " ".join(WORD_RE.findall(text.casefold()))


def token_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def stable_id(text: str) -> str:
    return sha256(normalize(text).encode()).hexdigest()[:12]


def scan_paths(root: Path, extensions: frozenset[str]) -> list[Path]:
    paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    return sorted(p for p in paths if p.suffix.lower() in extensions)


def parse_file(path: Path, root: Path, min_tokens: int) -> list[Block]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    blocks: list[Block] = []
    heading: str | None = None
    pending: list[str] = []
    start = 0

    def flush(end: int) -> None:
        nonlocal pending, start
        text = "\n".join(pending).strip()
        pending = []
        if not text or token_count(text) < min_tokens or REFERENCE_RE.match(text):
            return
        match = re.search(r"\[([A-Z][A-Z0-9_-]*)\]", text)
        blocks.append(
            Block(
                str(path.relative_to(root)),
                start + 1,
                end + 1,
                heading,
                text,
                token_count(text),
                match.group(1) if match else None,
            )
        )

    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        is_bullet = bool(re.match(r"^\s*(?:[-*+] |\d+[.)] )", line))
        if match:
            flush(index - 1)
            heading = match.group(1).strip()
        elif not line.strip():
            flush(index - 1)
        elif is_bullet:
            flush(index - 1)
            pending, start = [line.strip()], index
            flush(index)
        else:
            if not pending:
                start = index
            pending.append(line.strip())
    flush(len(lines) - 1)
    return blocks


class SemHashRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    index: int


def analyze(root: Path, config: AnalysisConfig) -> Report:
    paths = scan_paths(root, config.extensions)
    blocks = [
        block
        for path in paths
        for block in parse_file(
            path, root if root.is_dir() else path.parent, config.min_block_tokens
        )
    ]
    clusters: list[Cluster] = []
    exact_tokens = 0
    if blocks:
        from semhash import SemHash

        model: Any = None
        if config.model:
            from model2vec import StaticModel

            model = cast(Any, StaticModel.from_pretrained(config.model))
        records = [
            SemHashRecord(text=block.text, index=index).model_dump()
            for index, block in enumerate(blocks)
        ]
        semhash = SemHash.from_records(records=records, columns=["text"], model=model)
        neighbors = semhash.index.query_threshold(semhash.index.vectors, threshold=config.threshold)
        graph: dict[int, list[tuple[int, float]]] = defaultdict(list)
        indexed_items = semhash.index.items
        for row_number, row in enumerate(neighbors):
            if not row:
                continue
            source_record = indexed_items[row_number][0]
            source = SemHashRecord.model_validate(source_record).index
            for record, score in row:
                target = SemHashRecord.model_validate(record).index
                if source == target:
                    continue
                if (
                    blocks[source].rule_id
                    and blocks[target].rule_id
                    and blocks[source].rule_id != blocks[target].rule_id
                ):
                    continue
                graph[source].append((target, float(score)))

        visited: set[int] = set()
        for index in range(len(blocks)):
            if index in visited or index not in graph:
                continue
            stack, members, scores = [index], set(), []
            while stack:
                current = stack.pop()
                if current in members:
                    continue
                members.add(current)
                for neighbor, score in graph[current]:
                    scores.append(score)
                    if neighbor not in members:
                        stack.append(neighbor)
            visited.update(members)
            if len(members) < 2:
                continue
            matched = [blocks[item] for item in sorted(members)]
            exact = len({normalize(item.text) for item in matched}) == 1
            if exact:
                exact_tokens += sum(item.tokens for item in matched[1:])
            clusters.append(
                Cluster(
                    matched,
                    min(scores, default=1.0),
                    exact,
                )
            )
    return Report(
        len(paths), len(blocks), sum(block.tokens for block in blocks), exact_tokens, clusters
    )
