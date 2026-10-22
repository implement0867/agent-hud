# Rules for Claude

- After each push, open a pull request for the branch if it has none. A pushed branch that has no pull request gets lost.
- Before each push, check whether the branch's pull request is merged. If it is, start the branch again from `origin/main` and open a new pull request.
- Commit only through `make check && git commit`.
