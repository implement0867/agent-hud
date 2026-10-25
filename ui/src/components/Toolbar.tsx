import {
  ChevronUp,
  Eraser,
  History,
  Keyboard,
  Maximize2,
  MessageCircle,
  Minus,
  Plus,
  SendHorizontal,
  StickyNote,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { assertNever } from "~/lib/assertNever";
import { mod } from "~/lib/keys";
import { reactionIcons, reactionTones, reactionsOf } from "~/lib/reactions";
import { useTools } from "~/lib/whiteboard";
import { ActionKind, Reaction } from "~/schemas/actions";
import type { THeard } from "~/schemas/events";

const ToolButton = ({
  label,
  shortcut,
  pressed,
  onClick,
  children,
}: {
  label: string;
  shortcut: string;
  pressed?: boolean;
  onClick: () => void;
  children: ReactNode;
}) => (
  <button
    type="button"
    aria-label={label}
    aria-pressed={pressed}
    title={`${label} (${shortcut})`}
    className={`flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-xl px-2 text-sm transition-colors ${pressed === true ? "bg-sky-100 text-sky-800" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"}`}
    onClick={onClick}
  >
    {children}
  </button>
);

const Divider = () => <span className="mx-1 h-5 w-px bg-stone-200" />;

/** A chip for each kind of feedback on the board, by either author; a click shows the next part with it. */
const Tally = ({ show }: { show: (ref: string) => void }) => {
  const { board } = useTools();
  const [turn, setTurn] = useState(0);
  const threads = Object.entries(board.threads);
  const groups = [
    ...Reaction.options.map((reaction) => ({
      key: reaction,
      Icon: reactionIcons[reaction],
      tone: reactionTones[reaction],
      refs: threads
        .filter(([, thread]) =>
          reactionsOf(thread).some(([, reacted]) => reacted === reaction),
        )
        .map(([ref]) => ref),
    })),
    {
      key: "comments",
      Icon: MessageCircle,
      tone: "bg-sky-100 text-sky-700",
      refs: threads
        .filter(([, thread]) => thread.comments.length > 0)
        .map(([ref]) => ref),
    },
  ].filter(({ refs }) => refs.length > 0);
  if (groups.length === 0) return null;
  return (
    <>
      {groups.map(({ key, Icon, tone, refs }) => (
        <button
          key={key}
          type="button"
          title={`Show the next part with ${key}`}
          className={`flex h-7 items-center gap-1 rounded-full px-2 text-xs font-medium ${tone}`}
          onClick={() => {
            const ref = refs[turn % refs.length];
            if (ref !== undefined) show(ref);
            setTurn(turn + 1);
          }}
        >
          <Icon className="size-3.5" strokeWidth={2.5} />
          {refs.length}
        </button>
      ))}
      <Divider />
    </>
  );
};

/** One line for a pending action, as the agent will hear it. */
const describe = ({ body, parts }: THeard): string => {
  const text = (ref: string) => {
    const part = parts[ref];
    return part === undefined ? ref : `${ref} "${part}"`;
  };
  switch (body.kind) {
    case ActionKind.enum.put:
      return `new note ${body.id}`;
    case "edit":
      return `edit ${body.id}`;
    case ActionKind.enum.remove:
      return `remove ${body.id}`;
    case ActionKind.enum.restore:
      return `restore ${body.id}`;
    case ActionKind.enum.react:
      return `${body.reaction} ${text(body.ref)}`;
    case ActionKind.enum.unreact:
      return `no reaction on ${text(body.ref)}`;
    case ActionKind.enum.comment:
      return `comment on ${text(body.ref)}: ${body.text}`;
    case ActionKind.enum.say:
      return body.text;
    case ActionKind.enum.fill:
      return `${body.ref} = ${JSON.stringify(body.value)}`;
    case ActionKind.enum.link:
      return `arrow ${body.src} → ${body.dst}${body.text === "" ? "" : ` "${body.text}"`}`;
    case ActionKind.enum.unlink:
      return `remove arrow ${body.id}`;
    case ActionKind.enum.move:
      return `move ${body.id}`;
    case ActionKind.enum.resize:
      return `resize ${body.id}`;
    case ActionKind.enum.place:
      return `place ${body.id}`;
    case ActionKind.enum.clear:
      return "clear the board";
    case ActionKind.enum.send:
      return "send";
    default:
      return assertNever(body);
  }
};

/** Sends the user's actions since the last send to the agent, as one turn; the chevron lists them. */
const SendButton = ({
  pending,
  send,
}: {
  pending: THeard[];
  send: () => void;
}) => {
  const [open, setOpen] = useState(false);
  const unsent = pending.length;
  const box = useRef<HTMLDivElement>(null);
  /** Esc, and a press outside the list, close it. */
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    document.addEventListener(
      "keydown",
      (event) => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        setOpen(false);
      },
      { capture: true, signal: controller.signal },
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
      { capture: true, signal: controller.signal },
    );
    return () => {
      controller.abort();
    };
  }, [open]);
  return (
    <div ref={box} className="relative flex items-center">
      <button
        type="button"
        aria-label="Send to the agent"
        title={`Send your changes to the agent (${mod}↵)`}
        disabled={unsent === 0}
        className="flex h-9 items-center gap-1.5 rounded-l-xl bg-sky-600 px-3 text-sm font-medium text-white transition-colors hover:bg-sky-700 disabled:bg-transparent disabled:text-stone-400"
        onClick={send}
      >
        <SendHorizontal className="size-4" />
        Send
        {unsent > 0 && (
          <span
            aria-label={`${String(unsent)} unsent`}
            className="rounded-full bg-white/25 px-1.5 text-xs tabular-nums"
          >
            {unsent}
          </span>
        )}
      </button>
      <button
        type="button"
        aria-label="What goes to the agent"
        aria-expanded={open}
        title="What goes to the agent on Send"
        disabled={unsent === 0}
        className="flex h-9 items-center rounded-r-xl bg-sky-600 px-1 text-white transition-colors hover:bg-sky-700 disabled:bg-transparent disabled:text-stone-400"
        onClick={() => {
          setOpen(!open);
        }}
      >
        <ChevronUp
          className={`size-4 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && unsent > 0 ? (
        <ul
          aria-label="Pending actions"
          className="absolute bottom-11 left-0 max-h-64 w-80 overflow-y-auto rounded-xl bg-white p-2 text-xs text-stone-700 shadow-xl ring-1 ring-stone-900/10"
        >
          {pending.map((heard) => (
            <li
              key={heard.id}
              className="truncate px-2 py-1"
              title={describe(heard)}
            >
              {describe(heard)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
};

export const Toolbar = ({
  scale,
  zoom,
  reset,
  fit,
  note,
  clear,
  pending,
  send,
  history,
  toggleHistory,
  shortcuts,
  toggleShortcuts,
  onHeight,
}: {
  scale: number;
  zoom: (factor: number) => void;
  reset: () => void;
  fit: () => void;
  note: () => void;
  clear: () => void;
  pending: THeard[];
  send: () => void;
  history: boolean;
  toggleHistory: () => void;
  shortcuts: boolean;
  toggleShortcuts: () => void;
  /** Gets the toolbar's height when it changes, so that the chat sits above it on a narrow screen. */
  onHeight: (height: number) => void;
}) => {
  const { board, show } = useTools();
  const nav = useRef<HTMLElement>(null);
  useEffect(() => {
    const element = nav.current;
    if (element === null) return;
    const observer = new ResizeObserver(() => {
      onHeight(element.offsetHeight);
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, [onHeight]);
  return (
    <nav
      ref={nav}
      aria-label="Tools"
      className="pointer-events-auto absolute bottom-4 left-1/2 flex max-w-[calc(100%-2rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-0.5 rounded-2xl bg-white p-1 shadow-xl ring-1 ring-stone-900/10"
    >
      <SendButton pending={pending} send={send} />
      <Divider />
      <Tally show={show} />
      <ToolButton label="New note" shortcut="N" onClick={note}>
        <StickyNote className="size-4" />
        Note
      </ToolButton>
      <ToolButton
        label="History"
        shortcut="H"
        pressed={history}
        onClick={toggleHistory}
      >
        <History className="size-4" />
      </ToolButton>
      <ToolButton
        label="Shortcuts"
        shortcut="?"
        pressed={shortcuts}
        onClick={toggleShortcuts}
      >
        <Keyboard className="size-4" />
      </ToolButton>
      <button
        type="button"
        aria-label="Clear the board"
        title="Clear the board: the cards go to the history"
        disabled={Object.keys(board.cards).length === 0}
        className="flex h-9 min-w-9 items-center justify-center rounded-xl px-2 text-stone-600 transition-colors hover:bg-rose-50 hover:text-rose-700 disabled:text-stone-300 disabled:hover:bg-transparent"
        onClick={() => {
          if (window.confirm("Clear the board? The cards go to the history."))
            clear();
        }}
      >
        <Eraser className="size-4" />
      </button>
      <Divider />
      <ToolButton
        label="Zoom out"
        shortcut="-"
        onClick={() => {
          zoom(1 / 1.25);
        }}
      >
        <Minus className="size-4" />
      </ToolButton>
      <ToolButton label="Reset zoom" shortcut="0" onClick={reset}>
        <span className="w-10 text-xs tabular-nums">
          {Math.round(scale * 100)}%
        </span>
      </ToolButton>
      <ToolButton
        label="Zoom in"
        shortcut="+"
        onClick={() => {
          zoom(1.25);
        }}
      >
        <Plus className="size-4" />
      </ToolButton>
      <ToolButton label="Fit all cards" shortcut="1" onClick={fit}>
        <Maximize2 className="size-4" />
      </ToolButton>
    </nav>
  );
};
