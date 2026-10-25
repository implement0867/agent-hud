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
port 7676 unless the app already runs there, so all sessions use one app. The plugin connects the MCP
server `board` at `http://127.0.0.1:7676/mcp/`, and adds the `board` skill and the `/agent-hud:open`
command, which gives the page URL and follows the user's actions.

Each project has its own board. The plugin sends the project directory of the session in the `X-Agent-Hud-Board`
header of each MCP request, and the app keeps a board for each, with an id of the directory's last name and six
hex digits of the whole, such as `agent-hud-3f2a1c`, so that two sessions in two projects do not see each other's
cards or get each other's turns. A request without the header, such as one from a client that is not the plugin,
acts on the board `shared`. The URL that `listen` returns names the session's board, and so does the page URL;
the page's pill names the board it shows and lists the others, and a click opens one.

The hook asks `GET /health` on the port, which the app answers with its name, its version and the build
fingerprint it was started with, a checksum of the server's sources that the hook computes. The same build
answering means nothing to do. An app from other sources, or an agent-hud from before `/health`, which
serves the board page at `/`, is stopped and the new one started: the hook stops the process that
`server.pid` names, or the one that `lsof` finds on the port when it runs agent-hud's server, and says
what it found when it can stop neither. Another program on the port, with neither agent-hud's `/health`
nor its page, is an error, and the hook says so. The hook waits up to 15 s for the app to answer, then
exits 1 with a message if it does not, and `uv` missing from PATH is a message too. The first start
installs the dependencies, which takes longer. The app logs to `$XDG_STATE_HOME/agent-hud/server.log`
and records its pid in `server.pid` next to it, with `~/.local/state` as the default; to stop it, `kill`
that pid. The app stops by itself after an hour with no page or monitor connected and no request, and
the next session's hook starts it again.

| Variable | Does |
|---|---|
| `AGENT_HUD_PORT` | the port, 7676 by default; the hook, the MCP server URL and `make serve` read it |
| `AGENT_HUD_TOKEN` | the token that `/mcp/` needs as a bearer token, which the plugin sends from this variable; unset, `/mcp/` is open to local processes and the app makes a token for the sockets alone |
| `AGENT_HUD_STATE_DIR` | the directory of the token file and, by default, of the boards; `$XDG_STATE_HOME/agent-hud` by default, with `~/.local/state` for the XDG state home |
| `AGENT_HUD_BOARDS_DIR` | the directory of the SQLite file of each board, named by the board's id, which the app appends each action to and replays on start; `boards` in the state dir by default. On a clear and on shutdown the app compacts each: its checkpoint takes the board at the start of the user's turn, and the actions from there alone stay. One process holds the files, so a second one on the same state dir, such as a second uvicorn worker, does not start |
| `AGENT_HUD_STATIC_DIR` | the directory of the built UI; the one in the package by default |
| `AGENT_HUD_IDLE_SECONDS` | how long the app runs with no page or monitor connected and no request before it stops, 3600 by default; 0 keeps it running |
| `AGENT_HUD_MONITOR_CHARS` | how many characters of one event Claude Code's Monitor shows, 3000 by default; a turn with more goes to the monitor in as many events as it needs |
| `AGENT_HUD_MONITOR_GAP` | the seconds between the events of one turn, 0.5 by default, so that the Monitor shows them apart: it joins events closer than 0.2 s |

The hook of the first session of the day starts the app, so these must be set in the environment that
starts that session, such as the shell profile.

The app answers `/ws`, `/agent` and `/boards` only with its token as the `token` query parameter, and the sockets
take the board's id as the `board` query parameter, with `shared` as the default. The URL that `listen` returns
carries both, and so does the page URL that `/agent-hud:open` gives; the app also writes the token to
`$XDG_STATE_HOME/agent-hud/token`, readable by the user only. `/ws` also needs the page's own Origin, which
the browser always sends, so a local script cannot act as the user. `/boards` lists each board with its card count
and the state of its agent.

The app serves the board page at `/`, a whiteboard that updates when the agent writes:

| On the page | Does |
|---|---|
| A new card | goes to the free space below the others, on a grid of three columns; the board keeps its place for every tab and reload, and the agent reads it. A new card lands clear of every card; after that cards may cross, and the card last touched, by the user or by the agent's new version or move, shows on top. A card that arrives out of view gets a chip at the nearest edge, "new: risks", which shows the card on a click |
| Drag a card's header | moves the card and puts it on top of the cards it crosses; the board keeps its place for everyone |
| Drag a card's bottom right corner | sets its width; the board keeps it for everyone. A card no one resized is as wide as its content needs, between 256 pixels and a column of the grid, 640: a short note is small, a table with input columns shows each step on one line, and prose wraps at the column |
| Double-click empty space | writes a note there, kept whole in view; a click outside saves it, and the note opens no feedback of its own |
| Double-click a card's text, `E`, or the pencil | edits its markdown, with Save and Cancel; ⌘↵ saves too. A click outside or Esc closes an unchanged editor; with changes, a click outside keeps it open and asks to save or discard, and Esc asks for a second Esc. When a part that has feedback, values or an arrow is gone from the new text, the save asks once and says how many parts lose theirs to the history. When the agent puts a new version while the editor is open, the save is refused and the editor says so, with a button to save over the new version. An agent's card that the user edits keeps its look and says "edited by you" |
| Click a heading, paragraph, list item, table row or code line | selects it and opens its feedback: reactions and comments. The panel sits in the viewport beside the card, at full size at every zoom, clear of the other cards when a side, below or above has room, and its comments scroll under the wheel. Esc closes the panel and keeps the selection; a second Esc clears it. A click on a card's header selects the card alone, and `C` or Enter opens the feedback of the selection. A click or a focus on an input cell selects nothing |
| Hover a part | shows approve and reject before the marks the part has, which stay where they are; a click on the comment count opens the part's feedback, where a question is a comment with its mark. In a table the marks sit before the row's text, clear of its inputs. `A`, `R` and `Q` react to the selection |
| Drag the dot on a part's right edge | draws an arrow to the part or card under the pointer, at any speed: the dot's strip is there before the pointer is, and shows the dot once it arrives; a click on the dot does nothing. A click on an arrow or its label selects it, to label or remove it; arrows and labels paint under the cards, the selected label over them |
| Delete | removes the selected card or arrow; a toast offers to undo the removal for a few seconds, and the History drawer has Restore on each removed card |
| `?`, or the keyboard button | opens the sheet of shortcuts, which names ⌘ or Ctrl for the platform |
| Hover a chat message | shows when it was said |
| The server stops | the page keeps the last board, greyed, with a banner that it tries again; it reconnects with a delay that grows to ten seconds, and a half-written chat message stays |
| A comment half written | stays in the box, keyed by its part, when the agent's new version closes the panel, and comes back when the part is selected again |
| Drag empty space, Space+drag, scroll | pans |
| ⌘ or Ctrl + scroll, `+`, `-`, `0`, `1` | zooms, resets, fits all cards in the part of the view that the chat leaves free. Below 1280 px the chat sits above the toolbar, and the toolbar wraps |
| Send, or ⌘↵ | the one Send, in the chat beside the message box: sends the message, when there is one, and the user's actions since the last send to the agent, as one turn; its count says how many. The chevron beside it lists them as the user reads them, one line per action, grouped by card: the row's name, the column's title and the value for a cell, the part's text for a reaction or a comment; a click on a line shows the part, Esc or a press outside closes the list. The turn carries the last reaction on a part and the last value of a cell, when they differ from the start of the turn with what the agent wrote since, so a value on a row the agent put counts, and no moves or resizes. Until Send, each of them looks pending: a dashed amber outline on the cell or the reaction, an outlined bubble that says "unsent" for a comment or a message, and an "unsent" chip on a new or edited card; after Send nothing does |
| Chat | messages to and from the agent, and each comment on a part; a ref such as `plan/2` shows the part; `M` focuses the message box. Its header counts the feedback on the board by kind, and a click on a count shows the next part with it; a click on its title collapses the chat to a button. A drag on its left edge sets its width, which the browser keeps. Closed, it counts the agent's new messages and the changes to send |
| The pill at the top left | the board the page shows, with a menu of every board on the app, each with its cards and whether an agent follows it, which opens the one clicked, and Clear this board at its end; and the agent's socket: no agent connected, or connected and working on the user's turn, or connected and waiting for it; and the turns sent that no agent has taken, which wait for the next monitor, across restarts |
| History, `H`, or a card's version chip | shows the earlier versions of the cards with the feedback they had, in a drawer docked at the left; the board moves right by the drawer's width while it is open, and back when it closes. A version chip with a comment icon says the history holds feedback |
| The agent's new version of a card | marks the parts it added or reworded with a green bar and a title, counts them in the card's header, and lists the texts it removed under the card, struck through, until the user clicks a part of the card or edits it. A comment count with a ring says the agent commented last |
| The agent removes the user's arrow | a toast names the arrow, with Put it back and OK |
| Clear this board, in the board menu | asks first, in the page, naming the board and how many cards go to the history with their feedback and how many arrows and messages go for good; then empties the board, its arrows and the chat |
| The toolbar | Note, History, Shortcuts, the zoom with its percentage, and Fit, each with its label. The percentage is Reset: it takes the view back to full size at the start, and shows an arrow while the view is elsewhere. Fit shows every card at the zoom that holds them all, in the part of the view that the chat leaves free |

A code block whose fence gives `file=src/app.py start=40` shows the file name and line numbers, and a `diff` block
tints its added and removed lines. A card with code is wider.

An edit is a `put`: the feedback on the parts whose text it keeps stays with them, and the rest moves to the card's history.

## Tools

| Tool | Does |
|---|---|
| `write(actions)` | acts on the board as the agent, all or nothing, and returns `{"added": ["plan"], "replaced": [], "retired": [], "dropped": [], "parts": {"plan": {"1": "parse", "2": "render"}}, "tables": {"plan": [{"rows": ["2"], "columns": {"2": {"kind": "number", "name": "Hours", "options": []}}}]}, "values": {"plan/2/2": 3}}`: the cards added and replaced, the parts whose feedback went to the history, the arrows dropped, the text of each part of each card put by its number, the tables of each card put with the part numbers of their rows and their input columns by column number, and the value of each cell filled. Each action is `put {id, md, version?}`, `remove {id}`, `restore {id}`, `react {ref, reaction}`, `unreact {ref}`, `comment {ref, text}`, `say {text}`, `fill {ref, value}`, `link {id, src, dst, text}`, `unlink {id}`, `move {id, x, y}`, `resize {id, width}` or `clear`, with a `kind`. A `ref` is a card id, or a card id and the number of a heading, paragraph, list item, table body row or code line, counted together in document order, such as `plan/2`. Nested list items and the code lines inside a list item count too, and a paragraph inside a list item is text of the item, so the item shown as "2." is not always part 2. A table header such as `cost {number}`, `done {check}`, `note {text}` or `size {S, M, L}` makes an input column, and `fill` sets its cell by row and column, such as `plan/2/3`. An arrow links two refs. A put of a card keeps the feedback, values and arrows on the parts whose text is unchanged, matched by text in order, and on the card itself when its markdown is unchanged; the rest goes with the card as it was to `history`. A replaced card keeps its first `author`, with `edited` true when the other author put the latest version. A put with `version`, the number of earlier versions the card has, is refused when the card has another number or is gone. A remove moves all of it there, a restore puts a removed card back as its last version was, and a clear does so for every card and empties the arrows and the chat. Each author has their own reaction on a part. Returns the cards added and replaced, the parts whose feedback went to the history, the arrows dropped, and the parts of each card put, by number: `{"added": ["plan"], "replaced": [], "retired": [], "dropped": [], "parts": {"plan": {"1": "parse", "2": "render"}}}`. A batch puts each card at most once. |
| `read()` | the board as JSON, to read once and again when the agent is unsure: `{"cards": {"plan": {"md": "1. a", "author": "agent", "edited": false}}, "threads": {"plan/1": {"reactions": {"user": "approve"}, "comments": [{"id": "9f2c…", "author": "user", "text": "why a?"}]}}, "values": {"plan/2/3": 3.5}, "arrows": {"why": {"src": "risk", "dst": "plan/1", "text": "blocks", "author": "agent"}}, "messages": [{"id": "1c2d…", "author": "user", "text": "go ahead", "ref": null}], "positions": {"plan": {"x": 0.0, "y": 0.0}}, "widths": {}, "parts": {"plan": {"1": "a"}}, "history": {}}`. Each message has a `ref`, which names the part for a comment. `parts` gives the text of each part of each card by its number. `read(history=true)` also returns the earlier versions of each card. `read(cards=["plan"])` returns those cards alone, with the feedback, values, arrows, positions and history on them, and `read(since=id)`, with the id of a turn, message or comment, returns the cards that changed after it and the messages after it; an id the board no longer has gives the whole board. |
| `listen()` | `{"url": "ws://127.0.0.1:7676/agent?board=agent-hud-3f2a1c&token=…", "command": "uv run … agent-hud-turns 'ws://…'", "board": "agent-hud-3f2a1c", "monitors": 0}`: the websocket URL of the user's turns on the session's board, for Claude Code's Monitor tool with a websocket source, a shell command that prints each turn as its lines, for a Monitor tool that takes a command, the board's id, and the monitors already open on the board, the session's own included: above what the session opened, another session follows the same board, and each turn goes to both. Give the monitor the description `board`, which Claude Code shows with each event. Each turn is one event of lines: a head, `{"turn": "9f2c…", "actions": 2}`, with the id of the send or chat message that ended the turn and its number of actions, then one line per action, such as `{"kind": "react", "ref": "plan/2", "reaction": "reject", "parts": {"plan/2": "rewrite the cache"}}`, where `parts` has the text of each part that the line is the first in the turn to name, as it was when the user acted. A code line's text starts with its file and line number. A `put` on a card that was on the board comes as `{"kind": "edit", "id": "plan", "diff": "@@ -1,2 +1,2 @@…"}`, a unified diff of its markdown. The Monitor shows 3000 characters of an event and 500 of a line, so a turn with more comes as several events half a second apart, each with a head that counts them, `{"turn": "9f2c…", "actions": 24, "frame": 2, "of": 3}`, with the actions in order across them; `AGENT_HUD_MONITOR_CHARS` and `AGENT_HUD_MONITOR_GAP` set the size and the gap. The same turn id from two monitors is one turn. |

The listed schema of `write` is one object with the fields of all kinds of action, and the description gives the fields of
each kind, so that the tools cost the agent fewer tokens. The server still checks each action against the model of its kind.

## Layout

```text
server/          Python 3.12 package (uv, ruff, basedpyright), with the built UI in agent_hud/static
ui/              React + Vite + strict TypeScript (ESLint strictTypeChecked, Prettier)
.claude-plugin/  plugin and marketplace manifests
hooks/           the hook that starts the app
skills/ commands/  the board skill and the open command
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node 22.

| Command | Does |
|---|---|
| `cd server && uv run playwright install chromium` | install the browser that the page tests drive, once |
| `make check` | ruff format and lint, basedpyright, pytest; tsc, eslint, prettier, vitest |
| `make check-live` | the live check of the monitor channel, which `make check` skips: a nested Claude Code session with the plugin from this checkout opens its monitor and puts a plan on its board; after the Monitor tool's cap, the user's turn comes from a page socket, and the agent must write within a minute. It needs `claude` signed in and takes the cap and two minutes; `AGENT_HUD_LIVE_AFTER=60` sends the turn that many seconds after the monitor opens instead, for a quick run |
| `make serve` | start the app on port 7676, or `AGENT_HUD_PORT` |
| `cd ui && npm run build` | build the UI into the server package; commit the build |
| `claude --plugin-dir .` | run Claude Code with the plugin from this checkout |
| `cd ui && npm run dev` | Vite dev server, which sends `/ws` to the running server |
| `cd ui && npm test` | the unit tests of the UI's library, with vitest and fast-check: properties such as that a new card lands clear of every card on the board |

A merged pull request bumps the versions it changes, in a commit to main: the UI's in `ui/package.json` when it
changes `ui/`, the server's in `server/pyproject.toml` when it changes `server/`, and the plugin's in
`.claude-plugin/plugin.json` when it changes either of those, `hooks/`, `commands/`, `skills/` or `.claude-plugin/`.
The bump is a patch, or a minor or major one with the label `minor` or `major` on the pull request, and the plugin's
new version gets the tag `v<version>`. A rebuilt UI changes `server/` too, so it bumps the server as well.
