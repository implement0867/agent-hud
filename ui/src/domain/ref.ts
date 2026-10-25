import { invariant } from "~/lib/invariant";

/**
 * A ref names a card by its id (plan), a part of a card by its number in the card (plan/2), or a cell of a table row by
 * the row's part number and the cell's column number (plan/2/3). This module is the one place that writes and reads them.
 */

/** The ref of the card's part with the number. */
export const partRef = (card: string, part: number) =>
  `${card}/${String(part)}`;

/** The ref of the cell in the column of the card's row, both numbered from 1. */
export const cellRef = (card: string, row: number, column: number) =>
  `${partRef(card, row)}/${String(column)}`;

/** The id of the card that the ref is on. */
export const cardOf = (ref: string) => {
  const end = ref.indexOf("/");
  return end === -1 ? ref : ref.slice(0, end);
};

/** Whether the ref names a whole card rather than a part of one. */
export const isCardRef = (ref: string) => !ref.includes("/");

/** The ref of the row that a cell is in. */
export const rowOf = (cell: string) => cell.slice(0, cell.lastIndexOf("/"));

/** A run of a text: plain, or a ref to a part of a card on the board, with its offset in the text. */
export type TRefPiece = { text: string; ref: string | null; at: number };

/**
 * The text in runs: plain text, and each ref to a part of a card on the board, such as plan/2; a cell's ref links its row.
 * A ref to a card that is not on the board stays plain.
 */
export const splitRefs = (
  text: string,
  onBoard: (card: string) => boolean,
): TRefPiece[] => {
  const pieces: TRefPiece[] = [];
  let at = 0;
  for (const match of text.matchAll(
    /\b([A-Za-z][A-Za-z0-9_-]{0,31}\/[1-9][0-9]*)(?:\/[1-9][0-9]*)?\b/g,
  )) {
    const [found, part] = match;
    invariant(part !== undefined, "the pattern captures the part's ref");
    if (match.index > at)
      pieces.push({ text: text.slice(at, match.index), ref: null, at });
    pieces.push({
      text: found,
      ref: onBoard(cardOf(part)) ? part : null,
      at: match.index,
    });
    at = match.index + found.length;
  }
  if (at < text.length) pieces.push({ text: text.slice(at), ref: null, at });
  return pieces;
};
