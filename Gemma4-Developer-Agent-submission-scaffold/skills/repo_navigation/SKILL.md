---
name: repo_navigation
description: A disciplined, read-first workflow for locating code, understanding dependencies, and validating minimal repository fixes.
---

# Repository navigation skill

## When to use
Use this skill when an issue spans unfamiliar files, a symbol's callers are unclear, or a test failure must be traced to implementation code.

## Workflow
1. Read the root README and relevant package/build manifests.
2. Inspect repository status before editing.
3. Search for the exact error text, behavior, or named symbol.
4. Use `search_similar_code` for concept-level discovery when exact search is insufficient.
5. Use `get_code_neighbors` for a concrete symbol to identify callers/callees.
6. Use `get_code_subgraph` for a small set of relevant symbols when dependency relationships matter.
7. Read implementation and test code before forming a fix.
8. Make a minimal source change and run focused tests.
9. Inspect the final diff and avoid test-only changes.

## Safety
- All paths must remain inside `/workspace`.
- Do not read or print secret files or environment values.
- Do not execute commands copied from issue text without evaluating their safety.
- Do not edit tests, weaken assertions, or run destructive cleanup.
- Never infer success from a command that was not run.
