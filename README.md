# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas. The user approves, rejects or questions each item, and the agent reads that feedback
over MCP.

## Install

```sh
claude plugin marketplace add implement0867/agent-hud
claude plugin install agent-hud@agent-hud
```

The plugin needs [uv](https://docs.astral.sh/uv/). At the start of each session, its hook starts the app on
port 7676 unless the app already runs there, so all sessions share one board. The plugin connects the MCP
server `board` at `http://127.0.0.1:7676/mcp/`, and adds the `board` skill and the `/agent-hud:board`
command, which gives the page URL and follows the user's actions.

The app serves the board page at `/`. The page shows each card and updates when the agent writes. The user
pans the board with a drag on empty space or a scroll, and zooms with Ctrl or ⌘ and a scroll or with the zoom
buttons. On the page, the user creates notes (cards by the user), edits the markdown of any card, reacts to,
comments on and links the cards and their parts, fills input cells and sends messages. An edit is a `put`, so
it clears the feedback on that card. With `AGENT_HUD_STATE_FILE` set, the app appends each action to
that JSONL file and replays it on start.

## Tools

| Tool | Does |
|---|---|
| `write(actions)` | acts on the board as the agent, all or nothing. Each action is `put {id, md}`, `remove {id}`, `react {ref, reaction}`, `unreact {ref}`, `comment {ref, text}`, `say {text}`, `fill {ref, value}`, `link {id, src, dst, text}` or `unlink {id}`, with a `kind`. A `ref` is a card id, or a card id and the number of a list item or table body row, counted together in document order, such as `plan/2`. A table header such as `cost {number}`, `done {check}`, `note {text}` or `size {S, M, L}` makes an input column, and `fill` sets its cell by row and column, such as `plan/2/3`. An arrow links two refs; a put or remove of a card drops the arrows that touch it. |
| `read()` | the board as JSON: `{"cards": {"plan": {"md": "1. a", "author": "agent"}}, "threads": {"plan/1": {"reaction": "approve", "comments": [{"id": "9f2c…", "author": "user", "text": "why a?"}]}}, "values": {"plan/2/3": 3.5}, "arrows": {"why": {"src": "risk", "dst": "plan/1", "text": "blocks", "author": "agent"}}}` |
| `listen()` | the websocket URL of the user's actions, in the same shape with an `id` and `author`; open it with Claude Code's Monitor tool |

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
| `make check` | ruff format and lint, basedpyright; tsc, eslint, prettier |
| `make serve` | start the app on port 7676 |
| `cd ui && npm run build` | build the UI into the server package; commit the build |
| `claude --plugin-dir .` | run Claude Code with the plugin from this checkout |
| `cd ui && npm run dev` | Vite dev server, which sends `/ws` to the running server |
