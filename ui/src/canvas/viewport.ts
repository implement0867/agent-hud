import type { Viewport } from "~/store/ui";

export type Point = { x: number; y: number };
export type Rect = { x: number; y: number; w: number; h: number };

export const MIN_ZOOM = 0.2;
export const MAX_ZOOM = 3;

const clamp = (value: number, lo: number, hi: number) =>
  Math.min(hi, Math.max(lo, value));

export const toWorld = (v: Viewport, screen: Point): Point => ({
  x: (screen.x - v.x) / v.zoom,
  y: (screen.y - v.y) / v.zoom,
});

/** Zoom by a factor while keeping the world point under `screen` fixed. */
export const zoomAt = (
  v: Viewport,
  screen: Point,
  factor: number,
): Viewport => {
  const zoom = clamp(v.zoom * factor, MIN_ZOOM, MAX_ZOOM);
  const ratio = zoom / v.zoom;
  return {
    zoom,
    x: screen.x - (screen.x - v.x) * ratio,
    y: screen.y - (screen.y - v.y) * ratio,
  };
};

export const union = (rects: readonly Rect[]): Rect | null => {
  const [first, ...rest] = rects;
  if (first === undefined) return null;
  return rest.reduce<Rect>((acc, r) => {
    const x = Math.min(acc.x, r.x);
    const y = Math.min(acc.y, r.y);
    return {
      x,
      y,
      w: Math.max(acc.x + acc.w, r.x + r.w) - x,
      h: Math.max(acc.y + acc.h, r.y + r.h) - y,
    };
  }, first);
};

/** Viewport that shows `bounds` inside a screen of `size`, with padding, never zooming past 100%. */
export const fit = (
  bounds: Rect,
  size: { w: number; h: number },
  pad = 64,
): Viewport => {
  const zoom = clamp(
    Math.min((size.w - pad * 2) / bounds.w, (size.h - pad * 2) / bounds.h, 1),
    MIN_ZOOM,
    MAX_ZOOM,
  );
  return {
    zoom,
    x: (size.w - bounds.w * zoom) / 2 - bounds.x * zoom,
    y: (size.h - bounds.h * zoom) / 2 - bounds.y * zoom,
  };
};

/** Smallest pan that brings `rect` (world) into view; null when it is already visible. */
export const reveal = (
  v: Viewport,
  rect: Rect,
  size: { w: number; h: number },
  pad = 48,
): Viewport | null => {
  const left = rect.x * v.zoom + v.x;
  const top = rect.y * v.zoom + v.y;
  const right = left + rect.w * v.zoom;
  const bottom = top + rect.h * v.zoom;
  let dx = 0;
  let dy = 0;
  if (right > size.w - pad) dx = size.w - pad - right;
  if (left + dx < pad) dx = pad - left;
  if (bottom > size.h - pad) dy = size.h - pad - bottom;
  if (top + dy < pad) dy = pad - top;
  return dx === 0 && dy === 0 ? null : { ...v, x: v.x + dx, y: v.y + dy };
};
