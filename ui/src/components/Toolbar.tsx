import {
  Maximize2,
  MessageCircle,
  Minus,
  Plus,
  StickyNote,
} from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { reactionIcons, reactionTones } from "~/lib/reactions";
import { useTools } from "~/lib/whiteboard";
import { Reaction } from "~/schemas/actions";

const ToolButton = ({
  label,
  shortcut,
  onClick,
  children,
}: {
  label: string;
  shortcut: string;
  onClick: () => void;
  children: ReactNode;
}) => (
  <button
    type="button"
    aria-label={label}
    title={`${label} (${shortcut})`}
    className="flex h-9 min-w-9 items-center justify-center gap-1.5 rounded-xl px-2 text-sm text-stone-600 transition-colors hover:bg-stone-100 hover:text-stone-900"
    onClick={onClick}
  >
    {children}
  </button>
);

const Divider = () => <span className="mx-1 h-5 w-px bg-stone-200" />;

/** A chip for each kind of feedback on the board; a click shows the next part with it. */
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
        .filter(([, thread]) => thread.reaction === reaction)
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

export const Toolbar = ({
  scale,
  zoom,
  reset,
  fit,
  note,
  show,
}: {
  scale: number;
  zoom: (factor: number) => void;
  reset: () => void;
  fit: () => void;
  note: () => void;
  show: (ref: string) => void;
}) => (
  <nav
    aria-label="Tools"
    className="pointer-events-auto absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-2xl bg-white p-1 shadow-xl ring-1 ring-stone-900/10"
  >
    <Tally show={show} />
    <ToolButton label="New note" shortcut="N" onClick={note}>
      <StickyNote className="size-4" />
      Note
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
