---
description: Open the agent-hud board and follow the user's actions on it
---

Call the board's `listen` tool. Give the user the page URL, which is the URL that `listen` returns with `ws://` changed to `http://` and the path changed to `/`, keeping the `token` query parameter. Open the websocket URL with the Monitor tool, with the description `board`, so that you get each turn of the user: their actions up to the moment they send. Then call `read` and tell the user what is on the board.

$ARGUMENTS
