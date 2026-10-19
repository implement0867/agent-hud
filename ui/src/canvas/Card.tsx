import { memo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent } from "react";

import type { Point } from "~/canvas/viewport";
import { Icon } from "~/chrome/icons";
import { Anchor } from "~/feedback/Anchor";
import { cx } from "~/lib/cx";
import { useStore } from "~/lib/store";
import { Body } from "~/primitives/Body";
import type { BoxEl } from "~/protocol/schema";
import { boardStore, updateBox } from "~/store/board";
import { useSend } from "~/store/socket";
import { select, uiStore } from "~/store/ui";

const kindLabel: Readonly<Record<BoxEl["kind"], string>> = {
  text: "Text",
  list: "List",
  table: "Table",
};

export const Card = memo(({ id }: { id: string }) => {
  const el = useStore(boardStore, (s) => s.elements[id]);
  if (el === undefined || el.kind === "link") return null;
  return <CardFrame el={el} />;
});
Card.displayName = "Card";

const isControl = (target: EventTarget) =>
  target instanceof Element &&
  target.closest("button, input, textarea, select, a, .anchor-actions") !==
    null;

/** Distance the pointer moved since `from`, in world units. */
const worldDelta = (e: PointerEvent, from: Point): Point => {
  const { zoom } = uiStore.get().viewport;
  return { x: (e.clientX - from.x) / zoom, y: (e.clientY - from.y) / zoom };
};

const CardFrame = ({ el }: { el: BoxEl }) => {
  const send = useSend();
  const selected = useStore(uiStore, (s) => s.selected === el.id);
  const fresh = useStore(boardStore, (s) => s.fresh.includes(el.id));
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ start: Point; base: Point } | null>(null);
  const resize = useRef<{ start: Point; base: number } | null>(null);
  const node = useRef<HTMLDivElement>(null);

  const dragTo = (e: PointerEvent): Point | null => {
    const d = drag.current;
    if (d === null) return null;
    const delta = worldDelta(e, d.start);
    return { x: d.base.x + delta.x, y: d.base.y + delta.y };
  };
  const resizeTo = (e: PointerEvent): number | null => {
    const r = resize.current;
    return r === null
      ? null
      : Math.min(1600, Math.max(220, r.base + worldDelta(e, r.start).x));
  };

  const style: CSSProperties =
    el.x === null || el.y === null
      ? { left: -100000, top: -100000, visibility: "hidden" }
      : {
          left: el.x,
          top: el.y,
          ...(el.w === null ? {} : { width: el.w, maxWidth: "none" }),
        };
  const note = el.kind === "text" && el.author === "user";

  return (
    <div
      ref={node}
      className={cx(
        "card",
        `card-${el.kind}`,
        note && "card-note",
        selected && "card-selected",
        fresh && "card-fresh",
        dragging && "card-dragging",
      )}
      style={style}
      data-card={el.id}
      data-unplaced={el.x === null ? "" : undefined}
    >
      <div
        className="card-head"
        onPointerDown={(e) => {
          const { x, y } = el;
          if (e.button !== 0 || x === null || y === null) return;
          if (isControl(e.target) || uiStore.get().tool === "link") return;
          select(el.id);
          drag.current = {
            start: { x: e.clientX, y: e.clientY },
            base: { x, y },
          };
          setDragging(true);
          e.currentTarget.setPointerCapture(e.pointerId);
          e.stopPropagation();
        }}
        onPointerMove={(e) => {
          const to = dragTo(e);
          if (to !== null) updateBox(el.id, to);
        }}
        onPointerUp={(e) => {
          const to = dragTo(e);
          drag.current = null;
          setDragging(false);
          if (to !== null) send({ t: "move", id: el.id, ...to });
        }}
      >
        <Anchor el={el} anchor="" className="card-anchor">
          <div className="card-title">
            <span className="card-id">{el.id}</span>
            <span className="card-name">
              {el.title ?? (note ? "Note" : kindLabel[el.kind])}
            </span>
          </div>
        </Anchor>
        {el.author === "user" ? (
          <button
            type="button"
            className="card-delete"
            title="Delete"
            onClick={() => {
              send({ t: "delete", id: el.id });
            }}
          >
            <Icon name="trash" size={14} />
          </button>
        ) : null}
      </div>
      <div className="card-body">
        <Body el={el} />
      </div>
      <div
        className="card-resize"
        title="Drag to resize"
        onPointerDown={(e) => {
          if (node.current === null) return;
          resize.current = {
            start: { x: e.clientX, y: e.clientY },
            base: node.current.offsetWidth,
          };
          e.currentTarget.setPointerCapture(e.pointerId);
          e.stopPropagation();
        }}
        onPointerMove={(e) => {
          const w = resizeTo(e);
          if (w !== null) updateBox(el.id, { w });
        }}
        onPointerUp={(e) => {
          const w = resizeTo(e);
          resize.current = null;
          if (w !== null) send({ t: "resize", id: el.id, w });
        }}
      />
    </div>
  );
};
