---
description: Find bugs in the codebase and suggest patches
argument-hint: [optional: file paths or scope description]
---

Launch the `bug-hunter` agent to review the code and report findings.

Scope: $ARGUMENTS

If no scope is given, default to reviewing uncommitted changes (`git diff`) first; if the working tree is clean, review files changed on the current branch vs. `main`. If the branch has no diff either, review the whole repo.

Return the agent's full report to the user unchanged.
