import { Bot, Pencil, Trash2, User } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import type { PointerEvent } from "react";

import { CardBody } from "~/components/CardBody";
import { IconButton } from "~/components/IconButton";
import { Connector, Marks } from "~/components/Marks";
import { MarkdownEditor } from "~/components/MarkdownEditor";
import type { TCardView } from "~/data/boardModel";
import { useBoard, useStore } from "~/data/context";
import { ActionKind, Author } from "~/domain/actions";
import type { TPoint } from "~/domain/board";
import {
  SelectionKind,
  isSelected,
  useWhiteboard,
} from "~/hooks/useWhiteboard";
import { clampCardWidth, columnWidth, leastCardWidth } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";
import { unsentTone } from "~/theme";

type TPointerDragArgs = {
  scale: number;
  /** Where the drag starts from, found when the button goes down. */
  from: () => TPoint;
  move: (to: TPoint) => void;
  drop: (to: TPoint) => void;
  click: () => void;
};

/** The pointer handlers of a drag in board units, which counts as a click until the pointer moves more than 3 pixels. */
const usePointerDrag = ({
  scale,
  from,
  move,
  drop,
  click,
}: TPointerDragArgs) => {
  const start = useRef<{ x: number; y: number; at: TPoint } | null>(null);
  const moved = useRef(false);
  const target = (
    event: PointerEvent,
    origin: { x: number; y: number; at: TPoint },
  ) => ({
    x: origin.at.x + (event.clientX - origin.x) / scale,
    y: origin.at.y + (event.clientY - origin.y) / scale,
  });
  return {
    onPointerDown: (event: PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      // The press takes the focus from an input, as a click elsewhere does, so that the keys act on the selection.
      if (document.activeElement instanceof HTMLElement)
        document.activeElement.blur();
      event.currentTarget.setPointerCapture(event.pointerId);
      start.current = { x: event.clientX, y: event.clientY, at: from() };
      moved.current = false;
    },
    onPointerMove: (event: PointerEvent<HTMLElement>) => {
      const origin = start.current;
      if (origin === null) return;
      moved.current ||=
        Math.hypot(event.clientX - origin.x, event.clientY - origin.y) > 3;
      if (moved.current) move(target(event, origin));
    },
    onPointerUp: (event: PointerEvent<HTMLElement>) => {
      const origin = start.current;
      start.current = null;
      if (origin === null) return;
      if (moved.current) drop(target(event, origin));
      else click();
    },
  };
};

type TCardFrameProps = {
  view: TCardView;
  scale: number;
  /** Takes the card's element when it mounts; returns what to do when it goes. */
  mount: (id: string, element: HTMLElement) => () => void;
};

/**
 * A card at its place on the board, as wide as its content needs up to a column of the grid unless someone set its width,
 * which looks the same for each author but for the icon. A drag on the card's header moves it, a drag on its bottom
 * right corner sets its width, a click selects it, and a double click on its text edits the markdown. Cards may cross
 * after their first place; a touch puts the card on top of the others. A card without a place is hidden until the
 * page gives it one, which needs its size.
 */
export const CardFrame = ({ view, scale, mount }: TCardFrameProps) => {
  const { id, card, at, versions, layer } = view;
  const store = useStore();
  const { model } = useBoard();
  const { selection, select, editing, edit, openHistory, remove } =
    useWhiteboard();
  const frame = useRef<HTMLElement | null>(null);
  const article = useCallback(
    (element: HTMLElement) => {
      frame.current = element;
      const unmount = mount(id, element);
      return () => {
        frame.current = null;
        unmount();
      };
    },
    [id, mount],
  );
  const mine = card.author === Author.enum.user;
  const AuthorIcon = mine ? User : Bot;
  /** The width that a resize shows before the server has it, over the width the card had when the resize started. */
  const [resizing, setResizing] = useState<{
    width: number;
    over: number | null;
  } | null>(null);
  const width =
    resizing !== null && resizing.over === view.width
      ? resizing.width
      : view.width;
  const resize = usePointerDrag({
    scale,
    from: () => {
      invariant(frame.current !== null, "the handle is in the card");
      return { x: width ?? frame.current.offsetWidth, y: 0 };
    },
    move: (to) => {
      setResizing({ width: clampCardWidth(to.x), over: view.width });
    },
    drop: (to) => {
      const next = clampCardWidth(to.x);
      setResizing({ width: next, over: view.width });
      void store
        .act({ kind: ActionKind.enum.resize, id, width: next })
        .then((taken) => {
          if (!taken) setResizing(null);
        });
    },
    click: () => undefined,
  });
  const drag = usePointerDrag({
    scale,
    from: () => {
      invariant(at !== null, "only a placed card shows and takes a drag");
      return at;
    },
    move: (to) => {
      store.drag(id, to);
    },
    drop: (to) => {
      store.drop(id, to);
    },
    // A click on the header selects the card alone; its feedback opens from its marks, or with C.
    click: () => {
      select({ kind: SelectionKind.enum.ref, ref: id }, false);
    },
  });
  const editor = editing?.card === id ? editing : null;
  const save = async (md: string, over: boolean) => {
    invariant(editor !== null, "the editor saves while it is open");
    const version = over ? {} : { version: editor.versions };
    if (await store.act({ kind: ActionKind.enum.put, id, md, ...version }))
      edit(null);
  };
  return (
    <article
      ref={article}
      data-ref={id}
      style={{
        left: at?.x ?? 0,
        top: at?.y ?? 0,
        width: width ?? "max-content",
        minWidth: leastCardWidth,
        maxWidth: width === null ? columnWidth : undefined,
        zIndex: layer,
        visibility: at === null ? "hidden" : "visible",
      }}
      className={`group/card card pointer-events-auto absolute flex animate-rise flex-col transition-shadow ${isSelected(selection, id) ? "ring-2 ring-accent-ring" : "ring-1 ring-edge-faint"}`}
      onPointerDownCapture={() => {
        store.touch(id);
      }}
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
          className={`grid size-5 shrink-0 place-items-center rounded-full text-white ${mine ? "bg-accent" : "bg-ink"}`}
        >
          <AuthorIcon className="size-3" />
        </span>
        <span className="truncate font-mono text-[11px] tracking-wide text-ink-faint">
          {id}
        </span>
        {card.edited ? (
          <span className="pill bg-accent-faint text-accent-strong">
            {mine ? "edited by the agent" : "edited by you"}
          </span>
        ) : null}
        {model.unsent.refs.has(id) ? (
          <span
            title="The agent does not have this card yet: Send"
            data-unsent=""
            className={`pill text-warning-strong ${unsentTone} -outline-offset-1`}
          >
            unsent
          </span>
        ) : null}
        {versions > 0 && (
          <button
            type="button"
            aria-label={`History of ${id}`}
            title={`Version ${String(versions + 1)}: show the earlier versions and their feedback`}
            className="pill bg-surface-sunken text-ink-muted hover:bg-accent-soft hover:text-accent-strong"
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
            variant="ghost"
            label={`Edit ${id}`}
            onClick={() => {
              edit(id);
            }}
          >
            <Pencil className="size-3.5" />
          </IconButton>
          <IconButton
            variant="ghost"
            label={`Remove ${id}`}
            onClick={() => {
              remove(id);
            }}
          >
            <Trash2 className="size-3.5" />
          </IconButton>
        </span>
        <Marks target={id} placement="header" />
        <Connector target={id} />
      </header>
      <div
        className="px-4 pb-4"
        onDoubleClick={(event) => {
          event.stopPropagation();
          edit(id);
        }}
      >
        {editor === null ? (
          <div key={versions} className="animate-pop">
            <CardBody id={id} md={card.md} />
          </div>
        ) : (
          <MarkdownEditor
            md={card.md}
            label={`Markdown of ${id}`}
            marked={editor.marked}
            changed={editor.versions !== versions}
            save={(md, over) => {
              void save(md, over);
            }}
            cancel={() => {
              edit(null);
            }}
          />
        )}
      </div>
      <span
        role="separator"
        aria-orientation="vertical"
        aria-label={`Width of ${id}`}
        aria-valuenow={width === null ? undefined : Math.round(width)}
        className="absolute right-0 bottom-0 size-4 cursor-ew-resize rounded-br-xl text-ink-ghost hover:text-ink-muted"
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
