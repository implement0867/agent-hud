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
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { IconButton } from "~/components/IconButton";
import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";
import { describeHeard } from "~/domain/events";
import { TallyKind, tally } from "~/domain/reactions";
import type { TTallyKind } from "~/domain/reactions";
import { useWhiteboard } from "~/hooks/useWhiteboard";
import { mod } from "~/lib/keys";
import { reactionIcons, reactionTones } from "~/theme";

const tallyLooks: Record<TTallyKind, { Icon: LucideIcon; tone: string }> = {
  approve: { Icon: reactionIcons.approve, tone: reactionTones.approve },
  reject: { Icon: reactionIcons.reject, tone: reactionTones.reject },
  question: { Icon: reactionIcons.question, tone: reactionTones.question },
  comments: { Icon: MessageCircle, tone: "bg-accent-soft text-accent-strong" },
};

const Divider = () => <span className="mx-1 h-5 w-px bg-outline" />;

/** A chip for each kind of feedback on the board, by either author; a click shows the next part with it. */
const Tally = () => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  const [turn, setTurn] = useState(0);
  const refs = tally(model.board.threads);
  const kinds = TallyKind.options.filter((kind) => refs[kind].length > 0);
  if (kinds.length === 0) return null;
  return (
    <>
      {kinds.map((kind) => {
        const { Icon, tone } = tallyLooks[kind];
        const found = refs[kind];
        return (
          <button
            key={kind}
            type="button"
            title={`Show the next part with ${kind}`}
            className={`flex h-7 items-center gap-1 rounded-full px-2 text-xs font-medium ${tone}`}
            onClick={() => {
              const ref = found[turn % found.length];
              if (ref !== undefined) show(ref);
              setTurn(turn + 1);
            }}
          >
            <Icon className="size-3.5" strokeWidth={2.5} />
            {found.length}
          </button>
        );
      })}
      <Divider />
    </>
  );
};

const sendTone =
  "flex h-9 items-center bg-accent text-white transition-colors hover:bg-accent-strong disabled:bg-transparent disabled:text-ink-faint";

type TSendButtonProps = { send: () => void };

/** Sends the user's actions since the last send to the agent, as one turn; the chevron lists them, and Esc or a press outside closes the list. */
const SendButton = ({ send }: TSendButtonProps) => {
  const { model } = useBoard();
  const [open, setOpen] = useState(false);
  const unsent = model.pending.length;
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
  return (
    <div ref={box} className="relative flex items-center">
      <button
        type="button"
        aria-label="Send to the agent"
        title={`Send your changes to the agent (${mod}↵)`}
        disabled={unsent === 0}
        className={`${sendTone} gap-1.5 rounded-l-xl px-3 text-sm font-medium`}
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
        className={`${sendTone} rounded-r-xl px-1`}
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
          className="panel absolute bottom-11 left-0 max-h-64 w-80 overflow-y-auto p-2 text-xs text-ink-soft"
        >
          {model.pending.map((heard) => {
            const line = describeHeard(heard);
            return (
              <li key={heard.id} className="truncate px-2 py-1" title={line}>
                {line}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
};

type TToolbarProps = {
  scale: number;
  /** Zooms in by the steps, or out by negative steps. */
  zoom: (steps: number) => void;
  reset: () => void;
  fit: () => void;
  note: () => void;
  send: () => void;
  history: boolean;
  toggleHistory: () => void;
  shortcuts: boolean;
  toggleShortcuts: () => void;
  /** Takes the toolbar's element, so that the chat sits above it on a narrow screen; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
};

/** The board's tools at the bottom: send, the feedback tally, notes, history, shortcuts, clear and the view. */
export const Toolbar = ({
  scale,
  zoom,
  reset,
  fit,
  note,
  send,
  history,
  toggleHistory,
  shortcuts,
  toggleShortcuts,
  measure,
}: TToolbarProps) => {
  const { model } = useBoard();
  const store = useStore();
  return (
    <nav
      ref={measure}
      aria-label="Tools"
      className="panel pointer-events-auto absolute bottom-4 left-1/2 flex max-w-[calc(100%-2rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-0.5 p-1"
    >
      <SendButton send={send} />
      <Divider />
      <Tally />
      <IconButton
        variant="tool"
        label="New note"
        title="New note (N)"
        onClick={note}
      >
        <StickyNote className="size-4" />
        Note
      </IconButton>
      <IconButton
        variant="tool"
        label="History"
        title="History (H)"
        pressed={history}
        onClick={toggleHistory}
      >
        <History className="size-4" />
      </IconButton>
      <IconButton
        variant="tool"
        label="Shortcuts"
        title="Shortcuts (?)"
        pressed={shortcuts}
        onClick={toggleShortcuts}
      >
        <Keyboard className="size-4" />
      </IconButton>
      <IconButton
        variant="danger"
        label="Clear the board"
        title="Clear the board: the cards go to the history"
        disabled={model.cards.length === 0}
        onClick={() => {
          if (window.confirm("Clear the board? The cards go to the history."))
            void store.act({ kind: ActionKind.enum.clear });
        }}
      >
        <Eraser className="size-4" />
      </IconButton>
      <Divider />
      <IconButton
        variant="tool"
        label="Zoom out"
        title="Zoom out (-)"
        onClick={() => {
          zoom(-1);
        }}
      >
        <Minus className="size-4" />
      </IconButton>
      <IconButton
        variant="tool"
        label="Reset zoom"
        title="Reset zoom (0)"
        onClick={reset}
      >
        <span className="w-10 text-xs tabular-nums">
          {Math.round(scale * 100)}%
        </span>
      </IconButton>
      <IconButton
        variant="tool"
        label="Zoom in"
        title="Zoom in (+)"
        onClick={() => {
          zoom(1);
        }}
      >
        <Plus className="size-4" />
      </IconButton>
      <IconButton
        variant="tool"
        label="Fit all cards"
        title="Fit all cards (1)"
        onClick={fit}
      >
        <Maximize2 className="size-4" />
      </IconButton>
    </nav>
  );
};
