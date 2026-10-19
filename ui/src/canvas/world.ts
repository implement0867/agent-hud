import { createContext, useContext } from "react";
import type { RefObject } from "react";

import type { Rect } from "~/canvas/viewport";
import type { AnchorRef } from "~/protocol/schema";
import { anchorKey } from "~/store/ui";

export type World = {
  /** Full-screen element that receives pointer and wheel input. */
  containerRef: RefObject<HTMLDivElement | null>;
  /** Transformed layer; children are positioned in world units. */
  layerRef: RefObject<HTMLDivElement | null>;
};

export const WorldContext = createContext<World | null>(null);

export const useWorld = (): World => {
  const world = useContext(WorldContext);
  if (world === null)
    throw new Error("useWorld must be used inside WorldContext");
  return world;
};

/** A card's box in world units, read from layout (unaffected by zoom). */
export const cardRect = (node: HTMLElement): Rect => ({
  x: node.offsetLeft,
  y: node.offsetTop,
  w: node.offsetWidth,
  h: node.offsetHeight,
});

export const cardNode = (layer: HTMLElement, id: string): HTMLElement | null =>
  layer.querySelector<HTMLElement>(`[data-card="${CSS.escape(id)}"]`);

export const anchorNode = (
  layer: HTMLElement,
  ref: AnchorRef,
): HTMLElement | null =>
  layer.querySelector<HTMLElement>(
    `[data-anchor="${CSS.escape(anchorKey(ref.id, ref.anchor))}"]`,
  );

/** Any node's box in world units, from its on-screen box. */
export const worldRect = (
  layer: HTMLElement,
  node: HTMLElement,
  zoom: number,
): Rect => {
  const base = layer.getBoundingClientRect();
  const r = node.getBoundingClientRect();
  return {
    x: (r.left - base.left) / zoom,
    y: (r.top - base.top) / zoom,
    w: r.width / zoom,
    h: r.height / zoom,
  };
};

export const allCardRects = (layer: HTMLElement): Rect[] =>
  Array.from(
    layer.querySelectorAll<HTMLElement>("[data-card]:not([data-unplaced])"),
    cardRect,
  );

/**
 * Where an arrow attaches to an anchor: the anchor's height on its card's edges.
 * Arrows then stay outside cards and never cover card content.
 */
export const arrowRect = (
  layer: HTMLElement,
  node: HTMLElement,
  zoom: number,
): Rect => {
  const anchor = worldRect(layer, node, zoom);
  const card = node.closest<HTMLElement>("[data-card]");
  if (card === null) return anchor;
  const box = cardRect(card);
  return { x: box.x, w: box.w, y: anchor.y, h: anchor.h };
};
