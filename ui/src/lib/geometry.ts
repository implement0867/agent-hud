import type { TPoint } from "~/schemas/board";

export type TView = TPoint & { scale: number };
export type TSize = { width: number; height: number };
export type TRect = TPoint & TSize;

const clampScale = (scale: number) => Math.min(3, Math.max(0.2, scale));

/** The point on the board under a point of the viewport. */
export const toBoard = (view: TView, at: TPoint): TPoint => ({
  x: (at.x - view.x) / view.scale,
  y: (at.y - view.y) / view.scale,
});

/** The view zoomed by the factor, with the board point under `at` kept in place. */
export const zoomAt = (view: TView, factor: number, at: TPoint): TView => {
  const scale = clampScale(view.scale * factor);
  const ratio = scale / view.scale;
  return {
    x: at.x - (at.x - view.x) * ratio,
    y: at.y - (at.y - view.y) * ratio,
    scale,
  };
};

/** The view at the same scale that shows the rect at the centre of the viewport. */
export const centreOn = (view: TView, rect: TRect, size: TSize): TView => ({
  scale: view.scale,
  x: size.width / 2 - (rect.x + rect.width / 2) * view.scale,
  y: size.height / 2 - (rect.y + rect.height / 2) * view.scale,
});

/** The view that shows all the rects with a margin, at most at full scale. */
export const fitAll = (rects: TRect[], size: TSize): TView => {
  const left = Math.min(...rects.map((rect) => rect.x));
  const top = Math.min(...rects.map((rect) => rect.y));
  const right = Math.max(...rects.map((rect) => rect.x + rect.width));
  const bottom = Math.max(...rects.map((rect) => rect.y + rect.height));
  const margin = 64;
  const scale = clampScale(
    Math.min(
      1,
      (size.width - 2 * margin) / (right - left),
      (size.height - 2 * margin) / (bottom - top),
    ),
  );
  return {
    scale,
    x: (size.width - (right - left) * scale) / 2 - left * scale,
    y: (size.height - (bottom - top) * scale) / 2 - top * scale,
  };
};

/** The top of the lowest free space in three columns of the width, below the rects that cross each column. */
export const freePlace = (rects: TRect[], width: number): TPoint => {
  const gap = 48;
  return [0, 1, 2]
    .map((column) => {
      const x = column * (width + gap);
      const below = rects
        .filter((rect) => rect.x < x + width && rect.x + rect.width > x)
        .map((rect) => rect.y + rect.height + gap);
      return { x, y: Math.max(0, ...below) };
    })
    .reduce((best, place) => (place.y < best.y ? place : best));
};

/** The rect of the element in board coordinates, from its rect in the viewport. */
export const rectOnBoard = (
  element: Element,
  world: Element,
  scale: number,
): TRect => {
  const rect = element.getBoundingClientRect();
  const origin = world.getBoundingClientRect();
  return {
    x: (rect.left - origin.left) / scale,
    y: (rect.top - origin.top) / scale,
    width: rect.width / scale,
    height: rect.height / scale,
  };
};

const pointAt = (t: number, points: [TPoint, TPoint, TPoint, TPoint]) => {
  const [a, b, c, d] = points;
  const u = 1 - t;
  const blend = (key: "x" | "y") =>
    u * u * u * a[key] +
    3 * u * u * t * b[key] +
    3 * u * t * t * c[key] +
    t * t * t * d[key];
  return { x: blend("x"), y: blend("y") };
};

/**
 * A curve from the side of the source card that faces the target card, at the height of the source part,
 * to a small gap before the facing side of the target card, at the height of the target part. Cards one above the other loop out to the right.
 */
export const arrowCurve = (
  from: { card: TRect; y: number },
  to: { card: TRect; y: number },
) => {
  const fromCentre = from.card.x + from.card.width / 2;
  const toCentre = to.card.x + to.card.width / 2;
  const apart = Math.abs(toCentre - fromCentre) > from.card.width / 2;
  const rightward = toCentre > fromCentre;
  const start = {
    x: apart && !rightward ? from.card.x : from.card.x + from.card.width,
    y: from.y,
  };
  const gap = 4;
  const end = {
    x: apart && rightward ? to.card.x - gap : to.card.x + to.card.width + gap,
    y: to.y,
  };
  const reach = Math.max(48, Math.abs(end.x - start.x) / 2);
  const out = apart && !rightward ? -reach : reach;
  const back = apart ? -out : reach;
  const points: [TPoint, TPoint, TPoint, TPoint] = [
    start,
    { x: start.x + out, y: start.y },
    { x: end.x + back, y: end.y },
    end,
  ];
  const [a, b, c, d] = points;
  return {
    path: `M ${String(a.x)} ${String(a.y)} C ${String(b.x)} ${String(b.y)}, ${String(c.x)} ${String(c.y)}, ${String(d.x)} ${String(d.y)}`,
    middle: pointAt(0.5, points),
  };
};

/** The card of the ref, and the height of the middle of the ref's first line, in board coordinates. */
export const endOnBoard = (
  world: Element,
  ref: string,
  scale: number,
): { card: TRect; y: number } | null => {
  const [cardId = ""] = ref.split("/");
  const card = world.querySelector(`article[data-ref="${CSS.escape(cardId)}"]`);
  const part = world.querySelector(`[data-ref="${CSS.escape(ref)}"]`);
  if (card === null || part === null) return null;
  const rect = rectOnBoard(part, world, scale);
  return {
    card: rectOnBoard(card, world, scale),
    y: rect.y + Math.min(14, rect.height / 2),
  };
};
