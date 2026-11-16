# Pydantic documentation: 1 → 2 source set

Unmodified copies of pages from the official Pydantic documentation, used as the knowledge base for the Pydantic 1 → 2 analysis.

| | |
|---|---|
| Repository | [pydantic/pydantic](https://github.com/pydantic/pydantic) |
| Tag | `v2.14.3` |
| Commit | [`ea492e04654ab7f7a1f9287ea912419452ead4dd`](https://github.com/pydantic/pydantic/tree/ea492e04654ab7f7a1f9287ea912419452ead4dd/docs) |
| License | MIT, see [LICENSE](LICENSE) (copied from the same commit) |

## Files

- `documents.jsonl`: one page per line. `text` is the Markdown source exactly as stored in the repository at the commit above; the other fields are provenance metadata (`source_ref`, `canonical_url`, the page title from the site navigation).
- `manifest.json`: tag and commit, the list of pages, the fetch time and a SHA-256 checksum of `documents.jsonl`.

## Regenerating

```bash
uv run upgrade-copilot docs fetch --tag v2.14.3 --migration 1_to_2
```

Every file is read at the commit the tag resolves to, so regenerating yields the same `documents.jsonl`; only `fetched_at` in the manifest changes.
