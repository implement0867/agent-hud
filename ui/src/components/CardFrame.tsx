import { useCallback, useRef, useState } from "react";
import type { PointerEvent } from "react";

import { CardBody } from "~/components/CardBody";
import { ThreadMarks } from "~/components/Marks";
import { MarkdownEditor } from "~/components/MarkdownEditor";
import type { TCardView } from "~/data/boardModel";
import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";
import type { TPoint } from "~/domain/board";
import { toggledBox } from "~/domain/text";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import {
  clampCardWidth,
  columnWidth,
  leastCardHeight,
  leastCardWidth,
} from "~/lib/geometry";
import type { TRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";

type TPointerDragArgs = {
  scale: number;
  /** Where the drag starts from, found when the button goes down; null declines the drag. */
  from: (event: PointerEvent<HTMLElement>) => TPoint | null;
  move: (to: TPoint, by: TPoint) => void;
  drop: (to: TPoint, by: TPoint) => void;
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
  ) => {
    const by = {
      x: (event.clientX - origin.x) / scale,
      y: (event.clientY - origin.y) / scale,
    };
    return [{ x: origin.at.x + by.x, y: origin.at.y + by.y }, by] as const;
  };
  return {
    onPointerDown: (event: PointerEvent<HTMLElement>) => {
      if (event.button !== 0) return;
      const at = from(event);
      if (at === null) return;
      event.preventDefault();
      event.stopPropagation();
      // The press takes the focus from an input, as a click elsewhere does, so that the keys act on the selection.
      if (document.activeElement instanceof HTMLElement)
        document.activeElement.blur();
      event.currentTarget.setPointerCapture(event.pointerId);
      start.current = { x: event.clientX, y: event.clientY, at };
      moved.current = false;
    },
    onPointerMove: (event: PointerEvent<HTMLElement>) => {
      const origin = start.current;
      if (origin === null) return;
      moved.current ||=
        Math.hypot(event.clientX - origin.x, event.clientY - origin.y) > 3;
      if (moved.current) move(...target(event, origin));
    },
    onPointerUp: (event: PointerEvent<HTMLElement>) => {
      const origin = start.current;
      start.current = null;
      if (origin === null) return;
      if (moved.current) drop(...target(event, origin));
      else click();
    },
  };
};

/** A handle of the frame: the edges it moves, north, east, south and west. */
type THandle = {
  name: string;
  n?: true;
  e?: true;
  s?: true;
  w?: true;
  cursor: string;
  left: string;
  top: string;
};

const handles: THandle[] = [
  {
    name: "top left",
    n: true,
    w: true,
    cursor: "cursor-nwse-resize",
    left: "0%",
    top: "0%",
  },
  { name: "top", n: true, cursor: "cursor-ns-resize", left: "50%", top: "0%" },
  {
    name: "top right",
    n: true,
    e: true,
    cursor: "cursor-nesw-resize",
    left: "100%",
    top: "0%",
  },
  {
    name: "right",
    e: true,
    cursor: "cursor-ew-resize",
    left: "100%",
    top: "50%",
  },
  {
    name: "bottom right",
    s: true,
    e: true,
    cursor: "cursor-nwse-resize",
    left: "100%",
    top: "100%",
  },
  {
    name: "bottom",
    s: true,
    cursor: "cursor-ns-resize",
    left: "50%",
    top: "100%",
  },
  {
    name: "bottom left",
    s: true,
    w: true,
    cursor: "cursor-nesw-resize",
    left: "0%",
    top: "100%",
  },
  { name: "left", w: true, cursor: "cursor-ew-resize", left: "0%", top: "50%" },
];

/** The card's rect after a drag of the handle by the distance, kept at least as big as the least card. */
const resized = (rect: TRect, handle: THandle, by: TPoint): TRect => {
  const width = clampCardWidth(
    rect.width + (handle.e ? by.x : handle.w ? -by.x : 0),
  );
  const height = Math.max(
    leastCardHeight,
    rect.height + (handle.s ? by.y : handle.n ? -by.y : 0),
  );
  return {
    x: handle.w ? rect.x + rect.width - width : rect.x,
    y: handle.n ? rect.y + rect.height - height : rect.y,
    width,
    height,
  };
};

type TResizeHandleProps = {
  id: string;
  handle: THandle;
  scale: number;
  rect: () => TRect;
  active: boolean;
  show: (rect: TRect | null, handle: string | null) => void;
  commit: (rect: TRect, handle: THandle) => void;
};

/** A handle on the frame: a drag sets the card's width, height or both, from that edge or corner. */
const ResizeHandle = ({
  id,
  handle,
  scale,
  rect,
  active,
  show,
  commit,
}: TResizeHandleProps) => {
  const start = useRef<TRect | null>(null);
  const drag = usePointerDrag({
    scale,
    from: () => {
      start.current = rect();
      return { x: 0, y: 0 };
    },
    move: (_to, by) => {
      invariant(start.current !== null, "a drag starts before it moves");
      show(resized(start.current, handle, by), handle.name);
    },
    drop: (_to, by) => {
      invariant(start.current !== null, "a drag starts before it drops");
      commit(resized(start.current, handle, by), handle);
    },
    click: () => undefined,
  });
  return (
    <span
      role="separator"
      aria-label={`Resize ${id} from the ${handle.name}`}
      className={`absolute z-10 grid size-4 -translate-1/2 place-items-center ${handle.cursor}`}
      style={{ left: handle.left, top: handle.top }}
      {...drag}
    >
      <span
        className={`size-2 rounded-full shadow-[0_0_0_1.5px_var(--accent-ring)] ${active ? "bg-accent shadow-[0_0_0_1.5px_var(--accent)]" : "bg-surface"}`}
      />
    </span>
  );
};

type TChangeLinksProps = { id: string; changed: boolean };

/** The links at the right of the card's title line: hide or show the changes of the last version, and the history. */
const ChangeLinks = ({ id, changed }: TChangeLinksProps) => {
  const store = useStore();
  const { openHistory } = useWhiteboard();
  const link =
    "cursor-pointer text-ink-muted hover:text-ink-soft hover:underline";
  return (
    <span
      data-chrome=""
      className="absolute top-[calc(var(--pad-y)+4px)] right-11 z-10 flex gap-1.5 text-[0.6875rem] leading-4 text-ink-muted"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
      }}
    >
      <button
        type="button"
        className={link}
        onClick={(event) => {
          event.stopPropagation();
          if (changed) store.sawChanges(id);
          else store.showChanges(id);
        }}
      >
        {changed ? "Hide changes" : "Show changes"}
      </button>
      <span aria-hidden className="text-ink-ghost">
        ·
      </span>
      <button
        type="button"
        aria-label={`History of ${id}`}
        className={link}
        onClick={(event) => {
          event.stopPropagation();
          openHistory(id);
        }}
      >
        History
      </button>
    </span>
  );
};

type TCardFrameProps = {
  view: TCardView;
  scale: number;
  /** Takes the card's element when it mounts; returns what to do when it goes. */
  mount: (id: string, element: HTMLElement) => () => void;
};

/**
 * A card at its place on the board: its markdown from the first line, with no strip above it. A drag on the card's
 * padding moves it; the frame that shows on hover has a handle at each edge and corner, which sets the width, the height
 * or both. A click selects the card, a selection of its words opens the toolbar of the selection, and a double click
 * edits the markdown. A card shorter than its text scrolls, with fades at its ends. Cards may cross after their first
 * place; a touch puts the card on top of the others. A card without a place is hidden until the page gives it one.
 */
export const CardFrame = ({ view, scale, mount }: TCardFrameProps) => {
  const { id, card, at, versions, layer } = view;
  const store = useStore();
  const { model } = useBoard();
  const { selection, select, editing, edit, linking, look } = useWhiteboard();
  const frame = useRef<HTMLElement | null>(null);
  const body = useRef<HTMLDivElement | null>(null);
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
  const before = model.changed[id] ?? null;
  /** The rect that a resize shows before the server has it, and the handle that makes it. */
  const [resizing, setResizing] = useState<{
    rect: TRect;
    handle: string | null;
    over: string;
  } | null>(null);
  const [ends, setEnds] = useState({ top: false, bottom: false });
  const sizeKey = `${String(view.width)}x${String(view.height)}`;
  const live = resizing !== null && resizing.over === sizeKey ? resizing : null;
  const width = live?.rect.width ?? view.width;
  const height = live?.rect.height ?? view.height;
  const place = live === null ? at : { x: live.rect.x, y: live.rect.y };
  const rect = (): TRect => {
    invariant(
      frame.current !== null && at !== null,
      "a placed card takes a resize",
    );
    return {
      ...at,
      width: frame.current.offsetWidth,
      height: frame.current.offsetHeight,
    };
  };
  const commit = (next: TRect, handle: THandle) => {
    setResizing({ rect: next, handle: null, over: sizeKey });
    if (at !== null && (next.x !== at.x || next.y !== at.y))
      store.drop(id, { x: next.x, y: next.y });
    const sides = {
      ...(handle.e || handle.w ? { width: next.width } : {}),
      ...(handle.n || handle.s ? { height: next.height } : {}),
    };
    void store
      .act({ kind: ActionKind.enum.resize, id, ...sides })
      .then((taken) => {
        if (!taken) setResizing(null);
      });
  };
  const drag = usePointerDrag({
    scale,
    // The padding of the card and its frame move it; its words take a selection instead.
    from: (event) => {
      const target = event.target;
      if (at === null || !(target instanceof Element)) return null;
      return target.closest("[data-text-root], button, input, textarea, a") ===
        null
        ? at
        : null;
    },
    move: (to) => {
      store.drag(id, to);
    },
    drop: (to) => {
      store.drop(id, to);
    },
    click: () => {
      select({ kind: SelectionKind.enum.card, id });
    },
  });
  const editor = editing?.card === id ? editing : null;
  const save = async (md: string, over: boolean) => {
    invariant(editor !== null, "the editor saves while it is open");
    const version = over ? {} : { version: editor.versions };
    if (await store.act({ kind: ActionKind.enum.put, id, md, ...version }))
      edit(null);
  };
  const toggle = useCallback(
    (start: number, end: number) => {
      const current = store.read().board.cards[id];
      if (current === undefined) return;
      void store.act({
        kind: ActionKind.enum.put,
        id,
        md: toggledBox(current.md, start, end),
        version: store.read().board.history[id]?.length ?? 0,
      });
    },
    [store, id],
  );
  const selected =
    selection?.kind === SelectionKind.enum.card && selection.id === id;
  const dropTarget = linking?.over === id && linking.from.card !== id;
  const ring =
    editor !== null
      ? "shadow-[var(--shadow-card),0_0_0_2px_var(--accent-ring)]"
      : dropTarget
        ? "shadow-[var(--shadow-card),0_0_0_2px_var(--draw)]"
        : selected
          ? "shadow-[var(--shadow-card),0_0_0_1.5px_var(--accent-ring)]"
          : "shadow-[var(--shadow-card),0_0_0_1px_var(--edge-faint)]";
  const measureEnds = () => {
    const element = body.current;
    if (element === null) return;
    const next = {
      top: element.scrollTop > 1,
      bottom:
        element.scrollHeight - element.scrollTop - element.clientHeight > 1,
    };
    if (next.top !== ends.top || next.bottom !== ends.bottom) setEnds(next);
  };
  return (
    <article
      ref={article}
      data-card={id}
      aria-label={`Card ${id}`}
      style={{
        left: place?.x ?? 0,
        top: place?.y ?? 0,
        width: width ?? "max-content",
        // The editor shows the whole markdown, whatever height the card has.
        height: editor === null ? (height ?? undefined) : undefined,
        minWidth: leastCardWidth,
        maxWidth: width === null ? columnWidth : undefined,
        zIndex: layer,
        visibility: at === null ? "hidden" : "visible",
      }}
      className={`group/card pointer-events-auto absolute flex animate-rise flex-col rounded-card bg-surface transition-shadow ${ring}`}
      onPointerDownCapture={() => {
        store.touch(id);
      }}
      onClick={(event) => {
        event.stopPropagation();
        if (window.getSelection()?.isCollapsed !== false)
          select({ kind: SelectionKind.enum.card, id });
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        window.getSelection()?.removeAllRanges();
        edit(id);
      }}
      {...drag}
    >
      <div
        ref={body}
        className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-card py-[var(--pad-y)] pr-11 pb-[var(--pad)] pl-[var(--pad)] [scrollbar-color:var(--ink-ghost)_transparent] [scrollbar-width:thin]"
        onScroll={measureEnds}
        onPointerEnter={measureEnds}
      >
        {editor === null ? (
          <>
            {versions > 0 && <ChangeLinks id={id} changed={before !== null} />}
            <div
              key={versions}
              className={`animate-pop ${versions > 0 ? "[&_.markdown>:first-child]:pr-36" : ""}`}
            >
              <CardBody
                md={card.md}
                before={before}
                diffStyle={look.diff}
                toggle={toggle}
              />
            </div>
            <ThreadMarks
              card={id}
              body={body}
              version={`${card.md}|${String(before)}|${String(width)}|${look.diff}`}
            />
          </>
        ) : (
          <MarkdownEditor
            md={card.md}
            label={`Markdown of ${id}`}
            quotes={editor.quotes}
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
      {height !== null && ends.top ? (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-7 rounded-t-card bg-linear-to-b from-surface to-transparent"
        />
      ) : null}
      {height !== null && ends.bottom ? (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-7 rounded-b-card bg-linear-to-t from-surface to-transparent"
        />
      ) : null}
      {editor === null && at !== null && (
        <span
          className={`pointer-events-none absolute inset-0 rounded-card shadow-[0_0_0_1.5px_var(--accent-ring)] ${live !== null || selected ? "block" : "hidden group-hover/card:block"}`}
        >
          <span className="pointer-events-auto">
            {handles.map((handle) => (
              <ResizeHandle
                key={handle.name}
                id={id}
                handle={handle}
                scale={scale}
                rect={rect}
                active={live?.handle === handle.name}
                show={(next, name) => {
                  setResizing(
                    next === null
                      ? null
                      : { rect: next, handle: name, over: sizeKey },
                  );
                }}
                commit={commit}
              />
            ))}
          </span>
        </span>
      )}
    </article>
  );
};
