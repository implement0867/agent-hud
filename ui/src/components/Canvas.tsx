import { useEffect, useRef, useState } from "react";
import type {
  Dispatch,
  PointerEvent,
  ReactNode,
  RefObject,
  SetStateAction,
} from "react";

import { toBoard, zoomAt } from "~/lib/geometry";
import type { TView } from "~/lib/geometry";
import type { TPoint } from "~/schemas/board";

/**
 * The board under a view that pans and zooms. A drag on empty space, a drag with Space held, or a scroll pans;
 * Ctrl or ⌘ with a scroll zooms at the pointer. The content takes pointer events only where it sets pointer-events-auto.
 */
export const Canvas = ({
  view,
  setView,
  viewport,
  world,
  clear,
  create,
  overlay,
  children,
}: {
  view: TView;
  setView: Dispatch<SetStateAction<TView>>;
  viewport: RefObject<HTMLDivElement | null>;
  world: RefObject<HTMLDivElement | null>;
  clear: () => void;
  create: (at: TPoint) => void;
  overlay: ReactNode;
  children: ReactNode;
}) => {
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const [space, setSpace] = useState(false);

  useEffect(() => {
    const root = viewport.current;
    if (root === null) return;
    const onWheel = (event: WheelEvent) => {
      const onBoard =
        event.target === root ||
        (event.target instanceof Node && world.current?.contains(event.target));
      if (onBoard !== true) return;
      event.preventDefault();
      const box = root.getBoundingClientRect();
      const at = { x: event.clientX - box.left, y: event.clientY - box.top };
      const { deltaX, deltaY } = event;
      setView((view) =>
        event.ctrlKey || event.metaKey
          ? zoomAt(view, Math.exp(-deltaY / 300), at)
          : { ...view, x: view.x - deltaX, y: view.y - deltaY },
      );
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === " " && event.target === document.body) {
        event.preventDefault();
        setSpace(event.type === "keydown");
      }
    };
    root.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKey);
    return () => {
      root.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKey);
    };
  }, [viewport, world, setView]);

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const empty = event.target === event.currentTarget;
    if (!empty && !space && event.button !== 1) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, moved: !empty };
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const from = drag.current;
    if (from === null) return;
    const { clientX, clientY } = event;
    drag.current = {
      x: clientX,
      y: clientY,
      moved: from.moved || Math.hypot(clientX - from.x, clientY - from.y) > 3,
    };
    setView((view) => ({
      ...view,
      x: view.x + clientX - from.x,
      y: view.y + clientY - from.y,
    }));
  };

  const onPointerUp = () => {
    if (drag.current?.moved === false) clear();
    drag.current = null;
  };

  const grid = 24 * view.scale;
  return (
    <div
      ref={viewport}
      role="application"
      aria-label="Board"
      className={`relative flex-1 touch-none overflow-clip bg-stone-100 select-none ${space ? "cursor-grab active:cursor-grabbing" : ""}`}
      style={{
        backgroundImage:
          "radial-gradient(circle, rgb(168 162 158 / 0.55) 1px, transparent 1.2px)",
        backgroundSize: `${String(grid)}px ${String(grid)}px`,
        backgroundPosition: `${String(view.x)}px ${String(view.y)}px`,
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onDoubleClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const box = event.currentTarget.getBoundingClientRect();
        create(
          toBoard(view, {
            x: event.clientX - box.left,
            y: event.clientY - box.top,
          }),
        );
      }}
    >
      <div
        ref={world}
        className={`pointer-events-none absolute top-0 left-0 origin-top-left ${space ? "[&_*]:pointer-events-none!" : ""}`}
        style={{
          transform: `translate(${String(view.x)}px, ${String(view.y)}px) scale(${String(view.scale)})`,
        }}
      >
        {children}
      </div>
      <div className="pointer-events-none absolute inset-0">{overlay}</div>
    </div>
  );
};
