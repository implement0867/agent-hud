import { useCallback, useEffect, useMemo, useRef } from "react";

import { arrowBetween, labelBox, separate } from "~/canvas/geometry";
import { anchorNode, arrowRect, useWorld } from "~/canvas/world";
import { useStore } from "~/lib/store";
import type { LinkEl } from "~/protocol/schema";
import { boardStore } from "~/store/board";
import { uiStore } from "~/store/ui";

export type Part = "line" | "hit" | "text";
export type Register = (
  id: string,
  part: Part,
  node: SVGElement | null,
) => void;

export type LinkLayer = { links: readonly LinkEl[]; register: Register };

/**
 * Arrows between anchors. Anchor boxes come from layout, so a frame loop re-measures them
 * and writes path data straight to the DOM instead of re-rendering React. Paths draw under
 * the cards and texts over them; both register their nodes here.
 */
export const useLinkLayer = (): LinkLayer => {
  const order = useStore(boardStore, (s) => s.order);
  const elements = useStore(boardStore, (s) => s.elements);
  const { layerRef } = useWorld();
  const nodes = useRef(new Map<string, Map<Part, SVGElement>>());
  const links = useMemo(
    () =>
      order.flatMap((id) => {
        const el = elements[id];
        return el?.kind === "link" ? [el] : [];
      }),
    [order, elements],
  );

  const register = useCallback<Register>((id, part, node) => {
    const entry = nodes.current.get(id) ?? new Map<Part, SVGElement>();
    if (node === null) entry.delete(part);
    else entry.set(part, node);
    nodes.current.set(id, entry);
  }, []);

  useEffect(() => {
    if (links.length === 0) return;
    let frame = 0;
    const draw = () => {
      const root = layerRef.current;
      const { zoom } = uiStore.get().viewport;
      if (root !== null) {
        const drawn = links.flatMap((link) => {
          const parts = nodes.current.get(link.id);
          const a = anchorNode(root, link.src);
          const b = anchorNode(root, link.dst);
          if (parts === undefined || a === null || b === null) return [];
          const arrow = arrowBetween(
            arrowRect(root, a, zoom),
            arrowRect(root, b, zoom),
          );
          const text = parts.get("text");
          const width =
            text instanceof SVGTextElement ? text.getComputedTextLength() : 0;
          return [{ parts, arrow, text, box: labelBox(arrow.label, width) }];
        });
        const boxes = separate(drawn.map((item) => item.box));
        drawn.forEach(({ parts, arrow, text, box }, i) => {
          if (parts.get("line")?.getAttribute("d") !== arrow.d) {
            parts.get("line")?.setAttribute("d", arrow.d);
            parts.get("hit")?.setAttribute("d", arrow.d);
          }
          const y = String(arrow.label.y + (boxes[i]?.y ?? box.y) - box.y);
          if (text !== undefined && text.getAttribute("y") !== y) {
            text.setAttribute("x", String(arrow.label.x));
            text.setAttribute("y", y);
            text.setAttribute("text-anchor", arrow.label.align);
          }
        });
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [links, layerRef]);

  return useMemo(() => ({ links, register }), [links, register]);
};
