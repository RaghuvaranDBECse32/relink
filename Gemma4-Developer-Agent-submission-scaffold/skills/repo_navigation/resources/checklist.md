# Repository repair checklist

- Identify the repository language and package manager from manifests.
- Locate the implementation, callers, and tests.
- Reproduce the failure when feasible.
- Prefer the smallest behavior-preserving fix.
- Run a focused test before a broad suite.
- Inspect diff, whitespace, imports, and unintended file changes.
- Keep test changes out of the patch unless the task explicitly requests test additions and the harness permits them.
