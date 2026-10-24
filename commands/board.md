---
description: Open the agent-hud board and follow the user's actions on it
---

Call the board's `listen` tool. Give the user the page URL, which is the `url` that `listen` returns with `ws://` changed to `http://` and the path changed to `/`, keeping the `token` query parameter. Open the `url` with the Monitor tool's `ws` source, with `timeout_ms` as long as the tool allows; when your Monitor tool takes a command only, run the `command` that `listen` returns with it instead. Either way you get each turn of the user: their actions up to the moment they send. Open the monitor again each time it ends. Then call `read` and tell the user what is on the board.

$ARGUMENTS
