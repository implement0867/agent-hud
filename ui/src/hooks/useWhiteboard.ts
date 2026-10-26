import { createContext, useContext } from "react";
import { z } from "zod";

import type { TAnchor, TPoint } from "~/domain/board";
import { invariant } from "~/lib/invariant";
import type { TLook } from "~/lib/look";

export const SelectionKind = z
  .enum(["card", "thread", "draft", "arrow"])
  .describe(
    "What the user selected: a card, a thread, the words of a new thread, or an arrow",
  );

export type TSelection =
  | { kind: typeof SelectionKind.enum.card; id: string }
  | { kind: typeof SelectionKind.enum.thread; id: string }
  | { kind: typeof SelectionKind.enum.draft; anchor: TAnchor }
  | { kind: typeof SelectionKind.enum.arrow; id: string }
  | null;

/** An arrow the user draws from words of a card: it starts at the end of the words and follows the pointer to a card. */
export type TLinking = {
  from: TAnchor;
  start: TPoint;
  to: TPoint;
  /** The card under the pointer, which the arrow drops on. */
  over: string | null;
};

/**
 * The card in the editor, with what the editor needs from when it opened: the card's number of earlier versions, so
 * that a save does not replace a newer version, and the quotes of its threads and arrows, so that the editor can say
 * how many of them a change moves to the history.
 */
export type TEditing = { card: string; versions: number; quotes: string[] };

/** What the user does on the whiteboard, for the cards and panels in it. */
export type TWhiteboard = {
  selection: TSelection;
  select: (selection: TSelection) => void;
  /** Selects the card, or opens the thread on it, and moves the view to it. */
  show: (card: string, thread?: string | null) => void;
  linking: TLinking | null;
  editing: TEditing | null;
  /** Opens the card in the editor, or closes the editor on null. */
  edit: (card: string | null) => void;
  /** Opens the history of the card, or of all cards. */
  openHistory: (card: string | null) => void;
  /** Removes the card, with a toast that undoes it for a while. */
  remove: (id: string) => void;
  /** Removes the arrow, with a toast that undoes it for a while. */
  unlink: (id: string) => void;
  /** The number of comments of each thread the user has read. */
  seen: Readonly<Record<string, number>>;
  look: TLook;
};

export const WhiteboardContext = createContext<TWhiteboard | null>(null);

export const useWhiteboard = () => {
  const whiteboard = useContext(WhiteboardContext);
  invariant(whiteboard !== null, "the board renders inside the whiteboard");
  return whiteboard;
};
