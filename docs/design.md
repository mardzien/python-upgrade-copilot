# Python Upgrade Copilot — Technical Design (v0.1)

This document describes *how* the system is built. *What* it does and why is in the [project brief](project-brief.md).

## 1. Design principles

- **Every risk claim is backed by a verbatim quote** from an indexed, official source. A claim that cannot be verified is downgraded to "no confirmed risk". It is never shown as a finding.
- **Confidence is computed by deterministic rules**, not by the model's self-assessment.
- **The analyzed repository is never executed or imported.** Code and documentation are untrusted input.
- **Retrieval quality is measured, not assumed.** Vector retrieval is compared with a lexical (BM25) baseline.
- **No orchestration framework.** Every stage is a small, typed, testable unit behind a `Protocol`.

## 2. Approach

Two ways of linking documentation to code were considered:

| | Code → docs (RAG at analysis time) | Docs → change catalog (offline extraction) |
|---|---|---|
| Flow | AST finds usages → one query per symbol → retrieval → LLM assesses the risk of that usage → deterministic quote verification | An LLM extracts a catalog of breaking changes from the migration guide once; at PR time the catalog is matched to AST findings deterministically |
| Pros | Real retrieval on every PR; precise file:line attribution; works for usages nobody anticipated | Cheap, stable, highly auditable |
| Cons | Cost and variance grow with the number of distinct symbols | Hardly any retrieval at analysis time; coverage limited to what the extraction step caught |

**Chosen: code → docs.** The catalog idea may return later as a cache.

### Data flow

```
uv.lock (base, head) ──► lockfile diff ──► VersionChange(pydantic, 1.x → 2.y)
                                                │
repo *.py ──► AST usage analyzer ──► [Usage(path, line, symbol, kind, snippet)]
                                                │
prebuilt index (chunks + embeddings + manifest) │
        │                                       ▼
        └──────────► retriever (vector + BM25) ◄── query builder (symbol → query)
                              │
                              ▼  top-k chunks per symbol
                     grounded generator (LLM, structured output)
                              │
                              ▼
                     verifier (quote ⊂ chunk, chunk ∈ context)
                              │
                              ▼
                     confidence rules ──► Report ──► Markdown ──► CLI stdout / PR comment upsert
```

## 3. Domain model

Immutable dataclasses (`frozen=True, slots=True`). Pydantic v2 is used only to validate LLM output.

- `VersionChange(package, base, head)` with `base` and `head` as `packaging.version.Version`.
- `SourceDocument(library, migration_key, doc_version, doc_path, title, canonical_url, source_ref, text)`, where `source_ref` is `<tag>@<commit sha>`.
- `DocChunk(chunk_id, library, migration_key, doc_version, doc_title, section_path, canonical_url, source_ref, text)`.
- `Usage(path, line, col, symbol, kind, snippet, heuristic)`, where `symbol` is fully qualified, e.g. `pydantic.BaseModel.parse_obj`.
- `RetrievedChunk(chunk, score, retriever)`.
- `Claim(symbol, risk_description, quote, chunk_id, suggested_check, model_uncertain)`: raw generator output, before verification.
- `Finding(usage, claim, source_url, confidence)`, where `confidence` is one of `high`, `medium`, `low`.
- `Report(change, findings, unconfirmed, stats)`.

### Ports

The RAG pipeline is composed of `Protocol`s, so each stage can be swapped, faked in tests and evaluated in isolation:

- `Chunker.chunk(doc) -> list[DocChunk]`
- `Embedder.embed(texts) -> ndarray[float32]`, with L2-normalized rows
- `Retriever.retrieve(query, k) -> list[RetrievedChunk]`
- `QueryBuilder.build(symbol, usages, change) -> str`
- `Generator.assess(symbol, usages, context, change) -> (list[Claim], TokenUsage)`
- `Verifier.verify(claim, context) -> DocChunk | None`

## 4. Key decisions

### Documentation source

- Docs are fetched from the `docs/` directory of `pydantic/pydantic` at a git tag. The tag is resolved to a commit SHA, and files are downloaded from that immutable commit. The SHA is recorded in every document.
- For the 1 → 2 migration the source set is the v2 migration guide plus the v2 concept pages the migration touches. Every chunk carries `migration_key` and `doc_version`, so incompatible versions are never mixed.
- Canonical URLs are `https://docs.pydantic.dev/<major>.<minor>/<path>/#<anchor>`. Anchors reproduce the slug algorithm of the Python-Markdown `toc` extension used by the docs site, including `_1`, `_2` suffixes for duplicate headings. An automated live test checks that the anchors exist on the published site.
- Pydantic is MIT-licensed. The fetched sources ship with the license and an attribution note.

### Index

- The index is a versioned artifact in the repository: `data/index/pydantic/1_to_2/` with `chunks.jsonl`, `embeddings.npy` and `manifest.json` (embedding model, dimension, source tag and SHA, chunker version). It is built offline with `upgrade-copilot index build`. The Action only loads it, so documentation embeddings are never paid for at analysis time.
- An index is selected by **major-version transition**: `1_to_2` covers any `1.*` → `2.*` change. The report states exactly which documentation version was used. Any other change (e.g. `2.5` → `2.9`) gets a short "outside the supported range, not analyzed" comment instead of silence or an error.
- Vector search is a dot product over normalized vectors in NumPy. No external database.
- Query embeddings are cached on disk by `(model, sha256(text))`.

### Cost control

- Retrieval and generation run **once per distinct symbol**, not once per occurrence. The result is propagated to every occurrence, each with its own file and line.
- Top-k, the maximum number of symbols per run and the token budget are configurable. Every run reports tokens, estimated cost and duration.

### Grounded generation and verification

- OpenAI Structured Outputs with a Pydantic v2 schema. Model names come from configuration, never from domain code.
- Code and documentation passages are placed in clearly delimited data sections of the prompt. The system prompt forbids following instructions found in them.
- A **deterministic verifier** rejects a claim when the quote is missing, the quote is not a verbatim substring of the referenced chunk (after whitespace normalization), or the chunk was not part of the context given to that call. Rejected claims are counted in the run statistics. They never disappear silently.

### Confidence rules

- `high`: the quote is verified **and** the quote or its section title names the recognized symbol (or its documented v1 name).
- `medium`: the quote is verified, but the symbol is not named in it.
- `low`: the quote is verified, but the model flagged uncertainty **or** the AST match is heuristic (e.g. an attribute on a variable of unknown type).
- No verified evidence: "no confirmed risk".

Thresholds will be revisited after the first evaluation run.

### AST analyzer

Recognized patterns:

- `import pydantic`, `import pydantic as pd`, `from pydantic import X [as Y]`, `from pydantic.sub import X`;
- subclasses of `BaseModel`;
- decorators such as `@validator` and `@root_validator`;
- class-method calls on `BaseModel` subclasses defined in the same repository (`User.parse_obj(...)`);
- inner `Config` classes;
- `.dict()` / `.json()` on instances (heuristic, therefore `low` confidence).

Limitations are documented in the README and covered by tests.

### Interfaces

- **CLI** (Typer):
  - `upgrade-copilot analyze --repo PATH --base-lock FILE --head-lock FILE [--format md|json]`
  - `upgrade-copilot docs fetch`
  - `upgrade-copilot index build`
  - `upgrade-copilot eval run`
- **GitHub Action**:
  - Docker-based, triggered on `pull_request`, with `permissions: { contents: read, pull-requests: write }`.
  - The base `uv.lock` is read with `git show <base_sha>:uv.lock`.
  - The comment carries the marker `<!-- python-upgrade-copilot:v1 -->` and is upserted through the GitHub REST API.
  - When `OPENAI_API_KEY` is unavailable (fork or Dependabot PRs), the Action exits with a clear warning, without failing and without commenting.
- **Demo repository**: a separate public repository with Pydantic v1 code containing the controlled cases from the brief's evaluation section, and a pull request that bumps Pydantic to v2.

### Comparison with bump-pydantic

v0.1 includes a qualitative comparison on the demo repository: what `bump-pydantic` rewrites, what this report flags, and what neither catches. An automated comparison in the evaluation harness comes later.

## 5. Testing

- Unit tests never touch the network. OpenAI and GitHub sit behind `Protocol`s, with fakes in tests; HTTP is tested with `httpx.MockTransport`.
- Tests that need the network or an API key are marked `@pytest.mark.live` and skipped by default and in CI.
- Fixtures: small `uv.lock` files, Python files with AST cases, and a frozen mini-index for retrieval tests.

## 6. Constraints

- Python 3.12, `uv`, Ruff, mypy in strict mode.
- Base runtime dependencies: `openai`, `httpx`, `numpy`, `packaging`, `pydantic` (v2), `typer`. Any additional dependency must solve a named problem and be justified in its pull request. Build- and evaluation-only tools live in a separate dependency group and stay out of the Action image.
- Pydantic's docs use mkdocs-material extensions (tabs, admonitions, `--8<--` snippets). Normalization either handles them or skips them explicitly, and documents the choice.
- `OPENAI_API_KEY` is read only from the environment and is never logged.
