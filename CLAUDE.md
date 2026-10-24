# Rules for Claude

- After each push, open a pull request for the branch if it has none. A pushed branch that has no pull request gets lost.
- Each pull request has its own branch from `origin/main`, named for its issue, such as `ccr-e9f4af93-95hbzj-82`. A merged pull request's branch is never reused: the next change starts a new branch from `origin/main`.
- Commit only through `make check && git commit`.
