import { useRef } from "react";

import type { TPoint } from "~/domain/board";
import { usePointerDrag } from "~/hooks/usePointerDrag";
import { clampCardWidth, leastCardHeight } from "~/lib/geometry";
import type { TRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";

/** A handle of the frame: the edges it moves, north, east, south and west. */
export type THandle = {
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
const resizeRect = (rect: TRect, handle: THandle, by: TPoint): TRect => {
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
  show: (rect: TRect, handle: string) => void;
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
      show(resizeRect(start.current, handle, by), handle.name);
    },
    drop: (_to, by) => {
      invariant(start.current !== null, "a drag starts before it drops");
      commit(resizeRect(start.current, handle, by), handle);
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

type TResizeOutlineProps = {
  id: string;
  scale: number;
  rect: () => TRect;
  activeHandle: string | null;
  shown: boolean;
  resizable: boolean;
  show: (rect: TRect, handle: string) => void;
  commit: (rect: TRect, handle: THandle) => void;
};

/**
 * The outline of a card that shows on hover and while the card is selected or resized, with a handle at each edge and
 * corner. A card that is not resizable, such as a folded one, which is one line tall whatever its size, has no handles.
 */
export const ResizeOutline = ({
  id,
  scale,
  rect,
  activeHandle,
  shown,
  resizable,
  show,
  commit,
}: TResizeOutlineProps) => (
  <span
    className={`pointer-events-none absolute inset-0 rounded-card shadow-[0_0_0_1.5px_var(--accent-ring)] ${shown ? "block" : "hidden group-hover/card:block"}`}
  >
    <span className={resizable ? "pointer-events-auto" : "hidden"}>
      {handles.map((handle) => (
        <ResizeHandle
          key={handle.name}
          id={id}
          handle={handle}
          scale={scale}
          rect={rect}
          active={activeHandle === handle.name}
          show={show}
          commit={commit}
        />
      ))}
    </span>
  </span>
);
