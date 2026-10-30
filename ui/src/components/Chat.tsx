import {
  ChevronUp,
  MessageCircle,
  MessagesSquare,
  PanelRightClose,
  SendHorizontal,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";

import { Bubble } from "~/components/Bubble";
import { IconButton } from "~/components/IconButton";
import { useBoard, useStore } from "~/data/context";
import { ActionKind, Author, messageSchema } from "~/domain/actions";
import { groupPending } from "~/domain/pending";
import { useWhiteboard } from "~/hooks/useWhiteboard";
import { mod } from "~/lib/keys";

const widthKey = "agent-hud:chat-width";

/** The chat's place: above the toolbar on a screen narrower than 1280 px, at the bottom right on a wider one. */
const place =
  "pointer-events-auto absolute right-4 bottom-[calc(var(--toolbar)+2rem)] xl:bottom-4";

/** The count of the threads on the board; a click opens the next thread. */
const Tally = () => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  const [turn, setTurn] = useState(0);
  const threads = Object.entries(model.board.threads);
  if (threads.length === 0) return null;
  return (
    <button
      type="button"
      aria-label="Threads on the board"
      title={`On the board: ${String(threads.length)} threads. Show the next`}
      className="flex h-6 items-center gap-1 rounded-full bg-accent-soft px-1.5 text-xs font-medium text-accent-strong"
      onClick={() => {
        const found = threads[turn % threads.length];
        if (found !== undefined) show(found[1].card, found[0]);
        setTurn(turn + 1);
      }}
    >
      <MessageCircle className="size-3" strokeWidth={2.5} />
      {threads.length}
    </button>
  );
};

type TPendingListProps = { close: () => void };

/** What the next turn carries, one line per action as the user reads it, grouped by card; a click shows the part. */
const PendingList = ({ close }: TPendingListProps) => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  const list = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState(false);
  /** Whether the list goes on below its visible end, for the fade that says so. */
  const measure = () => {
    const element = list.current;
    if (element === null) return;
    setMore(
      element.scrollHeight - element.scrollTop - element.clientHeight > 1,
    );
  };
  useEffect(measure, [model.pending]);
  const count = model.pending.length;
  return (
    <div className="panel absolute right-0 bottom-full left-0 mb-2 overflow-hidden text-xs text-ink-soft">
      <p className="border-b border-divider px-3 py-2 font-medium text-ink-muted">
        Send carries {count} {count === 1 ? "change" : "changes"}
      </p>
      <div
        ref={list}
        aria-label="Pending actions"
        className="max-h-72 overflow-y-auto p-2"
        onScroll={measure}
      >
        {groupPending(model.pending, model.board).map((group) => (
          <section key={group.key} aria-label={group.title} className="mb-2">
            <h3 className="truncate px-2 py-1 text-[11px] font-semibold tracking-wide text-ink-muted uppercase">
              {group.title}
            </h3>
            <ul>
              {group.lines.map(({ id, card, thread, what, where }) => (
                <li key={id}>
                  <button
                    type="button"
                    disabled={card === null}
                    className="flex w-full items-baseline gap-2 rounded-lg px-2 py-1 text-left enabled:hover:bg-surface-sunken"
                    onClick={() => {
                      if (card === null) return;
                      close();
                      show(card, thread);
                    }}
                  >
                    {where !== "" && (
                      <span className="max-w-[45%] shrink-0 truncate text-ink-muted">
                        {where}
                      </span>
                    )}
                    <span className="min-w-0 flex-1 truncate font-medium text-ink">
                      {what}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      {more ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-surface to-transparent"
        />
      ) : null}
    </div>
  );
};

const sendTone =
  "flex h-8 items-center bg-accent text-on-accent transition-colors hover:bg-accent-strong disabled:bg-ink-ghost";

type TSendBoxProps = { send: () => void };

/**
 * The one Send: the message box, and beside it the button that sends the message with the user's unsent actions,
 * or the actions alone when the box is empty, with their count; the chevron lists them, and Esc or a press outside
 * closes the list. Enter and ⌘↵ send too, and Shift+Enter starts a new line. The text stays until the server takes it.
 */
const SendBox = ({ send }: TSendBoxProps) => {
  const { model } = useBoard();
  const store = useStore();
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [open, setOpen] = useState(false);
  const unsent = model.pending.length;
  const hasText = messageSchema.safeParse(text).success;
  const ready = !sending && (hasText || unsent > 0);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const listening = new AbortController();
    const { signal } = listening;
    document.addEventListener(
      "keydown",
      (event) => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        setOpen(false);
      },
      { capture: true, signal },
    );
    document.addEventListener(
      "pointerdown",
      (event) => {
        if (
          !(event.target instanceof Node) ||
          !box.current?.contains(event.target)
        )
          setOpen(false);
      },
      { capture: true, signal },
    );
    return () => {
      listening.abort();
    };
  }, [open]);
  const submit = async () => {
    if (!ready) return;
    setOpen(false);
    if (!hasText) {
      send();
      return;
    }
    setSending(true);
    if (await store.act({ kind: ActionKind.enum.post, text })) setText("");
    setSending(false);
  };
  return (
    <div ref={box} className="relative p-3 pt-0">
      {open && unsent > 0 ? (
        <PendingList
          close={() => {
            setOpen(false);
          }}
        />
      ) : null}
      <div className="flex items-end gap-1 rounded-2xl bg-surface-sunken p-1 focus-within:ring-2 focus-within:ring-accent-ring">
        <textarea
          rows={1}
          aria-label="Message the agent"
          placeholder="Message the agent"
          id="message-box"
          className="field-sizing-content max-h-40 min-h-8 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
          value={text}
          readOnly={sending}
          onChange={(event) => {
            setText(event.target.value);
          }}
          onKeyDown={(event) => {
            event.stopPropagation();
            if (
              event.key === "Enter" &&
              (!event.shiftKey || event.metaKey || event.ctrlKey)
            ) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        <span className="flex items-stretch">
          <button
            type="button"
            aria-label="Send to the agent"
            title={`Send your message and your changes to the agent (${mod}↵)`}
            disabled={!ready}
            className={`${sendTone} gap-1.5 pl-3 text-sm font-medium ${unsent > 0 ? "rounded-l-full pr-2" : "rounded-full pr-3"}`}
            onClick={() => {
              void submit();
            }}
          >
            <SendHorizontal className="size-4" />
            Send
            {unsent > 0 && (
              <span
                aria-label={`${String(unsent)} unsent`}
                className="rounded-full bg-on-accent/25 px-1.5 text-xs tabular-nums"
              >
                {unsent}
              </span>
            )}
          </button>
          {unsent > 0 && (
            <button
              type="button"
              aria-label="What goes to the agent"
              aria-expanded={open}
              title="What Send carries"
              className={`${sendTone} rounded-r-full border-l border-on-accent/30 px-1`}
              onClick={() => {
                setOpen(!open);
              }}
            >
              <ChevronUp
                className={`size-4 transition-transform ${open ? "rotate-180" : ""}`}
              />
            </button>
          )}
        </span>
      </div>
    </div>
  );
};

type TChatProps = {
  send: () => void;
  /** The height of the toolbar, which the chat sits above on a narrow screen. */
  above: number;
  /** Takes the open chat's element, for the board to keep clear of it; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
};

/**
 * The messages between the user and the agent, and the comments on parts, newest at the bottom, with the one Send
 * under them. A closed chat counts the agent's new messages and comments, and the changes not yet sent.
 * A drag on the chat's left edge sets its width, which the browser keeps.
 */
export const Chat = ({ send, above, measure }: TChatProps) => {
  const { model } = useBoard();
  /** The width the user last dragged the chat to, in this browser, as a CSS length; none before a drag. */
  const [width, setWidth] = useState(
    () => localStorage.getItem(widthKey) ?? undefined,
  );
  const [open, setOpen] = useState(true);
  const fromAgent = model.board.messages.filter(
    (said) => said.author === Author.enum.agent,
  ).length;
  const [seen, setSeen] = useState(fromAgent);
  const unread = open ? 0 : fromAgent - seen;
  const unsent = model.pending.length;
  const style = { "--toolbar": `${String(above)}px`, width };
  /** A drag on the left edge sets the width; the stylesheet keeps it between the least and the most. */
  const resize = (event: PointerEvent<HTMLElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const from = {
      x: event.clientX,
      width: event.currentTarget.parentElement?.offsetWidth ?? 0,
    };
    const dragged = (to: number) => `${String(from.width + from.x - to)}px`;
    const listening = new AbortController();
    const { signal } = listening;
    window.addEventListener(
      "pointermove",
      (move) => {
        setWidth(dragged(move.clientX));
      },
      { signal },
    );
    window.addEventListener(
      "pointerup",
      (up) => {
        listening.abort();
        setWidth(dragged(up.clientX));
        localStorage.setItem(widthKey, dragged(up.clientX));
      },
      { signal },
    );
  };
  const collapse = () => {
    setSeen(fromAgent);
    setOpen(false);
  };
  if (!open)
    return (
      <button
        type="button"
        aria-label="Open the chat"
        style={style}
        className={`${place} flex h-11 w-fit items-center gap-2 rounded-full bg-surface px-3 text-ink-soft shadow-pop ring-1 ring-edge hover:text-ink`}
        onClick={() => {
          setOpen(true);
        }}
      >
        <MessagesSquare className="size-5" />
        {unsent > 0 && (
          <span
            aria-label={`${String(unsent)} unsent`}
            className="rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-on-accent"
          >
            {unsent} to send
          </span>
        )}
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 grid size-5 place-items-center rounded-full bg-accent text-[11px] font-semibold text-on-accent">
            {unread}
          </span>
        )}
      </button>
    );
  return (
    <aside
      ref={measure}
      aria-label="Chat with the agent"
      style={style}
      className={`${place} panel flex max-h-[70%] w-80 max-w-[min(40rem,100%-2rem)] min-w-72 animate-pop flex-col select-text`}
    >
      <div
        role="separator"
        aria-label="Resize the chat"
        aria-orientation="vertical"
        className="absolute inset-y-3 -left-1.5 w-3 cursor-col-resize rounded-full hover:bg-accent-soft"
        onPointerDown={resize}
      />
      <header className="flex items-center gap-2 border-b border-divider px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">
          <button
            type="button"
            aria-label="Collapse the chat"
            title="Collapse the chat to a button"
            className="rounded px-1 hover:bg-surface-sunken"
            onClick={collapse}
          >
            Chat
          </button>
        </h2>
        <Tally />
        <span className="ml-auto">
          <IconButton variant="close" label="Close the chat" onClick={collapse}>
            <PanelRightClose className="size-4" />
          </IconButton>
        </span>
      </header>
      <ul className="flex min-h-24 flex-col-reverse gap-2 overflow-y-auto px-3 py-3">
        {model.board.messages.toReversed().map((said) => (
          <Bubble key={said.id} said={said} />
        ))}
      </ul>
      <SendBox send={send} />
    </aside>
  );
};
