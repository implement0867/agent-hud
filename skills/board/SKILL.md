---
name: board
description: Show plans, options, tables and questions to the user on the agent-hud board in the browser, and read the user's feedback. Use when a plan, a choice between options, or a table needs the user's review, or when the user asks for the board.
argument-hint: "[board-name]"
---

# Board

The board is a page in the browser that you and the user share. Its MCP tools are `create_board`, `list_boards`, `delete_board`, `write_board`, `read_board` and `listen_board`. A board has a name of 1 to 64 letters, digits, `_` or `-`, and `write_board`, `read_board`, `listen_board` and `delete_board` take the name of the board they act on: there is no default board. `list_boards` lists the boards with their cards and whether an agent follows each. `create_board` makes an empty board, and only it makes one. Use one board for the session: the one the user names, or one named for the project, such as `agent-hud`, created when `list_boards` does not have it; name it in every call. `delete_board` removes a board and its file for good, only when the user asks; it refuses while a monitor is open on the board. Each board is also the MCP resource `board://<name>`, which tells its subscribers of each change.

## Connect when invoked

When the user invokes this skill, connect to the board before anything else:

1. Pick the board: the one that the arguments of the invocation name, which are `$ARGUMENTS`, else the one the user names, else one named for the project directory. Call `list_boards`, and `create_board` when the list does not have it.
2. Call `listen_board` with the name, and open a monitor as "Read feedback" and "Keep one monitor open" tell.
3. Call `read_board` and tell the user what is on the board.
4. End your reply with the page URL as a markdown link that the user can click: the `url` that `listen_board` returned, with `ws://` changed to `http://` and the path changed to `/`, keeping the `board` and `token` query parameters.

## Show content

A card is markdown, and only markdown. Write it as you would write a document; the board numbers nothing and reads no other structure.

Call `write_board` with a list of actions. They run in order, all or nothing.

- `put {id, md, version?}` adds a card of markdown, or replaces the card with that id. A thread on words that the new text still has stays with them, at the place nearest to where it was. A thread on words that are gone goes to the card's history, and an arrow from them drops. A replaced card keeps its first author, and `edited` is true on it when the other author put the latest version. With `version`, the number of earlier versions the card has, the put is refused when the card changed since you read it.
  - A fenced code block with a language name, such as ```` ```python ````, shows in colour. A block with an unknown language shows as plain text.
  - Put `file=` and `start=` after the language, such as ```` ```python file=src/app.py start=40 ````, to show the file name and the line numbers.
  - A ```` ```diff ```` block tints its added and removed lines.
  - A task item, `- [ ] step`, and a table cell of a box alone, `[ ]` or `[x]`, show as a checkbox. When the user clicks one, you get an edit of the card's markdown. Put the box column first, with an empty header cell.
- `remove {id}` removes a card. `restore {id}` puts a removed card back as its last version was.
- `clear` starts over: every card goes to its history with its threads, and the board, its arrows and the chat empty. Use it when the user moves to a new task, rather than a `remove` per card.
- `post {text}` sends a message to the user. It shows in the chat on the page.
- `comment {card, quote?, occurrence?, text}` comments on words of a card, or on the card as a whole when `quote` is empty. It joins the thread on the same words, or starts one there.
- `link {id, card, quote?, occurrence?, dst, text?}` draws an arrow from words of a card to the card `dst`.
- `move {id, x, y}` places a card on the board, in pixels. A card with no place goes to the free space below the others, on a grid of three columns 688 pixels apart, once the page shows it, and `read_board` has its place. A new card lands clear of every card; after that cards may cross, and the card last touched, by a `move` or a new version too, shows on top.
- `resize {id, width?, height?}` sets the width, the height or both of a card, in pixels, and keeps a dimension you leave out. A card that no one resized is as wide as its content needs, between 256 pixels and a column of the grid, 640, and as tall as its text. A card shorter than its text scrolls.

`write_board` returns the cards it added and replaced, the threads that went to the history, as their card and quote, and the arrows it dropped: `{"added": ["plan"], "replaced": [], "retired": [], "dropped": []}`. Put each card at most once in a batch.

When an action does not fit its kind, `write_board` applies none of the actions, and its validation error names the action by its index in the list, from 0, its kind and the field. When an action does not fit the board, the error names the action by number, from 1, and kind, and the valid choices: the cards on the board, or how many places the card shows the quote at. Fix that action and send the list again.

Put one subject on each card, with a short id such as `plan` or `risks`. Write each step or option on a line of its own, as a list item or a table row, so that the user can select it and comment on it.

## Quotes

A quote names words of a card as the page shows them: the text without markdown, so `**the** board` shows as `the board`, a link shows its text, and a code line shows its code. A quote may run across lines and blocks. White space does not count, so `tag  the\nrelease` matches `tag the release`. When the card shows the quote at more than one place, give `occurrence`, from 0 for the first place, or quote more words so that the quote is at one place. Write the user's words in a table cell or a list item as the user reads them: an owner column names the user as they name themselves, or "you", not `user`, and a column of numbers names its unit in its title, such as `Hours`.

## Read feedback

- `read_board` returns the board: the cards, the threads by id, each with its card, its quote, its occurrence and its comments, the arrows, the chat messages and comments, and the card positions and sizes. `read_board` with `history` true also returns the earlier versions of each card with their threads. `read_board` with `cards` returns those cards alone, with what is on them. `read_changes` returns only the cards that changed since you last read them and the messages since your last read, and each call moves past what it returns; after a clear, or when unsure, `read_board` the whole board again. Use them to read less when the board is large. Cards with the author `user` are the user's own cards; a card with `edited` true has its latest version from the other author, so the user edited your card or you edited the user's card. Cards that the user placed near each other belong together for the user.
- `listen_board` returns the websocket `url` of the user's turns on the board, a shell `command` that prints each turn as its lines, the `board` name and the `monitors` already open on the board, your own included. When `monitors` counts one you did not open, another session already follows this board and would get each turn too: tell the user so before you open a monitor, and open one only when they want this session to take the turns. Open the `url` with the Monitor tool's `ws` source, or, when your Monitor tool takes a command only, run the `command` with it. Set the description `board` and nothing more, and `timeout_ms` as long as the tool allows. Without a monitor, the user's sends wait, and the page tells the user to run `/agent-hud:board`. The user's comments, arrows, edits and checked boxes collect until the user clicks Send or sends a chat message. Then the monitor gets one turn with all of them, without moves or resizes; `read_board` has the positions and sizes. The page lists what the next turn carries, in the user's words, and marks each change as unsent until Send, so the user sees what you get. A turn sent while no monitor was open waits for the next monitor, across restarts, and the page says so.

## Keep one monitor open

The Monitor tool caps `timeout_ms`, at ten minutes in some versions of Claude Code and thirty in others, whatever you ask; its result says when the monitor expires. The expiry notice is the cue to open the monitor again, at once and in the same way; so is a notice that the socket closed. Nothing is lost meanwhile: a turn the user sends while no monitor is open waits for the next one, but the user waits with it. Open one monitor at a time. Each open monitor on the board gets each turn, so a second one brings you the same turn twice, once under each task id: before you open another, stop a monitor that still runs with `TaskStop`, or wait for its expiry notice. When a turn comes with the id of one you already have, it is that turn again, and needs nothing.

While your monitor is open, the page shows the user that an agent is connected. After you get a turn, the page shows that you work on it until you write an action.

## Read a turn

A turn is one event of lines. The first is its head, `{"turn": "9f2c…", "actions": 3}`: the id of the send or chat message that ended the turn, and its number of actions. Then one line per action, in order, as JSON with the action's fields, such as `{"kind": "comment", "card": "plan", "quote": "tag the release", "text": "after the smoke test"}`. Answer a comment with a `comment` on the same card and quote, which joins its thread. A `put` of the user on a card that was on the board, such as a checked box, comes as an `edit` with a unified diff of the card's markdown; a `put` of a new card is a card the user made. Each turn has only the changes, as an edit of a file has only a diff. Read the board once, then follow the turns, and read it again only when you are not sure what the board shows.

The Monitor shows 3000 characters of an event and 500 of a line. A turn with more lines than one event holds comes as several events, half a second apart, each with a head that counts them, `{"turn": "9f2c…", "actions": 24, "frame": 2, "of": 3}`; the actions keep their order across them, so wait for the last frame before you act. A line longer than 500 characters, such as a long message or a long diff, shows cut at its end: `read_board` has the message whole in the chat and the card whole.

After you show content for review, tell the user what to review and to click Send, then wait for their turn.
