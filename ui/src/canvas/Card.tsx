import { memo, useCallback, useMemo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent } from "react";

import { Icon } from "~/chrome/icons";
import { Anchor } from "~/feedback/Anchor";
import { cx } from "~/lib/cx";
import { useStore } from "~/lib/store";
import { Body } from "~/primitives/Body";
import type { BoxEl } from "~/protocol/schema";
import { boardStore } from "~/store/board";
import { useSend } from "~/store/socket";
import { select, uiStore } from "~/store/ui";

const kindLabel: Readonly<Record<BoxEl["kind"], string>> = {
  text: "Text",
  list: "List",
  table: "Table",
  itable: "Table",
};

type Point = { x: number; y: number };

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

const CardFrame = ({ el }: { el: BoxEl }) => {
  const send = useSend();
  const placed = useStore(uiStore, (s) => s.placed[el.id]);
  const selected = useStore(uiStore, (s) => s.selected === el.id);
  const fresh = useStore(boardStore, (s) => s.fresh.includes(el.id));
  const [offset, setOffset] = useState<Point | null>(null);
  // Local values after a move or resize, valid until the server echoes a new value.
  const [moved, setMoved] = useState<{ to: Point; from: Point | null } | null>(
    null,
  );
  const [sized, setSized] = useState<{
    to: number;
    from: number | null;
  } | null>(null);
  const [width, setWidth] = useState<number | null>(null);
  const drag = useRef<{ start: Point; base: Point } | null>(null);
  const resize = useRef<{ start: number; base: number } | null>(null);
  const node = useRef<HTMLDivElement>(null);

  const server = useMemo<Point | null>(
    () => (el.x !== null && el.y !== null ? { x: el.x, y: el.y } : null),
    [el.x, el.y],
  );
  const base = useMemo<Point | null>(() => {
    if (
      moved !== null &&
      moved.from?.x === server?.x &&
      moved.from?.y === server?.y
    )
      return moved.to;
    return server ?? placed ?? null;
  }, [moved, server, placed]);

  const onPointerDown = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      if (
        e.button !== 0 ||
        base === null ||
        isControl(e.target) ||
        uiStore.get().tool === "link"
      )
        return;
      select(el.id);
      drag.current = { start: { x: e.clientX, y: e.clientY }, base };
      e.currentTarget.setPointerCapture(e.pointerId);
      e.stopPropagation();
    },
    [el.id, base],
  );
  const onPointerMove = useCallback((e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (d === null) return;
    const { zoom } = uiStore.get().viewport;
    setOffset({
      x: (e.clientX - d.start.x) / zoom,
      y: (e.clientY - d.start.y) / zoom,
    });
  }, []);
  const onPointerUp = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      const d = drag.current;
      drag.current = null;
      if (d === null) return;
      const { zoom } = uiStore.get().viewport;
      const target = {
        x: d.base.x + (e.clientX - d.start.x) / zoom,
        y: d.base.y + (e.clientY - d.start.y) / zoom,
      };
      setOffset(null);
      if (target.x !== d.base.x || target.y !== d.base.y) {
        setMoved({ to: target, from: server });
        send({ t: "move", id: el.id, ...target });
      }
    },
    [send, el.id, server],
  );

  const onResizeDown = useCallback((e: PointerEvent<HTMLDivElement>) => {
    const box = node.current;
    if (box === null) return;
    resize.current = { start: e.clientX, base: box.offsetWidth };
    e.currentTarget.setPointerCapture(e.pointerId);
    e.stopPropagation();
  }, []);
  const onResizeMove = useCallback((e: PointerEvent<HTMLDivElement>) => {
    const r = resize.current;
    if (r === null) return;
    const { zoom } = uiStore.get().viewport;
    setWidth(
      Math.min(1600, Math.max(220, r.base + (e.clientX - r.start) / zoom)),
    );
  }, []);
  const onResizeUp = useCallback(() => {
    resize.current = null;
    if (width === null) return;
    setSized({ to: width, from: el.w });
    setWidth(null);
    send({ t: "resize", id: el.id, w: width });
  }, [send, el.id, el.w, width]);

  const remove = useCallback(() => {
    send({ t: "delete", id: el.id });
  }, [send, el.id]);

  const w = width ?? (sized !== null && sized.from === el.w ? sized.to : el.w);
  const style: CSSProperties =
    base === null
      ? { left: -100000, top: -100000, visibility: "hidden" }
      : {
          left: base.x + (offset?.x ?? 0),
          top: base.y + (offset?.y ?? 0),
          ...(w === null ? {} : { width: w, maxWidth: "none" }),
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
        offset !== null && "card-dragging",
      )}
      style={style}
      data-card={el.id}
      data-unplaced={base === null ? "" : undefined}
    >
      <div
        className="card-head"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
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
            onClick={remove}
            title="Delete"
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
        onPointerDown={onResizeDown}
        onPointerMove={onResizeMove}
        onPointerUp={onResizeUp}
        title="Drag to resize"
      />
    </div>
  );
};
