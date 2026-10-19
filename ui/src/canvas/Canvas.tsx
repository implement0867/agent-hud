import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";

import { Card } from "~/canvas/Card";
import { NoteDraft } from "~/canvas/Drafts";
import { fitView } from "~/canvas/view";
import { LinkPaths, LinkTexts } from "~/canvas/Links";
import { useLinkLayer } from "~/canvas/useLinkLayer";
import { nextPlacement } from "~/canvas/placement";
import { reveal, toWorld, zoomAt } from "~/canvas/viewport";
import type { Point } from "~/canvas/viewport";
import { cardNode, cardRect, useWorld } from "~/canvas/world";
import { cx } from "~/lib/cx";
import { isTyping } from "~/lib/dom";
import { useStore } from "~/lib/store";
import { boardStore, updateBox } from "~/store/board";
import { useSend } from "~/store/socket";
import { select, uiStore } from "~/store/ui";

const onCard = (target: EventTarget) =>
  target instanceof Element && target.closest("[data-card]") !== null;

/** Place cards the agent left unplaced, in a left-to-right flow. */
const usePlacement = () => {
  const send = useSend();
  const { layerRef } = useWorld();
  const order = useStore(boardStore, (s) => s.order);
  const elements = useStore(boardStore, (s) => s.elements);

  useLayoutEffect(() => {
    const root = layerRef.current;
    if (root === null) return;
    const unplaced = order.filter((id) => {
      const el = elements[id];
      return (
        el !== undefined &&
        el.kind !== "link" &&
        (el.x === null || el.y === null)
      );
    });
    if (unplaced.length === 0) return;
    const rects = order.flatMap((id) => {
      const node = unplaced.includes(id) ? null : cardNode(root, id);
      return node === null || node.dataset["unplaced"] !== undefined
        ? []
        : [cardRect(node)];
    });
    for (const id of unplaced) {
      const node = cardNode(root, id);
      const size =
        node === null
          ? { w: 380, h: 240 }
          : { w: node.offsetWidth, h: node.offsetHeight };
      const at = nextPlacement(rects, size);
      rects.push({ ...at, ...size });
      updateBox(id, at);
      send({ t: "place", id, ...at });
    }
  }, [order, elements, layerRef, send]);
};

/** Fit everything once on first load; afterwards, pan to each new agent card. */
const useFollow = () => {
  const world = useWorld();
  const fresh = useStore(boardStore, (s) => s.fresh);
  const count = useStore(boardStore, (s) => s.order.length);
  const fitted = useRef(false);
  const revealed = useRef(new Set<string>());

  useEffect(() => {
    if (fitted.current || count === 0) return;
    const frame = requestAnimationFrame(() => {
      fitView(world);
      fitted.current = true;
    });
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [count, world]);

  useEffect(() => {
    const id = fresh.at(-1);
    if (id === undefined || revealed.current.has(id) || !fitted.current) return;
    const frame = requestAnimationFrame(() => {
      const root = world.layerRef.current;
      const box = world.containerRef.current;
      const node = root === null ? null : cardNode(root, id);
      if (
        node === null ||
        box === null ||
        node.dataset["unplaced"] !== undefined
      )
        return;
      revealed.current.add(id);
      const next = reveal(uiStore.get().viewport, cardRect(node), {
        w: box.clientWidth,
        h: box.clientHeight,
      });
      if (next !== null) uiStore.set((s) => ({ ...s, viewport: next }));
    });
    return () => {
      cancelAnimationFrame(frame);
    };
  });
};

const useWheel = () => {
  const { containerRef } = useWorld();
  useEffect(() => {
    const node = containerRef.current;
    if (node === null) return;
    const onWheel = (e: WheelEvent) => {
      if (
        e.target instanceof Element &&
        e.target.closest("textarea, select, .thread-popover") !== null
      )
        return;
      e.preventDefault();
      const rect = node.getBoundingClientRect();
      const screen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      uiStore.set((s) => ({
        ...s,
        viewport:
          e.ctrlKey || e.metaKey
            ? zoomAt(s.viewport, screen, Math.exp(-e.deltaY * 0.01))
            : {
                ...s.viewport,
                x: s.viewport.x - e.deltaX,
                y: s.viewport.y - e.deltaY,
              },
      }));
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      node.removeEventListener("wheel", onWheel);
    };
  }, [containerRef]);
};

const useSpaceHeld = () => {
  const [held, setHeld] = useState(false);
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isTyping(e.target)) {
        e.preventDefault();
        setHeld(true);
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") setHeld(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);
  return held;
};

export const Canvas = () => {
  const { containerRef, layerRef } = useWorld();
  const viewport = useStore(uiStore, (s) => s.viewport);
  const tool = useStore(uiStore, (s) => s.tool);
  const order = useStore(boardStore, (s) => s.order);
  const space = useSpaceHeld();
  const pan = useRef<{ start: Point; base: Point } | null>(null);
  const [panning, setPanning] = useState(false);
  usePlacement();
  useFollow();
  useWheel();
  const linkLayer = useLinkLayer();

  // Open on click: opening on pointerdown loses focus to the mousedown that follows.
  const openNote = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const at = toWorld(uiStore.get().viewport, {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
    uiStore.set((s) => ({ ...s, tool: "note", noteDraft: at }));
  };

  const grid = 24 * viewport.zoom;
  return (
    <div
      ref={containerRef}
      className={cx(
        "canvas",
        `tool-${tool}`,
        (space || tool === "hand") && "canvas-grab",
        panning && "canvas-panning",
      )}
      style={{
        backgroundSize: `${String(grid)}px ${String(grid)}px`,
        backgroundPosition: `${String(viewport.x)}px ${String(viewport.y)}px`,
      }}
      onPointerDown={(e) => {
        const background = !onCard(e.target);
        const { tool: current, viewport: v } = uiStore.get();
        if (current === "note" && background && e.button === 0) return;
        const wantsPan =
          e.button === 1 ||
          space ||
          current === "hand" ||
          (background && e.button === 0);
        if (!wantsPan) return;
        if (background && current === "select") select(null);
        if (background && current === "link")
          uiStore.set((s) => ({ ...s, linkFrom: null }));
        pan.current = {
          start: { x: e.clientX, y: e.clientY },
          base: { x: v.x, y: v.y },
        };
        setPanning(true);
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        const p = pan.current;
        if (p === null) return;
        uiStore.set((s) => ({
          ...s,
          viewport: {
            ...s.viewport,
            x: p.base.x + e.clientX - p.start.x,
            y: p.base.y + e.clientY - p.start.y,
          },
        }));
      }}
      onPointerUp={() => {
        pan.current = null;
        setPanning(false);
      }}
      onClick={(e) => {
        if (uiStore.get().tool === "note" && !onCard(e.target)) openNote(e);
      }}
      onDoubleClick={(e) => {
        if (!onCard(e.target)) openNote(e);
      }}
    >
      <div
        ref={layerRef}
        className="world"
        style={{
          transform: `translate(${String(viewport.x)}px, ${String(viewport.y)}px) scale(${String(viewport.zoom)})`,
        }}
      >
        {/* Arrows under the cards, so they never block card controls. */}
        <LinkPaths {...linkLayer} />
        {order.map((id) => (
          <Card key={id} id={id} />
        ))}
        <LinkTexts {...linkLayer} />
        <NoteDraft />
      </div>
    </div>
  );
};
