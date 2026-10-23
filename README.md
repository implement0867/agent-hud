# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

![The agent puts a plan and code; the user rejects a step, comments, asks about a code line and sends; the agent answers and puts a new plan, and the old plan with its feedback shows in the history](docs/demo.gif)

## Install

```sh
claude plugin marketplace add implement0867/agent-hud
claude plugin install agent-hud@agent-hud
```

The plugin needs [uv](https://docs.astral.sh/uv/). At the start of each session, its hook starts the app on
port 7676 unless the app already runs there, so all sessions share one board. The plugin connects the MCP
server `board` at `http://127.0.0.1:7676/mcp/`, and adds the `board` skill and the `/agent-hud:board`
command, which gives the page URL and follows the user's actions.

The hook asks `GET /health` on the port, which the app answers with its name and version. The same version
of the app answering means nothing to do. An older version is stopped and the new one started. Another
program on the port is an error, and the hook says so. The hook waits up to 15 s for the app to answer,
then exits 1 with a message if it does not, and `uv` missing from PATH is a message too. The first start
installs the dependencies, which takes longer. The app logs to `$XDG_STATE_HOME/agent-hud/server.log`
and records its pid in `server.pid` next to it, with `~/.local/state` as the default; to stop it, `kill`
that pid.

| Variable | Does |
|---|---|
| `AGENT_HUD_PORT` | the port, 7676 by default; the hook, the MCP server URL and `make serve` read it |
| `AGENT_HUD_TOKEN` | the token that `/mcp/` needs as a bearer token, which the plugin sends from this variable; unset, `/mcp/` is open to local processes and the app makes a token for the sockets alone |
| `AGENT_HUD_STATE_DIR` | the directory of the token file and, by default, of the board files; `$XDG_STATE_HOME/agent-hud` by default, with `~/.local/state` for the XDG state home |
| `AGENT_HUD_STATE_FILE` | the JSONL file that the app appends each action to and replays on start; `board.jsonl` in the state dir by default. On a clear and on shutdown the app compacts it: `board.json` next to it takes the board at the start of the user's turn, and the file keeps the turn alone |
| `AGENT_HUD_STATIC_DIR` | the directory of the built UI; the one in the package by default |

The hook of the first session of the day starts the app, so these must be set in the environment that
starts that session, such as the shell profile.

The app answers `/ws` and `/agent` only with its token as the `token` query parameter. The URL that `listen`
returns carries it, and so does the page URL that `/agent-hud:board` gives; the app also writes it to
`$XDG_STATE_HOME/agent-hud/token`, readable by the user only. `/ws` also needs the page's own Origin, which
the browser always sends, so a local script cannot act as the user.

The app serves the board page at `/`, a whiteboard that updates when the agent writes:

| On the page | Does |
|---|---|
| Drag a card's header | moves the card; the board keeps its place for everyone |
| Double-click empty space | writes a note there |
| Double-click a card's text, or `E` | edits its markdown; ⌘↵ or a click outside saves, Esc cancels |
| Click a list item, table row, code line or card header | selects it and opens its feedback: reactions and comments |
| Hover a part | shows quick reactions; `A`, `R` and `Q` react to the selection |
| Drag the dot on a part's right edge | draws an arrow to the part or card under the pointer; click an arrow to label or remove it |
| Delete | removes the selected card or arrow |
| Drag empty space, Space+drag, scroll | pans |
| ⌘ or Ctrl + scroll, `+`, `-`, `0`, `1` | zooms, resets, fits all cards |
| Send, or ⌘↵ | sends the user's actions since the last send to the agent, as one turn; a chat message sends them too |
| Chat | messages to and from the agent, and each comment on a part; a ref such as `plan/2` shows the part; `M` focuses it |
| The pill at the top left | the agent's socket: no agent connected, or connected and working on the user's turn, or connected and waiting for it |
| History, `H`, or a card's version chip | shows the earlier versions of the cards with the feedback they had |
| Clear | after a confirm, moves every card to its history with its feedback, and empties the board, its arrows and the chat |

A code block whose fence gives `file=src/app.py start=40` shows the file name and line numbers, and a `diff` block
tints its added and removed lines. A card with code is wider.

An edit is a `put`: the feedback on the parts whose text it keeps stays with them, and the rest moves to the card's history.

## Tools

| Tool | Does |
|---|---|
| `write(actions)` | acts on the board as the agent, all or nothing. Each action is `put {id, md}`, `remove {id}`, `react {ref, reaction}`, `unreact {ref}`, `comment {ref, text}`, `say {text}`, `fill {ref, value}`, `link {id, src, dst, text}`, `unlink {id}`, `move {id, x, y}` or `clear`, with a `kind`. A `ref` is a card id, or a card id and the number of a list item, table body row or code line, counted together in document order, such as `plan/2`. Nested list items and the code lines inside a list item count too, so the item shown as "2." is not always part 2. A table header such as `cost {number}`, `done {check}`, `note {text}` or `size {S, M, L}` makes an input column, and `fill` sets its cell by row and column, such as `plan/2/3`. An arrow links two refs. A put of a card keeps the feedback, values and arrows on the parts whose text is unchanged, matched by text in order, and on the card itself when its markdown is unchanged; the rest goes with the card as it was to `history`. A remove moves all of it there, and a clear does so for every card and empties the arrows and the chat. Each author has their own reaction on a part. Returns the cards added and replaced, the parts whose feedback went to the history, the arrows dropped, and the parts of each card put, by number: `{"added": ["plan"], "replaced": [], "retired": [], "dropped": [], "parts": {"plan": {"1": "parse", "2": "render"}}}`. A batch puts each card at most once. |
| `read()` | the board as JSON, to read once and again when the agent is unsure: `{"cards": {"plan": {"md": "1. a", "author": "agent"}}, "threads": {"plan/1": {"reactions": {"user": "approve"}, "comments": [{"id": "9f2c…", "author": "user", "text": "why a?"}]}}, "values": {"plan/2/3": 3.5}, "arrows": {"why": {"src": "risk", "dst": "plan/1", "text": "blocks", "author": "agent"}}, "messages": [{"id": "1c2d…", "author": "user", "text": "go ahead", "ref": null}], "positions": {"plan": {"x": 0.0, "y": 0.0}}, "parts": {"plan": {"1": "a"}}, "history": {}}`. Each message has a `ref`, which names the part for a comment. `parts` gives the text of each part of each card by its number. `read(history=true)` also returns the earlier versions of each card. `read(cards=["plan"])` returns those cards alone, with the feedback, values, arrows, positions and history on them, and `read(since=id)` returns the messages after the message or comment with that id. |
| `listen()` | the websocket URL of the user's turns; open it with Claude Code's Monitor tool. Each line is one turn, the changes that the user made since the last send: `{"actions": [{"id": "9f2c…", "author": "user", "body": {"kind": "react", "ref": "plan/2", "reaction": "reject"}, "parts": {"plan/2": "rewrite the cache"}}]}`, where `parts` has the text of each part that the action names, as it was when the user acted. A code line's text starts with its file and line number. A `put` on a card that was on the board comes as `{"kind": "edit", "id": "plan", "diff": "@@ -1,2 +1,2 @@…"}`, a unified diff of its markdown. |

The listed schema of `write` is one object with the fields of all kinds of action, and the description gives the fields of
each kind, so that the tools cost the agent fewer tokens. The server still checks each action against the model of its kind.

## Layout

```text
server/          Python 3.12 package (uv, ruff, basedpyright), with the built UI in agent_hud/static
ui/              React + Vite + strict TypeScript (ESLint strictTypeChecked, Prettier)
.claude-plugin/  plugin and marketplace manifests
hooks/           the hook that starts the app
skills/ commands/  the board skill and command
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node 22.

| Command | Does |
|---|---|
| `cd server && uv run playwright install chromium` | install the browser that the page tests drive, once |
| `make check` | ruff format and lint, basedpyright, pytest; tsc, eslint, prettier |
| `make serve` | start the app on port 7676, or `AGENT_HUD_PORT` |
| `cd ui && npm run build` | build the UI into the server package; commit the build |
| `claude --plugin-dir .` | run Claude Code with the plugin from this checkout |
| `cd ui && npm run dev` | Vite dev server, which sends `/ws` to the running server |
