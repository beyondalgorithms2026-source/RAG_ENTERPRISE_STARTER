## Summary

<!-- What does this PR change and why? -->

## Changes

-

## Testing

- [ ] `python -m unittest discover -s backend/tests` passes
- [ ] `make reader-clarity-check` passes
- [ ] `make repo-hygiene-check` passes
- [ ] `ruff check . && ruff format --check .` passes
- [ ] If ACL, auth, or retrieval changed: `make scenario-validate` passes
- [ ] If frontend changed: `cd web && npx tsc --noEmit && pnpm run build` passes

## Checklist

- [ ] No secrets, credentials, or corpus data committed
- [ ] No new dependencies added without approval
- [ ] Documentation updated if behaviour changed
