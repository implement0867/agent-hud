import { useEffect, useRef, useState } from "react";
import type { PointerEvent, ReactNode } from "react";

export type TView = { x: number; y: number; scale: number };

const home: TView = { x: 32, y: 32, scale: 1 };

const clamp = (scale: number) => Math.min(4, Math.max(0.2, scale));

/** The view zoomed by factor, with the point under (px, py) in the viewport kept in place. */
const zoomAt = (view: TView, factor: number, px: number, py: number) => {
  const scale = clamp(view.scale * factor);
  const ratio = scale / view.scale;
  return {
    x: px - (px - view.x) * ratio,
    y: py - (py - view.y) * ratio,
    scale,
  };
};

const ZoomButton = ({
  label,
  text,
  onClick,
}: {
  label: string;
  text: string;
  onClick: () => void;
}) => (
  <button
    type="button"
    aria-label={label}
    className="rounded border border-stone-300 bg-white px-2 text-sm text-stone-600 hover:bg-stone-100"
    onClick={onClick}
  >
    {text}
  </button>
);

/** A drag on empty space or a scroll pans, and Ctrl or ⌘ with a scroll zooms at the pointer. The content takes pointer events only where it sets pointer-events-auto. */
export const Canvas = ({
  children,
}: {
  children: (view: TView) => ReactNode;
}) => {
  const [view, setView] = useState(home);
  const drag = useRef<{ x: number; y: number } | null>(null);
  const viewport = useRef<HTMLDivElement>(null);

  const zoomCentre = (factor: number) => {
    const box = viewport.current?.getBoundingClientRect();
    if (box !== undefined)
      setView((view) => zoomAt(view, factor, box.width / 2, box.height / 2));
  };

  /** React listens to wheel events passively, so only a native listener can stop the browser zoom on Ctrl or ⌘. */
  useEffect(() => {
    const root = viewport.current;
    if (root === null) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const box = root.getBoundingClientRect();
      const { deltaX, deltaY, clientX, clientY } = event;
      if (event.ctrlKey || event.metaKey)
        setView((view) =>
          zoomAt(
            view,
            Math.exp(-deltaY / 300),
            clientX - box.left,
            clientY - box.top,
          ),
        );
      else
        setView((view) => ({
          ...view,
          x: view.x - deltaX,
          y: view.y - deltaY,
        }));
    };
    root.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      root.removeEventListener("wheel", onWheel);
    };
  }, []);

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY };
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const from = drag.current;
    if (from === null) return;
    const { clientX, clientY } = event;
    drag.current = { x: clientX, y: clientY };
    setView((view) => ({
      ...view,
      x: view.x + clientX - from.x,
      y: view.y + clientY - from.y,
    }));
  };

  const onPointerUp = () => {
    drag.current = null;
  };

  return (
    <div
      ref={viewport}
      role="application"
      aria-label="Board"
      className="relative flex-1 cursor-grab touch-none overflow-hidden active:cursor-grabbing"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div
        className="pointer-events-none absolute top-0 left-0 origin-top-left"
        style={{
          transform: `translate(${String(view.x)}px, ${String(view.y)}px) scale(${String(view.scale)})`,
        }}
      >
        {children(view)}
      </div>
      <div className="absolute right-4 bottom-4 flex gap-1">
        <ZoomButton
          label="Zoom out"
          text="−"
          onClick={() => {
            zoomCentre(1 / 1.25);
          }}
        />
        <ZoomButton
          label="Reset view"
          text={`${String(Math.round(view.scale * 100))}%`}
          onClick={() => {
            setView(home);
          }}
        />
        <ZoomButton
          label="Zoom in"
          text="+"
          onClick={() => {
            zoomCentre(1.25);
          }}
        />
      </div>
    </div>
  );
};
