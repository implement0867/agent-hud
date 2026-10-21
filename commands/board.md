---
description: Open the agent-hud board and follow the user's actions on it
---

Call the board's `listen` tool. Give the user the page URL, which is the URL that `listen` returns with `ws://` changed to `http://` and the path changed to `/`. Open the websocket URL with the Monitor tool, so that you get each action of the user. Then call `read` and tell the user what is on the board.

$ARGUMENTS
