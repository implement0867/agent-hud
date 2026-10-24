# agent_findings

1. Skill call returned only "Launching skill: agent-hud:board" with no body visible to me; I had to guess the table/input-column markdown syntax (`Owner {agent, user}` in header). Write accepted it with no error, and the user's values later appeared at checklist/row/col, so the syntax worked. The write result gave no sign of it at the time. Recovered.
2. Part numbering: heading is part 1, table rows are parts 2.., header row is not a part. Cell refs are checklist/<row part>/<col>, where Owner=2, Hours=3, Done=4 and col 1 is the Step text. Inferred, not documented in any result I saw.
3. Monitor timeout_ms schema max is 3600000 but the tool caps it at 10 min, so I re-armed every 10 min. Round 1 waited ~10 min for the user; later rounds took 2-3 min.
4. Every turn event was TRUNCATED in the monitor notification ("...(truncated)"). I had to call `read` each round to learn what the turn contained, and the user's chat message was always cut off.
5. The user edited my risks card (added "(no CI job exists yet)"); the truncated turn did not show it as an `edit` diff. I found it only by comparing the card text (edited: true). Recoverable.
6. Turn delivery was confusing: the same turn's notification was delivered under every monitor id I had opened (old, still-live monitors too), in round 3 three times. I never stopped the older monitors, so duplicates piled up. Also the user said "the board did not queue that edit" (test suite owner), yet the value was already in the board's values when I read. So a turn can lag the board's state.
7. A put of the checklist with inserted or moved rows kept values, reactions and comments on the right rows (matched by row text), and moved the arrow dst and comment refs (checklist/4 became checklist/9). Good, but I couldn't know beforehand. Rejected risks/5 was reported as "retired". The write result for fills returns an empty `parts`, so there is no confirmation of what was filled; I verified with read.
8. `read` with `since` still returned all cards in full, not only changes, so it saved little.
9. The user said they could not delete the stale arrow; I removed it with `unlink` (arrow-2824158c). Users have no obvious way to delete arrows; the arrow id is only in read output.
10. The user's stated hours total (9.5) did not match the values (11). Nothing in the tools computes totals.

Round 3: user approved the checklist; I said it is agreed. Done.

## Verdict (worst problems for an agent, ranked)
1. Monitor turns arrive truncated, so the user's message and most actions are cut off. Every round needs an extra `read`, and the read can't say which actions were new (no diff, `since` returns whole cards).
2. Duplicate and ambiguous turn delivery: re-armed monitors keep delivering the same turn under different task ids, so an agent can't tell one turn from several or whether older monitors are still live. The 10-minute monitor cap forces re-arming and makes this worse. The user also reported edits that were not queued.
3. Unwritten conventions: no visible table/input-column syntax (the skill body wasn't shown) and part numbering (heading is part 1, header row not a part, cell refs row/col). Write results for `fill` return an empty `parts`, so nothing confirms success.
