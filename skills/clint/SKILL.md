---
name: clint
description: Use the local `clint` CLI to find and quantify redundant information in agent instruction corpora, including SKILL.md, AGENTS.md, prompts, and text rules. Trigger when the user asks to audit instruction files, locate repeated rules, estimate context-token savings, inspect duplication, or enforce a redundancy threshold in CI. Prefer this skill whenever such a corpus needs analysis, even if the user does not name clint.
---

# Analyze instruction corpora with clint

Use `clint` to locate likely duplicate instruction paragraphs and estimate their context cost. The tool is read-only: it reports candidates and never edits the scanned files.

## Discover the current CLI

The command list is generated from clint's registered Typer definitions. If unsure about a flag or syntax, run:

```bash
clint self list
clint --help
```

Use `uv run clint` when working from this repository and the global `clint` command is unavailable. The repository's `just build` builds a versioned package, not a scan; do not run it just to inspect a corpus.

## Run a scan

Pass one or more exact paths, directories, or glob patterns. Quote globs so clint—not the invoking shell—expands them consistently:

```bash
clint ./skills
clint ./skills ./rules/AGENTS.md
clint './skills/**/*.md' './prompts/*.txt'
```

The default `--split auto` mode uses Markdown parsing for `.md` files and blank-line paragraph splitting for other supported text files. Markdown boundaries include paragraphs (including list and blockquote paragraphs), fenced/indented code, HTML blocks, and tables; headings and front matter are not treated as instruction blocks. Use `--split paragraph` to force blank-line splitting or `--split markdown` to force Markdown parsing.

The default output is readable terminal text. Use JSON when the user or a downstream script needs structured output:

```bash
clint ./skills --output json
```

Useful controls:

- `--split auto|paragraph|markdown`: Choose extension-aware, blank-line, or Markdown-aware block boundaries. `auto` is the default.
- `-t` / `--threshold`: SemHash similarity threshold from 0 to 1 (default `0.90`).
- `--min-block-tokens`: Ignore shorter paragraphs (default `10`).
- `--limit N`: Show only the first N clusters; corpus summary metrics still cover the full scan.
- `-s/--sort <asc|desc> <occurrences|similarity|estimated-savings>`: Choose cluster ordering. Default is descending estimated savings.
- `--fail-above RATIO`: Exit non-zero if estimated corpus redundancy exceeds the ratio, useful in CI.
- `--model MODEL`: Select a Model2Vec model when needed.

Example CI check:

```bash
clint ./skills ./AGENTS.md --fail-above 0.10 --output json
```

Use a ratio such as `0.10`, not a percentage such as `10`.

## Interpret results carefully

- Auto mode uses Markdown parsing for `.md` files and paragraph splitting otherwise. Paragraph mode splits on blank lines only. Markdown mode uses parser-provided line maps and recognizes paragraphs, code blocks, HTML blocks, and tables; headings and front matter are skipped, and no section metadata is inferred.
- Each occurrence gives a file and line range plus the original paragraph text. Use these locations to inspect the actual source before judging a match.
- Similarity clusters are candidates, not proof that two rules are interchangeable. Review negation, scope, conditions, exceptions, and procedural context; semantically similar instructions can still differ in an important constraint.
- Token savings are estimates based on word counts. Per-cluster redundant tokens assume keeping the shortest occurrence; this is a potential-savings estimate, not a recommendation to keep that particular wording or a tokenizer-accurate context measurement.
- A first semantic run may need to download and cache the local Model2Vec model. It runs locally on CPU afterward; there is no external LLM or API call.
- Overlapping input paths are deduplicated. Unmatched paths or globs are errors rather than silently ignored.

Do not edit instruction files just because clint reports a cluster. If the user asks to consolidate rules, inspect every occurrence, identify the actual shared invariant, preserve meaningful differences, and make edits only within the user's requested scope. Otherwise, present findings and let the user decide what to change.
