import { Bot, GripHorizontal, Pencil, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import type { PointerEvent, ReactNode } from "react";

import { CardBody } from "~/components/CardBody";
import { Connector, Marks } from "~/components/Marks";
import { SelectionKind, isSelected, useTools } from "~/lib/whiteboard";
import { ActionKind, Author } from "~/schemas/actions";
import type { TCard, TPoint } from "~/schemas/board";

/** Cmd or Ctrl with Enter, or a click outside, saves; Esc cancels. Saving the same text cancels. */
export const Editor = ({
  md,
  label,
  warning,
  save,
  cancel,
}: {
  md: string;
  label: string;
  warning: string | null;
  save: (md: string) => void;
  cancel: () => void;
}) => {
  const [text, setText] = useState(md);
  const done = () => {
    if (text.trim() === "" || text === md) cancel();
    else save(text);
  };
  return (
    <div
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
    >
      <textarea
        aria-label={label}
        ref={(element) => {
          element?.focus();
        }}
        className="field-sizing-content min-h-24 w-full resize-none bg-transparent font-mono text-[13px] leading-relaxed text-stone-800 outline-none"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
        onBlur={done}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === "Escape") cancel();
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) done();
        }}
      />
      <p className="mt-1 text-[11px] text-stone-400">
        {warning === null ? "" : `${warning} · `}⌘↵ save · esc cancel
      </p>
    </div>
  );
};

const usePointerDrag = ({
  scale,
  at,
  move,
  drop,
  click,
}: {
  scale: number;
  at: TPoint;
  move: (to: TPoint) => void;
  drop: (to: TPoint) => void;
  click: () => void;
}) => {
  const start = useRef<{ x: number; y: number; at: TPoint } | null>(null);
  const moved = useRef(false);
  const target = (
    event: PointerEvent,
    from: { x: number; y: number; at: TPoint },
  ) => ({
    x: from.at.x + (event.clientX - from.x) / scale,
    y: from.at.y + (event.clientY - from.y) / scale,
  });
  return {
    onPointerDown: (event: PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      event.currentTarget.setPointerCapture(event.pointerId);
      start.current = { x: event.clientX, y: event.clientY, at };
      moved.current = false;
    },
    onPointerMove: (event: PointerEvent<HTMLElement>) => {
      const from = start.current;
      if (from === null) return;
      moved.current ||=
        Math.hypot(event.clientX - from.x, event.clientY - from.y) > 3;
      if (moved.current) move(target(event, from));
    },
    onPointerUp: (event: PointerEvent<HTMLElement>) => {
      const from = start.current;
      start.current = null;
      if (from === null) return;
      if (moved.current) drop(target(event, from));
      else click();
    },
  };
};

/**
 * A card at its place on the board. A drag on the card's edge or header moves it, a click selects it,
 * and a double click on its text edits the markdown.
 */
export const CardFrame = ({
  id,
  card,
  at,
  scale,
  placed,
  editing,
  edit,
  move,
  drop,
  measure,
}: {
  id: string;
  card: TCard;
  at: TPoint;
  scale: number;
  placed: boolean;
  editing: boolean;
  edit: (editing: boolean) => void;
  move: (to: TPoint) => void;
  drop: (to: TPoint) => void;
  measure: (element: HTMLElement | null) => void;
}) => {
  const { board, act, selection, select, openHistory } = useTools();
  const versions = board.history[id]?.length ?? 0;
  const selected = isSelected(selection, id);
  const note = card.author === Author.enum.user;
  const width = /^ {0,3}(```|~~~)/m.test(card.md)
    ? "w-[40rem]"
    : note
      ? "w-64"
      : "w-96";
  const drag = usePointerDrag({
    scale,
    at,
    move,
    drop,
    click: () => {
      select({ kind: SelectionKind.enum.ref, ref: id });
    },
  });
  const feedback = Object.keys(board.threads).filter(
    (ref) => ref === id || ref.startsWith(`${id}/`),
  ).length;
  const save = async (md: string) => {
    if (await act({ kind: ActionKind.enum.put, id, md })) edit(false);
  };
  return (
    <article
      ref={measure}
      data-ref={id}
      style={{
        left: at.x,
        top: at.y,
        visibility: placed ? "visible" : "hidden",
      }}
      className={`group/card pointer-events-auto absolute flex animate-rise flex-col rounded-xl transition-shadow ${width} ${note ? "-rotate-[0.6deg] bg-amber-100 shadow-[0_8px_20px_-8px_rgba(120,80,0,0.35)]" : "bg-white shadow-[0_1px_2px_rgba(0,0,0,0.06),0_10px_30px_-12px_rgba(0,0,0,0.18)]"} ${selected ? "ring-2 ring-sky-400" : "ring-1 ring-stone-900/5"}`}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <header
        className="group/part relative flex cursor-grab items-center gap-2 px-4 pt-2.5 pb-1 active:cursor-grabbing"
        {...drag}
      >
        {note ? (
          <GripHorizontal className="size-4 text-amber-700/40" />
        ) : (
          <span className="grid size-5 place-items-center rounded-full bg-stone-800 text-white">
            <Bot className="size-3" />
          </span>
        )}
        <span
          className={`truncate font-mono text-[11px] tracking-wide ${note ? "text-amber-800/60 opacity-0 transition-opacity group-hover/card:opacity-100" : "text-stone-400"}`}
        >
          {id}
        </span>
        {versions > 0 && (
          <button
            type="button"
            aria-label={`History of ${id}`}
            title={`Version ${String(versions + 1)}: show the earlier versions and their feedback`}
            className="rounded-full bg-stone-100 px-1.5 py-px font-mono text-[10px] text-stone-500 hover:bg-sky-100 hover:text-sky-700"
            onPointerDown={(event) => {
              event.stopPropagation();
            }}
            onClick={(event) => {
              event.stopPropagation();
              openHistory(id);
            }}
          >
            v{versions + 1}
          </button>
        )}
        <span className="ml-auto flex items-center gap-0.5 opacity-0 transition-opacity group-hover/card:opacity-100">
          <IconButton
            label={`Edit ${id}`}
            onClick={() => {
              edit(true);
            }}
          >
            <Pencil className="size-3.5" />
          </IconButton>
          <IconButton
            label={`Remove ${id}`}
            onClick={() => {
              void act({ kind: ActionKind.enum.remove, id });
            }}
          >
            <Trash2 className="size-3.5" />
          </IconButton>
        </span>
        <span className="relative w-14">
          <Marks target={id} />
        </span>
        <Connector target={id} />
      </header>
      <div
        className="px-4 pb-4"
        onDoubleClick={(event) => {
          event.stopPropagation();
          edit(true);
        }}
      >
        {editing ? (
          <Editor
            md={card.md}
            label={`Markdown of ${id}`}
            warning={
              feedback === 0
                ? null
                : "saving moves the feedback on the parts you change to the history"
            }
            save={(md) => {
              void save(md);
            }}
            cancel={() => {
              edit(false);
            }}
          />
        ) : (
          <div key={versions} className="animate-pop">
            <CardBody id={id} md={card.md} />
          </div>
        )}
      </div>
    </article>
  );
};

export const IconButton = ({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) => (
  <button
    type="button"
    aria-label={label}
    title={label}
    className="grid size-6 place-items-center rounded-md text-stone-400 hover:bg-stone-900/5 hover:text-stone-700"
    onPointerDown={(event) => {
      event.stopPropagation();
    }}
    onClick={(event) => {
      event.stopPropagation();
      onClick();
    }}
  >
    {children}
  </button>
);
