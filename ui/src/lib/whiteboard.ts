import { createContext, useContext } from "react";
import type { PointerEvent } from "react";
import { z } from "zod";

import type { TBoardSocket } from "~/api/boardSocket";
import type { TRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";
import type { TBoard, TPoint } from "~/schemas/board";

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
  select: (selection: TSelection) => void;
  linking: TLinking | null;
  /** Starts an arrow from the ref; it ends on the part under the pointer when the button goes up. */
  beginLink: (from: string, event: PointerEvent) => void;
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
