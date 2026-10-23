import {
  History,
  Maximize2,
  MessageCircle,
  Minus,
  Plus,
  SendHorizontal,
  StickyNote,
} from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { reactionIcons, reactionTones, reactionsOf } from "~/lib/reactions";
import { useTools } from "~/lib/whiteboard";
import { Reaction } from "~/schemas/actions";

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

/** Sends the user's actions since the last send to the agent, as one turn. */
const SendButton = ({ unsent, send }: { unsent: number; send: () => void }) => (
  <button
    type="button"
    aria-label="Send to the agent"
    title="Send your changes to the agent (⌘↵)"
    disabled={unsent === 0}
    className="flex h-9 items-center gap-1.5 rounded-xl bg-sky-600 px-3 text-sm font-medium text-white transition-colors hover:bg-sky-700 disabled:bg-transparent disabled:text-stone-400"
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
);

export const Toolbar = ({
  scale,
  zoom,
  reset,
  fit,
  note,
  unsent,
  send,
  history,
  toggleHistory,
}: {
  scale: number;
  zoom: (factor: number) => void;
  reset: () => void;
  fit: () => void;
  note: () => void;
  unsent: number;
  send: () => void;
  history: boolean;
  toggleHistory: () => void;
}) => {
  const { show } = useTools();
  return (
    <nav
      aria-label="Tools"
      className="pointer-events-auto absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-2xl bg-white p-1 shadow-xl ring-1 ring-stone-900/10"
    >
      <SendButton unsent={unsent} send={send} />
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
