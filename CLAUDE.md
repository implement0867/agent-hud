# Rules for Claude

- After each push, open a pull request for the branch if it has none. A pushed branch that has no pull request gets lost.
- Each pull request has its own branch from `origin/main`, named for its issue, such as `ccr-e9f4af93-95hbzj-82`. A merged pull request's branch is never reused: the next change starts a new branch from `origin/main`.
- Commit only through `make check && git commit`.
- Each `match` must be provably exhaustive: name each remaining case, then end with `case _:` that calls `typing.assert_never`, even when the type checker reports that case as unreachable.
- Judge the design of the code before you build on it. When a decision is wrong, such as a structure that exists only because an earlier change copied it, say so first and in plain words, and open an issue for it. Do not build on it, add a layer around it, or wait for the user to find it.
- Nobody has installed this app. Do not keep code for compatibility with an earlier version: a breaking change is acceptable.
