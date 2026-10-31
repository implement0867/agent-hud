import { useRef } from "react";
import type { PointerEvent } from "react";

import type { TPoint } from "~/domain/board";

type TPointerDragArgs = {
  scale: number;
  /** Where the drag starts from, found when the button goes down; null declines the drag. */
  from: (event: PointerEvent<HTMLElement>) => TPoint | null;
  move: (to: TPoint, by: TPoint) => void;
  drop: (to: TPoint, by: TPoint) => void;
  click: () => void;
};

/** The pointer handlers of a drag in board units, which counts as a click until the pointer moves more than 3 pixels. */
export const usePointerDrag = ({
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
