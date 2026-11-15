# Python Upgrade Copilot — Project Brief

**Status:** approved MVP concept

## 1. Context

The project is a standalone exercise demonstrating skills in:

- building an end-to-end RAG system,
- integrating LLMs through an API,
- preparing and versioning data,
- analyzing Python code,
- testing and evaluating LLM systems,
- integrating with GitHub Actions,
- documenting decisions, limitations, costs and results.

The code, architecture, evaluation data and quality criteria are developed independently.

## 2. Problem

Tools such as Dependabot and Renovate can open a pull request that updates a dependency, but the fact that a new version exists does not answer:

- which places in the code may break,
- which documented change causes the risk,
- how trustworthy the diagnosis is,
- which tests are worth running or adding.

Python Upgrade Copilot connects a dependency version change with the library's official documentation and with how the library is actually used in the repository.

## 3. Value Proposition

When a dependency update is detected, the tool posts a report on the pull request containing:

1. the potentially affected file and line number,
2. the library API being used,
3. a description of the documented change,
4. a quote from and a link to the official source,
5. the confidence level of the diagnosis,
6. a suggested test or migration step.

Every risk claim must follow from a cited source. Insufficient evidence must lead to an explicit "no confirmed risk" answer rather than a guess.

## 4. Target User

The first user is a Python developer reviewing a dependency-update pull request in a small or medium-sized repository.

The project also serves as a portfolio piece: it should show a deliberate use of RAG and LLMs to solve a concrete problem, not just a "chat with your documents" demo.

## 5. Scope of v0.1

The first public release supports:

- Python 3.12,
- projects managed with `uv`,
- exact dependency versions read from `uv.lock`,
- the Pydantic library,
- a controlled Pydantic 1 → 2 migration case,
- official Pydantic migration guides, release notes and documentation,
- static analysis of Python code without executing it,
- a report generated locally through a CLI,
- a GitHub Action that maintains a single comment on the pull request,
- the OpenAI API for embeddings and report generation.

`pydantic/bump-pydantic` serves as a reference point during evaluation. The project does not copy its features or compete with it as an automated codemod. Its purpose is to produce an auditable risk report.

## 6. Scope of v0.2

After a working v0.1 is published, the plan is to:

- extract a common interface for documentation sources,
- add a SQLAlchemy adapter,
- test the SQLAlchemy 1.4 → 2.0 migration,
- confirm that the core is not hard-wired to Pydantic,
- extend the evaluation set,
- polish the documentation and the project demo.

## 7. Out of Scope for the MVP

The MVP does not include:

- support for arbitrary PyPI packages,
- Poetry, `requirements.txt`, Pipenv or other lockfiles,
- automatic code modification,
- automatic approval or merging of pull requests,
- running code or tests from the analyzed repository,
- a web interface,
- FastAPI,
- an MCP server,
- an elaborate agent,
- patch generation,
- full support for pull requests from forks and from Dependabot,
- training or fine-tuning models.

These may be considered only after v0.1 has been delivered and measured.

## 8. Example Flow

1. A pull request changes the Pydantic version in `uv.lock`.
2. The GitHub Action compares the base and target versions.
3. The Pydantic adapter selects the official documents for that version range.
4. The retriever finds passages describing potentially relevant changes.
5. The AST analyzer locates imports and uses of the relevant APIs in the repository.
6. The matching layer links the evidence to specific places in the code.
7. The model produces structured conclusions based solely on the provided context.
8. The renderer creates or updates a single comment on the pull request.

## 9. Data Assumptions

- Only official library materials are a source of truth.
- Every chunk in the index keeps at least:
  - the library name,
  - the version range,
  - the document and section title,
  - the canonical URL,
  - the chunk text,
  - the date or version identifier of the source.
- Documentation is fetched from a versioned, reproducible source whenever one is available.
- Licensing and reuse terms of the documentation must be checked before a prebuilt index is published.
- The index must not mix information about incompatible versions.

## 10. RAG Assumptions

- The RAG pipeline is built without a heavy orchestration framework.
- The OpenAI API provides embeddings and the report-generation model.
- Model names are configurable; they are not part of the domain logic.
- The API key is passed through `OPENAI_API_KEY` and never ends up in the repository or in logs.
- The first index is small and can run locally without an external vector database.
- Vector retrieval is compared against a simple text baseline.
- Generation must not add claims that the retrieved passages do not support.
- The model output has a validated, structured schema before the comment is rendered.

## 11. Code Analysis Assumptions

- The analysis relies primarily on the standard library `ast` module.
- The tool recognizes direct imports, aliases, and basic calls or attribute accesses.
- The MVP does not need to resolve dynamic imports, monkey patching or generated code.
- The tool does not execute code from the repository and does not install its dependencies.
- Every finding includes the file path, the line number and the recognized symbol.
- Heuristics and their limitations are explicitly described and tested.

## 12. Report Format

The pull request comment contains:

- a summary of the analyzed version change,
- the number of risks found per confidence level,
- a section for each finding,
- the file path and line number,
- the recognized API usage,
- a description of the risk,
- a quote from and a link to the official source,
- a suggested test or manual check,
- a clear disclaimer that the report does not replace running the tests.

Subsequent runs of the Action update the existing comment, identified by a hidden marker, instead of creating a new one.

## 13. GitHub Action and Security

- The first demo runs on a regular pull request opened from a branch in a controlled repository.
- The Action does not use `pull_request_target` to check out and run untrusted code.
- Minimal workflow permissions are declared explicitly.
- Writing the comment requires only the necessary pull request or issue permissions.
- Secrets are not exposed to workflows triggered from untrusted forks.
- Code and documentation content is treated as untrusted data that may contain prompt injection.
- The system prompt forbids following instructions found in the analyzed data.
- GitHub Actions limitations regarding secrets in Dependabot pull requests are documented explicitly. Full Dependabot integration is not a v0.1 completion criterion.

## 14. Proposed Tech Stack

- Python 3.12,
- `uv`,
- `pytest`,
- Ruff,
- mypy,
- OpenAI API,
- `ast`,
- `packaging`,
- `httpx`,
- Typer or an equivalent lightweight CLI,
- NumPy or a simple local vector store,
- GitHub Actions,
- a Docker-based Action.

Dependencies are limited to those that solve a concrete problem. FastAPI and an external vector database are not needed for the MVP.

## 15. Logical Components

### Lockfile diff

Compares the base and target `uv.lock` and returns the version change of the supported library.

### Documentation source adapter

Fetches and normalizes official materials for a library and version range.

### Ingestion and index

Splits documents into chunks, stores metadata and builds the local index.

### Retriever

Selects documentation passages relevant to the detected symbols and the version change.

### Python usage analyzer

Locates uses of the library API using the AST.

### Risk matcher

Links detected usages to documented changes and assigns a confidence level.

### Report generator

Validates the model's structured output and renders the Markdown report.

### GitHub integration

Finds the project's previous comment and creates or updates it.

## 16. Evaluation

The evaluation set should contain at least 20 controlled cases:

- examples of real incompatibilities,
- usages not affected by the change,
- import aliases,
- similar names unrelated to the library,
- cases with insufficient evidence,
- correct and intentionally broken files.

Measured:

- recall of known issues,
- number of false alarms,
- correctness of file and line attribution,
- correctness and relevance of citations,
- share of claims without evidence,
- execution time,
- cost of a single analysis,
- stability of the result across repeated runs.

Minimum quality criteria for v0.1:

- no uncited risk claims,
- all links in the controlled set point to the correct official source,
- correct detection of at least 80% of the prepared positive cases,
- explicit marking of uncertainty instead of a forced diagnosis,
- repeatable updating of a single pull request comment.

## 17. Definition of Done for v0.1

In a controlled repository there is a pull request that updates Pydantic. The GitHub Action:

1. detects the version change,
2. analyzes the code without executing it,
3. finds the known risk cases,
4. posts a single readable comment,
5. points to exact locations in the code,
6. backs every claim with an official quote,
7. runs again without duplicating the comment,
8. has automated tests and documented limitations.

Completing ingestion, creating a vector database or running in a notebook alone does not mean the project is done.

## 18. Risks

### Weak linkage between documentation and code

Mitigation: a small, controlled migration scope, AST analysis, an explicit confidence level and the option to answer "insufficient evidence".

### Model hallucinations

Mitigation: structured output, mandatory citations, source validation and tests for unsupported claims.

### Scope too broad

Mitigation: v0.1 supports only Pydantic and `uv.lock`; a second library is added only after the first version is published.

### Secrets in GitHub Actions

Mitigation: the first demo uses a controlled internal pull request; forks and Dependabot stay out of scope.

### Similarity to existing tools

Mitigation: a focus on auditable documentation → code usage → risk mapping, rather than automatic version bumps or bulk refactoring.

### API cost and latency

Mitigation: a small index, caching, a limit on the number of passages, measuring the cost of every run and configurable models.

## 19. Deferred Decisions

After a working v0.1, it can be decided:

- whether an agent and tool calling are needed,
- whether to expose the core through MCP,
- whether to support Dependabot through a different permission architecture,
- whether to add automatic fixes,
- whether an API service is needed,
- which further libraries offer the best return on development effort.

None of these decisions may delay the release of the first working vertical slice.
