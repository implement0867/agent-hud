import { createContext, useContext } from "react";
import type { PointerEvent } from "react";
import { z } from "zod";

import type { TPoint } from "~/domain/board";
import type { TRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";

export const SelectionKind = z
  .enum(["ref", "arrow"])
  .describe("What the user selected: a card or part, or an arrow");

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

/**
 * The card in the editor, with what the editor needs from when it opened: the card's number of earlier versions, so
 * that a save does not replace a newer version, and the page text of each part with feedback, so that the editor can
 * say how many of them a change moves to the history. The card's own feedback moves on any change and has text "".
 */
export type TEditing = { card: string; versions: number; marked: string[] };

/** What the user does on the whiteboard, for the cards, parts and panels in it. */
export type TWhiteboard = {
  selection: TSelection;
  /** Selects, and opens the feedback of a part unless told not to, as a click on a card's header does. */
  select: (selection: TSelection, feedback?: boolean) => void;
  /** Selects the part or card and moves the view to it. */
  show: (ref: string) => void;
  /** The part or card that the arrow being drawn starts at; the arrow's loose end moves without changing this. */
  linkingFrom: string | null;
  /** Starts an arrow from the ref; it ends on the part under the pointer when the button goes up. */
  beginLink: (from: string, event: PointerEvent) => void;
  editing: TEditing | null;
  /** Opens the card in the editor, or closes the editor on null. */
  edit: (card: string | null) => void;
  /** Opens the history of the card, or of all cards. */
  openHistory: (card: string | null) => void;
  /** Removes the card, with a toast that undoes it for a while. */
  remove: (id: string) => void;
  /** Removes the arrow, with a toast that undoes it for a while. */
  unlink: (id: string) => void;
};

export const WhiteboardContext = createContext<TWhiteboard | null>(null);

export const useWhiteboard = () => {
  const whiteboard = useContext(WhiteboardContext);
  invariant(whiteboard !== null, "the board renders inside the whiteboard");
  return whiteboard;
};

export const isSelected = (selection: TSelection, ref: string) =>
  selection?.kind === SelectionKind.enum.ref && selection.ref === ref;
