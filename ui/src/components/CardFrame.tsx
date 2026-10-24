import { Bot, Pencil, Trash2, User } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import type { PointerEvent, ReactNode } from "react";

import { CardBody } from "~/components/CardBody";
import { Connector, Marks } from "~/components/Marks";
import { SelectionKind, isSelected, useTools } from "~/lib/whiteboard";
import { ActionKind, Author } from "~/schemas/actions";
import type { TCard, TPoint } from "~/schemas/board";

const SmallButton = ({
  onClick,
  children,
}: {
  onClick: () => void;
  children: ReactNode;
}) => (
  <button
    type="button"
    className="font-semibold text-sky-700 hover:underline"
    onClick={onClick}
  >
    {children}
  </button>
);

/**
 * Cmd or Ctrl with Enter saves. Esc and a click outside close the editor while the text is as it was; with changes,
 * a click outside keeps the editor open and asks to save or discard, and Esc asks for a second Esc.
 * When the card got a new version since the editor opened, the editor says so and offers to save over it.
 */
export const Editor = ({
  md,
  label,
  warning,
  changed = false,
  save,
  cancel,
}: {
  md: string;
  label: string;
  warning: string | null;
  /** Whether the card got a new version since the editor opened. */
  changed?: boolean;
  /** Saves the text; over is true to replace a newer version of the card. */
  save: (md: string, over: boolean) => void;
  cancel: () => void;
}) => {
  const [text, setText] = useState(md);
  const [asking, setAsking] = useState<"save" | "discard" | null>(null);
  const dirty = text.trim() !== "" && text !== md;
  const done = () => {
    if (!dirty) cancel();
    else if (!changed) save(text, false);
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
        onBlur={() => {
          if (dirty) setAsking("save");
          else cancel();
        }}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === "Escape") {
            if (!dirty || asking === "discard") cancel();
            else setAsking("discard");
          }
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) done();
        }}
      />
      {changed ? (
        <div
          role="alert"
          className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-900"
        >
          The agent put a new version of this card while you edited; a save
          would replace it.
          <span className="mt-1 flex gap-3">
            <SmallButton
              onClick={() => {
                save(text, true);
              }}
            >
              Save over it
            </SmallButton>
            <SmallButton onClick={cancel}>Discard mine</SmallButton>
          </span>
        </div>
      ) : asking === "save" ? (
        <p className="mt-1 flex gap-3 text-[11px] text-stone-500">
          Unsaved changes
          <SmallButton
            onClick={() => {
              save(text, false);
            }}
          >
            Save
          </SmallButton>
          <SmallButton onClick={cancel}>Discard</SmallButton>
        </p>
      ) : warning !== null || asking === "discard" ? (
        <p className="mt-1 text-[11px] text-stone-400">
          {asking === "discard" ? "esc again discards your changes" : warning}
        </p>
      ) : null}
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

/** The width of a card that no one resized: wider with code. */
const defaultWidth = (md: string) => (/^ {0,3}(```|~~~)/m.test(md) ? 640 : 384);

const clampWidth = (width: number) => Math.min(1280, Math.max(256, width));

/**
 * A card at its place on the board, which looks the same for each author but for the icon. A drag on the card's header
 * moves it, a drag on its bottom right corner sets its width, a click selects it, and a double click on its text edits the
 * markdown. Cards may cross after their first place; a touch puts the card on top of the others.
 */
export const CardFrame = ({
  id,
  card,
  at,
  scale,
  placed,
  z,
  raise,
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
  /** The card's layer: a higher one shows over the cards it crosses. */
  z: number;
  /** Puts the card on top, on a touch. */
  raise: () => void;
  editing: boolean;
  edit: (editing: boolean) => void;
  move: (to: TPoint) => void;
  drop: (to: TPoint) => void;
  /** Gets the card's element by id when it mounts, and null when it goes. */
  measure: (id: string, element: HTMLElement | null) => void;
}) => {
  const { board, act, selection, select, openHistory, remove } = useTools();
  const measured = useCallback(
    (element: HTMLElement | null) => {
      measure(id, element);
    },
    [id, measure],
  );
  const versions = board.history[id]?.length ?? 0;
  /** The number of earlier versions when the editor opened, so that a save does not replace a newer version. */
  const [opened, setOpened] = useState<number | null>(null);
  if (editing && opened === null) setOpened(versions);
  if (!editing && opened !== null) setOpened(null);
  const changed = editing && opened !== null && opened !== versions;
  const selected = isSelected(selection, id);
  const mine = card.author === Author.enum.user;
  const AuthorIcon = mine ? User : Bot;
  const stored = board.widths[id];
  const [stretch, setStretch] = useState<number | null>(null);
  const [storedSeen, setStoredSeen] = useState(stored);
  if (storedSeen !== stored) {
    setStoredSeen(stored);
    setStretch(null);
  }
  const width = stretch ?? stored ?? defaultWidth(card.md);
  const resize = usePointerDrag({
    scale,
    at: { x: width, y: 0 },
    move: (to) => {
      setStretch(clampWidth(to.x));
    },
    drop: (to) => {
      const next = clampWidth(to.x);
      setStretch(next);
      void act({ kind: ActionKind.enum.resize, id, width: next }).then(
        (taken) => {
          if (!taken) setStretch(null);
        },
      );
    },
    click: () => undefined,
  });
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
  const save = async (md: string, over: boolean) => {
    const version = over ? {} : { version: opened ?? versions };
    if (await act({ kind: ActionKind.enum.put, id, md, ...version }))
      edit(false);
  };
  return (
    <article
      ref={measured}
      data-ref={id}
      style={{
        left: at.x,
        top: at.y,
        width,
        zIndex: z,
        visibility: placed ? "visible" : "hidden",
      }}
      className={`group/card pointer-events-auto absolute flex animate-rise flex-col rounded-xl bg-white shadow-[0_1px_2px_rgba(0,0,0,0.06),0_10px_30px_-12px_rgba(0,0,0,0.18)] transition-shadow ${selected ? "ring-2 ring-sky-400" : "ring-1 ring-stone-900/5"}`}
      onPointerDownCapture={raise}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <header
        className="group/part relative flex cursor-grab items-center gap-2 px-4 pt-2.5 pb-1 active:cursor-grabbing"
        {...drag}
      >
        <span
          role="img"
          aria-label={mine ? "By you" : "By the agent"}
          title={mine ? "you" : "agent"}
          className={`grid size-5 shrink-0 place-items-center rounded-full text-white ${mine ? "bg-sky-600" : "bg-stone-800"}`}
        >
          <AuthorIcon className="size-3" />
        </span>
        <span className="truncate font-mono text-[11px] tracking-wide text-stone-400">
          {id}
        </span>
        {card.edited ? (
          <span className="rounded-full bg-sky-50 px-1.5 py-px font-mono text-[10px] text-sky-700">
            {mine ? "edited by the agent" : "edited by you"}
          </span>
        ) : null}
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
              remove(id);
            }}
          >
            <Trash2 className="size-3.5" />
          </IconButton>
        </span>
        <span className="relative h-5 w-18 shrink-0">
          <Marks target={id} place="top-1/2 right-0 -translate-y-1/2" />
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
            changed={changed}
            save={(md, over) => {
              void save(md, over);
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
      <span
        role="separator"
        aria-orientation="vertical"
        aria-label={`Width of ${id}`}
        aria-valuenow={Math.round(width)}
        className="absolute right-0 bottom-0 size-4 cursor-ew-resize rounded-br-xl text-stone-300 hover:text-stone-500"
        {...resize}
      >
        <svg viewBox="0 0 16 16" className="size-full" aria-hidden>
          <path
            d="M13 7 7 13M13 10.5 10.5 13"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </span>
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
