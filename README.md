# clint

`clint` is a small, local Python CLI for finding redundant information in agent instruction corpora: `SKILL.md`, `AGENTS.md`, prompts, rules, and other Markdown/text files.

It answers: **how many tokens are consuming context without adding unique information, and where are they?**

## Quick start

```bash
uv sync
uv run clint ./skills
uv run clint ./skills --threshold 0.90 --min-block-tokens 10
uv run clint ./skills --json > report.json
uv run clint ./skills --fail-above 0.10
```

`skillcheck` is also installed as a compatibility alias. The command exits with `1` when `--fail-above` is exceeded and `2` for invalid input/errors.

### Stronger semantic matching

SemHash with local Model2Vec embeddings is the default semantic engine. It loads its small CPU model on first run (and caches it locally). For an explicit alternate Model2Vec model, use:

```bash
uv run clint ./skills --model minishlab/potion-base-8M --threshold 0.90
```

SemHash and Model2Vec run locally on CPU. No API, LLM, vector database, server, or GPU is needed.

## What it scans

- Recursively scans `.md` and `.txt` files.
- Parses paragraphs and list items into blocks, preserving file, line range, heading, original text, and stable rule IDs such as `[GIT-04]`.
- Ignores blocks below `--min-block-tokens` and intentional references such as `See [GIT-04].`.
- Clusters likely duplicates without modifying source files.
- Chooses a deterministic canonical occurrence using configured canonical prefixes, then completeness/token count, then path.

Similarity is intentionally configurable because generic phrases can be false positives. Review clusters before replacing instructions.

## JSON output

The schema is intentionally plain JSON; see [`examples/report.json`](examples/report.json). Top-level fields include `files_scanned`, `blocks_scanned`, `total_tokens`, `exact_duplicate_percentage`, `semantic_redundancy_percentage`, `estimated_unique_tokens`, `estimated_redundant_tokens`, `estimated_context_token_savings`, and `clusters`.

Each cluster includes similarity, all source blocks, canonical location, token counts, and a suggested action. `context_redundancy` is token-weighted:

```text
estimated_redundant_tokens / total_tokens
```

This is an estimate, not a tokenizer-specific bill. The initial version counts word tokens for transparent, consistent reporting.

## Development

```bash
uv run pytest
uv run ruff check src tests
uv run ty check src
```

The project uses Python 3.13+, Pydantic-validated dataclasses and models, and a modular `src/clint` package (parser/scanner, SemHash clustering, metrics, reporting, and Typer CLI). Structured SemHash inputs and JSON report output are validated with Pydantic. It does not automatically edit files.
