import type { TPoint } from "~/domain/board";
import { cardOf, isCardRef } from "~/domain/ref";
import type { TRect, TSize } from "~/lib/geometry";

/**
 * Measurements of the board's elements, by the data-ref that each card (article) and part carries. The world is the
 * element that the view translates and scales; its transform converts between the viewport and board coordinates.
 */

/** The element of the card or part on the board, or null when it is not there. */
export const elementOf = (world: Element, ref: string) =>
  world.querySelector(
    `${isCardRef(ref) ? "article" : ""}[data-ref="${CSS.escape(ref)}"]`,
  );

/** The scale that the view shows the world at. */
const scaleOf = (world: Element) =>
  new DOMMatrixReadOnly(getComputedStyle(world).transform).a;

/** The point of the board under a point of the screen. */
export const pointOnBoard = (
  world: Element,
  client: { clientX: number; clientY: number },
): TPoint => {
  const origin = world.getBoundingClientRect();
  const scale = scaleOf(world);
  return {
    x: (client.clientX - origin.left) / scale,
    y: (client.clientY - origin.top) / scale,
  };
};

/** The rect of the element in board coordinates. */
export const rectOnBoard = (element: Element, world: Element): TRect => {
  const rect = element.getBoundingClientRect();
  const origin = world.getBoundingClientRect();
  const scale = scaleOf(world);
  return {
    x: (rect.left - origin.left) / scale,
    y: (rect.top - origin.top) / scale,
    width: rect.width / scale,
    height: rect.height / scale,
  };
};

/** The rect of the ref's card, and the height of the middle of the ref's first line, in board coordinates. */
export const endOnBoard = (
  world: Element,
  ref: string,
): { card: TRect; y: number } | null => {
  const card = elementOf(world, cardOf(ref));
  const part = elementOf(world, ref);
  if (card === null || part === null) return null;
  const rect = rectOnBoard(part, world);
  return {
    card: rectOnBoard(card, world),
    y: rect.y + Math.min(14, rect.height / 2),
  };
};

/** Where a part is in its card, and the card's size, in board units, so that what goes beside the part follows the card. */
export type TAnchor = { card: TSize; part: TRect };

/** The anchor of the ref, measured from the page, or null when the ref is not on the board. */
export const anchorOf = (world: Element, ref: string): TAnchor | null => {
  const card = elementOf(world, cardOf(ref));
  const part = elementOf(world, ref);
  if (card === null || part === null) return null;
  const cardRect = rectOnBoard(card, world);
  const partRect = rectOnBoard(part, world);
  return {
    card: { width: cardRect.width, height: cardRect.height },
    part: {
      ...partRect,
      x: partRect.x - cardRect.x,
      y: partRect.y - cardRect.y,
    },
  };
};

/** The text that the page shows for the ref, or "" when the ref is not on the board. */
export const textOf = (world: Element, ref: string) =>
  elementOf(world, ref)?.textContent ?? "";

/** The ref of the card or part under the point of the screen, or null. */
export const refAt = (client: { clientX: number; clientY: number }) =>
  document
    .elementFromPoint(client.clientX, client.clientY)
    ?.closest("[data-ref]")
    ?.getAttribute("data-ref") ?? null;
