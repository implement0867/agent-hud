import { createContext, useContext } from "react";
import type { PointerEvent } from "react";
import { z } from "zod";

import type { TBoardSocket } from "~/api/boardSocket";
import type { TRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";
import type { TBoard, TPoint, TVersion } from "~/schemas/board";

export type TAct = TBoardSocket["act"];

export const SelectionKind = z.enum(["ref", "arrow"]);

export type TSelection =
  | { kind: typeof SelectionKind.enum.ref; ref: string }
  | { kind: typeof SelectionKind.enum.arrow; id: string }
  | null;

/** An arrow the user drags from a part, with its loose end at a point of the board. */
export type TLinking = {
  from: string;
  start: { card: TRect; y: number };
  to: TPoint;
};

export type TTools = {
  board: TBoard;
  act: TAct;
  selection: TSelection;
  /** Selects, and opens the feedback of a part unless told not to, as a click on a card's header does. */
  select: (selection: TSelection, feedback?: boolean) => void;
  /** Selects the part or card and moves the view to it. */
  show: (ref: string) => void;
  linking: TLinking | null;
  /** Starts an arrow from the ref; it ends on the part under the pointer when the button goes up. */
  beginLink: (from: string, event: PointerEvent) => void;
  /** Opens the history of the card, or of all cards. */
  openHistory: (card: string | null) => void;
  /** Removes the card, with a toast that undoes it for a while. */
  remove: (id: string) => void;
  /** Removes the arrow, with a toast that undoes it for a while. */
  unlink: (id: string) => void;
  /** An earlier version of a card shows its feedback, and takes no actions. */
  readOnly: boolean;
};

export const ToolContext = createContext<TTools | null>(null);

export const useTools = () => {
  const tools = useContext(ToolContext);
  invariant(tools !== null, "the board renders inside the whiteboard");
  return tools;
};

export const CardContext = createContext<string | null>(null);

/** The id of the card that the part renders in. */
export const useCardId = () => {
  const id = useContext(CardContext);
  invariant(id !== null, "parts render inside a card");
  return id;
};

export const isSelected = (selection: TSelection, ref: string) =>
  selection?.kind === SelectionKind.enum.ref && selection.ref === ref;

/** An id for a card or an arrow that the user makes. */
export const newId = (prefix: string) =>
  `${prefix}-${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`;

/** The tools for an earlier version of a card: its feedback on the board, and no actions. */
export const readOnlyTools = (tools: TTools, version: TVersion): TTools => ({
  ...tools,
  board: { ...tools.board, threads: version.threads, values: version.values },
  act: () => Promise.resolve(false),
  selection: null,
  select: () => undefined,
  linking: null,
  beginLink: () => undefined,
  remove: () => undefined,
  unlink: () => undefined,
  readOnly: true,
});

const refPattern = /\b[A-Za-z][A-Za-z0-9_-]{0,31}(?:\/[1-9][0-9]*){1,2}\b/;

/** The text in pieces, each with its offset: plain text, and each ref to a part of a card on the board, such as plan/2; a cell's ref names its row. */
export const splitRefs = (
  text: string,
  board: TBoard,
): { text: string; ref: string | null; at: number }[] => {
  const pieces = text.split(new RegExp(`(${refPattern.source})`));
  const offsets = pieces.map((_, index) =>
    pieces.slice(0, index).reduce((sum, piece) => sum + piece.length, 0),
  );
  return pieces.flatMap((piece, index) => {
    if (piece === "") return [];
    const [card = "", part = ""] = piece.split("/");
    const ref =
      index % 2 === 1 && Object.hasOwn(board.cards, card)
        ? `${card}/${part}`
        : null;
    return [{ text: piece, ref, at: offsets[index] ?? 0 }];
  });
};
