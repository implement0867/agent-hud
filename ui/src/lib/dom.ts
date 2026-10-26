import type { TAnchor, TPoint } from "~/domain/board";
import { rangeOf } from "~/lib/anchor";
import type { TRect } from "~/lib/geometry";

/**
 * Measurements of the board's elements: each card is an article with data-card, and its words are in its text root.
 * The world is the element that the view translates and scales; its transform converts between the viewport and board
 * coordinates.
 */

/** The element of the card on the board, or null when it is not there. */
export const cardElement = (world: Element, card: string) =>
  world.querySelector(`article[data-card="${CSS.escape(card)}"]`);

/** The element that holds the card's words, or null. */
export const textRoot = (world: Element, card: string) =>
  cardElement(world, card)?.querySelector("[data-text-root]") ?? null;

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

/** The rect of the client rect in board coordinates. */
export const clientOnBoard = (rect: DOMRect, world: Element): TRect => {
  const origin = world.getBoundingClientRect();
  const scale = scaleOf(world);
  return {
    x: (rect.left - origin.left) / scale,
    y: (rect.top - origin.top) / scale,
    width: rect.width / scale,
    height: rect.height / scale,
  };
};

/** The rect of the element in board coordinates. */
export const rectOnBoard = (element: Element, world: Element): TRect =>
  clientOnBoard(element.getBoundingClientRect(), world);

/** The range of the anchor's words on the page, or null when its card or its words are not there. */
export const anchorRange = (world: Element, anchor: TAnchor) => {
  const root = textRoot(world, anchor.card);
  return root === null || anchor.quote === ""
    ? null
    : rangeOf(root, anchor.quote, anchor.occurrence);
};

/**
 * Where an arrow from the anchor starts, in board coordinates: at the end of its words, half way up their last line,
 * or at the right of the card's first line for the card as a whole; and the card's rect. Null when the card is not there.
 */
export const arrowStart = (
  world: Element,
  anchor: TAnchor,
): { card: TRect; at: TPoint } | null => {
  const element = cardElement(world, anchor.card);
  if (element === null) return null;
  const card = rectOnBoard(element, world);
  const last = [...(anchorRange(world, anchor)?.getClientRects() ?? [])].at(-1);
  if (last === undefined)
    return { card, at: { x: card.x + card.width, y: card.y + 24 } };
  const rect = clientOnBoard(last, world);
  return {
    card,
    at: { x: rect.x + rect.width + 2, y: rect.y + rect.height / 2 },
  };
};

/** The id of the card under the point of the screen, or null. */
export const cardAt = (client: { clientX: number; clientY: number }) =>
  document
    .elementFromPoint(client.clientX, client.clientY)
    ?.closest("article[data-card]")
    ?.getAttribute("data-card") ?? null;
