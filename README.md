# agent-hud

A shared browser canvas for Claude Code. The agent puts plans, options and tables on the
canvas as markdown cards. The user selects words on a card and comments on them, draws arrows
from them, checks boxes and edits the markdown, and the agent reads that feedback over MCP.

![The agent puts a plan and code; the user comments on a step and on a code line and sends; the agent answers and puts a new plan, and the old plan with its feedback shows in the history](docs/demo.gif)

## Install

```sh
claude plugin marketplace add implement0867/agent-hud
claude plugin install agent-hud@agent-hud
```

The plugin needs [uv](https://docs.astral.sh/uv/). At the start of each session, its hook starts the app on
port 7676 unless the app already runs there, so all sessions use one app. The plugin connects the MCP
server `board` at `http://127.0.0.1:7676/mcp/`, and adds the `board` skill and the `/agent-hud:open`
command, which gives the page URL and follows the user's actions.

A board is a named workspace, not tied to a project. Its name is 1 to 64 letters, digits, `_` or `-`, such as
`agent-hud`. The agent makes a board with `create_board`, and each other tool takes the name of the board it acts
on: there is no default board, and no tool makes a board as a side effect. An unknown name, a missing name or a
name that is not one is an error. So two sessions on two boards do not see each other's cards or get each other's
turns. The URL that `listen` returns names its board, and so does the page URL; the page's pill names the board it
shows and lists the others, and a click opens one. The page without a board in its URL lists the boards.

Each board is also the MCP resource `board://<name>`, the board as JSON. A client that subscribes to it with
`subscriptions/listen` gets `notifications/resources/updated` at each change of the board, and one that asks for
the list gets `notifications/resources/list_changed` when a board is created or deleted.

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
| `AGENT_HUD_BOARDS_DIR` | the directory of the SQLite file of each board, named by the board's name, which the app appends each action to and replays on start; `boards` in the state dir by default. On a clear and on shutdown the app compacts each: its checkpoint takes the board at the start of the user's turn, and the actions from there alone stay. A file from an earlier version, whose cards had numbered parts and inputs, stops the app with a ValidationError, and so does a file whose name is not a board name: move it out of the directory. One process holds the files, so a second one on the same state dir, such as a second uvicorn worker, does not start |
| `AGENT_HUD_STATIC_DIR` | the directory of the built UI; the one in the package by default |
| `AGENT_HUD_IDLE_SECONDS` | how long the app runs with no page or monitor connected and no request before it stops, 3600 by default; 0 keeps it running |
| `AGENT_HUD_MONITOR_CHARS` | how many characters of one event Claude Code's Monitor shows, 3000 by default; a turn with more goes to the monitor in as many events as it needs |
| `AGENT_HUD_MONITOR_GAP` | the seconds between the events of one turn, 0.5 by default, so that the Monitor shows them apart: it joins events closer than 0.2 s |

The hook of the first session of the day starts the app, so these must be set in the environment that
starts that session, such as the shell profile.

The app answers `/ws`, `/agent` and `/boards` only with its token as the `token` query parameter, and the sockets
take the board's name as the `board` query parameter, which they need. The URL that `listen` returns
carries both, and so does the page URL that `/agent-hud:open` gives; the app also writes the token to
`$XDG_STATE_HOME/agent-hud/token`, readable by the user only. `/ws` also needs the page's own Origin, which
the browser always sends, so a local script cannot act as the user. `/boards` lists each board with its card count
and the state of its agent.

The app serves the board page at `/`, a whiteboard that updates when the agent writes:

| On the page | Does |
|---|---|
| A new card | goes to the free space below the others, on a grid of three columns; the board keeps its place for every tab and reload, and the agent reads it. A new card lands clear of every card; after that cards may cross, and the card last touched, by the user or by the agent's new version or move, shows on top. A card that arrives out of view gets a chip at the nearest edge, "new: risks", which shows the card on a click |
| A card | is its markdown from the first line, with no strip above it: headings, text, lists, tables and code on the design's type scale, in Source Sans 3 and JetBrains Mono. Its right margin holds the bubbles of its threads |
| Click a card, or drag its padding | selects the card, or moves it and puts it on top of the cards it crosses; the arrow keys move the selected card, by 32 pixels with Shift |
| Hover a card | shows its frame with a handle at each edge and corner: a drag sets the width, the height or both, and the board keeps them for everyone. A card no one resized is as wide as its content needs, between 256 pixels and a column of the grid, 640, and as tall as its text; a card shorter than its text scrolls, with fades at its ends |
| Select words on a card | shows a toolbar above them with Comment, or `C`, and Arrow. Comment opens a small thread beside the words, with the quoted words, the comments, and a field to reply in; the first comment starts the thread there. The words of each thread have an accent underline |
| A thread's bubble | sits in the card's margin level with its words, or after them with the look's "in line" threads; it is filled and counts the agent's new comments, which clear when the user opens the thread, and is an outline when nothing is new |
| Arrow, then click a card | draws an arrow from the end of the selected words to that card, which shows a ring under the pointer; the words keep an underline in the arrow's colour, and the arrow keeps its ends as the cards move. A click on an arrow or its label selects it, to label or remove it |
| A box, `[ ]` or `[x]` | in a task item or a table cell shows as a checkbox; a click flips it in the markdown, which the agent gets as an edit |
| Double-click empty space | writes a note there, kept whole in view; a click outside saves it |
| Double-click a card, `E` or Enter | turns the card into its markdown, in a monospace field with a ring, and a footer that says ⌘↵ saves. A click outside or Esc closes an unchanged editor; with changes, a click outside asks to save or discard, and Esc asks for a second Esc. When the words of a thread or an arrow are gone from the new text, the save asks once and says how many go to the history. When the agent puts a new version while the editor is open, the save is refused and the editor says so, with a button to save over the new version |
| Delete | removes the selected card or arrow; a toast offers to undo the removal for a few seconds, and the History drawer has Restore on each removed card |
| `?`, or the keyboard button | opens the sheet of shortcuts, which names ⌘ or Ctrl for the platform |
| Hover a chat message | shows when it was said |
| The server stops | the page keeps the last board, greyed, with a banner that it tries again; it reconnects with a delay that grows to ten seconds, and a half-written chat message stays |
| A comment half written | stays in the box, keyed by its thread, when the agent's new version closes the thread, and comes back when the thread opens again |
| Drag empty space, Space+drag, scroll | pans |
| ⌘ or Ctrl + scroll, `+`, `-`, `0`, `1` | zooms, resets, fits all cards in the part of the view that the chat leaves free. Below 1280 px the chat sits above the toolbar, and the toolbar wraps |
| Send, or ⌘↵ | the one Send, in the chat beside the message box: sends the message, when there is one, and the user's actions since the last send to the agent, as one turn; its count says how many. The chevron beside it lists them as the user reads them, one line per action, grouped by card: the quoted words and the comment, or the card for an edit; a click on a line shows the card or opens the thread, Esc or a press outside closes the list. The turn carries no moves or resizes. Until Send, an unsent comment has a dashed outline on its bubble and in the chat; after Send nothing does |
| Chat | messages to and from the agent, and each comment, which starts with the words of its thread and opens the thread on a click; `M` focuses the message box. Its header counts the threads on the board, and a click shows the next. A click on its title collapses the chat to a button. A drag on its left edge sets its width, which the browser keeps. Closed, it counts the agent's new messages and the changes to send |
| The pill at the top left | the board the page shows, with a menu of every board on the app, each with its cards and whether an agent follows it, which opens the one clicked, and Clear this board at its end; and the agent's socket: no agent connected, or connected and working on the user's turn, or connected and waiting for it; and the turns sent that no agent has taken, which wait for the next monitor, across restarts |
| History, `H`, or a card's History link | shows the earlier versions of the cards with their threads, in a drawer docked at the left; the board moves right by the drawer's width while it is open, and back when it closes |
| The agent's new version of a card | shows the change in the card's text since the version the user last saw: the removed words struck through on a red tint and the added words on a green one, or, with the look's "lines" changes, the old and the new lines with − and + on tinted rows. "Hide changes · History" sits at the right of the title line; Hide changes shows the plain new version, and a card with an earlier version offers Show changes |
| The agent removes the user's arrow | a toast names the arrow, with Put it back and OK |
| Clear this board, in the board menu | asks first, in the page, naming the board and how many cards go to the history with their threads and how many arrows and messages go for good; then empties the board, its arrows and the chat |
| The toolbar | Note, History, Shortcuts, Look, the zoom with its percentage, and Fit, each with its label. The percentage is Reset: it takes the view back to full size at the start, and shows an arrow while the view is elsewhere. Fit shows every card at the zoom that holds them all, in the part of the view that the chat leaves free |
| Look | the viewer's look, which the browser keeps as `agent-hud-look`: the light or the dark theme on stone, the accent (sky, violet, emerald or amber), the density (comfortable or compact), the card radius (8, 12 or 16), the size of the card text, where the bubbles of threads sit, and whether changes show as words or lines |

A code block shows on a light sunken ground, with keywords in the accent; its lines do not wrap, and it scrolls sideways.
A fence that gives `file=src/app.py start=40` shows the file name above the block and line numbers in a faint column,
and a `diff` block tints its added and removed lines. A card with code is wider.

An edit is a `put`: the threads on words that it keeps stay with them, and the rest move to the card's history.

## Tools

| Tool | Does |
|---|---|
| `create_board(name)` | makes an empty board with the name, and returns `{"name": "plan", "cards": 0, "agent": "away"}`; an error when the name is not one or a board has it |
| `list_boards()` | each board, as `create_board` returns it, with its number of cards and the state of its agent |
| `delete_board(name)` | removes the board and its file for good; an error when no board has the name or a monitor is open on it |
| `write(name, actions)` | acts on the board as the agent, all or nothing, and returns `{"added": ["plan"], "replaced": [], "retired": [{"card": "plan", "quote": "on a fresh board"}], "dropped": []}`: the cards added and replaced, the threads that went to the history, and the arrows dropped. Each action is `put {id, md, version?}`, `remove {id}`, `restore {id}`, `comment {card, quote?, occurrence?, text}`, `say {text}`, `link {id, card, quote?, occurrence?, dst, text?}`, `unlink {id}`, `move {id, x, y}`, `resize {id, width?, height?}` or `clear`, with a `kind`. A card is markdown only. A `quote` names words of a card as the card shows them, without markdown, with white space that does not count; empty, it names the card as a whole. When the card shows the quote at more than one place, `occurrence` says which, from 0; without it, the action is refused and the error says how many places there are. A comment joins the thread on the same words, or starts one there; an arrow goes from words to the card `dst`. A put of a card keeps each thread and arrow on words that the new text still has, at the place nearest to where they were, and threads on the card as a whole; the threads on words that are gone go with the card as it was to `history`, and their arrows drop. A replaced card keeps its first `author`, with `edited` true when the other author put the latest version. A put with `version`, the number of earlier versions the card has, is refused when the card has another number or is gone. A remove moves all of it there, a restore puts a removed card back as its last version was, and a clear does so for every card and empties the arrows and the chat. A resize keeps the dimension it leaves out. A batch puts each card at most once. |
| `read(name)` | the board as JSON, to read once and again when the agent is unsure: `{"cards": {"plan": {"md": "1. a", "author": "agent", "edited": false}}, "threads": {"9f2c…": {"card": "plan", "quote": "a", "occurrence": 0, "comments": [{"id": "9f2c…", "author": "user", "text": "why a?", "thread": "9f2c…", "at": "…"}]}}, "arrows": {"why": {"card": "risk", "quote": "the cache", "occurrence": 0, "dst": "plan", "text": "blocks", "author": "agent"}}, "messages": [{"id": "1c2d…", "author": "user", "text": "go ahead", "thread": null, "at": "…"}], "positions": {"plan": {"x": 0.0, "y": 0.0}}, "sizes": {}, "history": {}}`. Each message has a `thread`, which names the thread of a comment. `read(name, history=true)` also returns the earlier versions of each card. `read(name, cards=["plan"])` returns those cards alone, with the threads, arrows, positions, sizes and history on them, and `read(name, since=id)`, with the id of a turn, message or comment, returns the cards that changed after it and the messages after it; an id the board no longer has gives the whole board. |
| `listen(name)` | `{"url": "ws://127.0.0.1:7676/agent?board=agent-hud&token=…", "command": "uv run … agent-hud-turns 'ws://…'", "board": "agent-hud", "monitors": 0}`: the websocket URL of the user's turns on the board, for Claude Code's Monitor tool with a websocket source, a shell command that prints each turn as its lines, for a Monitor tool that takes a command, the board's name, and the monitors already open on the board, the session's own included: above what the session opened, another session follows the same board, and each turn goes to both. Give the monitor the description `board`, which Claude Code shows with each event. Each turn is one event of lines: a head, `{"turn": "9f2c…", "actions": 2}`, with the id of the send or chat message that ended the turn and its number of actions, then one line per action, such as `{"kind": "comment", "card": "plan", "quote": "rewrite the cache", "text": "the cache is shared"}`, without the fields that are none. A `put` on a card that was on the board, such as a checked box, comes as `{"kind": "edit", "id": "plan", "diff": "@@ -1,2 +1,2 @@…"}`, a unified diff of its markdown. The Monitor shows 3000 characters of an event and 500 of a line, so a turn with more comes as several events half a second apart, each with a head that counts them, `{"turn": "9f2c…", "actions": 24, "frame": 2, "of": 3}`, with the actions in order across them; `AGENT_HUD_MONITOR_CHARS` and `AGENT_HUD_MONITOR_GAP` set the size and the gap. The same turn id from two monitors is one turn. |

The listed schema of `write` is one object with the fields of all kinds of action, and the description gives the fields of
each kind, so that the tools cost the agent fewer tokens. The server still checks each action against the model of its kind before the tool runs, and a wrong action comes back as Pydantic's validation error, which names the action's index in the list, from 0, its kind and the field.

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
| `cd ui && npm test` | the unit tests of the UI's library, with vitest and fast-check: properties such as that a new card lands clear of every card on the board, and that a quote cut from a card's text is found where it was cut |

A merged pull request bumps the versions it changes, in a commit to main: the UI's in `ui/package.json` when it
changes `ui/`, the server's in `server/pyproject.toml` when it changes `server/`, and the plugin's in
`.claude-plugin/plugin.json` when it changes either of those, `hooks/`, `commands/`, `skills/` or `.claude-plugin/`.
The bump is a patch, or a minor or major one with the label `minor` or `major` on the pull request, and the plugin's
new version gets the tag `v<version>`. A rebuilt UI changes `server/` too, so it bumps the server as well.
