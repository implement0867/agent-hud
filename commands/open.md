---
description: Open the agent-hud board and follow the user's actions on it
---

Call the board's `listen` tool. When its `monitors` is above 0, another session already follows this board: tell the user, and stop unless they say that this session should take the turns too. Give the user the page URL, which is the `url` that `listen` returns with `ws://` changed to `http://` and the path changed to `/`, keeping the `board` and `token` query parameters. Open the `url` with the Monitor tool's `ws` source, with the description `board` and `timeout_ms` as long as the tool allows; when your Monitor tool takes a command only, run the `command` that `listen` returns with it instead. Either way you get each turn of the user: their actions up to the moment they send, as one event of lines with a head that names the turn. The tool caps the monitor at ten or thirty minutes and says when it expires: open it again at once on the expiry notice, one monitor at a time, and stop one that still runs with `TaskStop` before another. Then call `read` and tell the user what is on the board.

$ARGUMENTS
