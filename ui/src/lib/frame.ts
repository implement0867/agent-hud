import type { CSSProperties } from "react";
import { z } from "zod";

import type { TPoint } from "~/domain/board";
import { assertNever } from "~/lib/assertNever";
import { columnWidth, leastCardWidth } from "~/lib/geometry";

/** What a card's frame shows: the card open, folded to its first line, or the editor of its markdown. */
export const FrameMode = z.enum(["open", "folded", "editing"]);

export type TFrameMode = z.infer<typeof FrameMode>;

/** The frame's mode: the editor while it is open on the card, over the card's fold. */
export const findFrameMode = (
  editing: boolean,
  folded: boolean,
): TFrameMode => {
  if (editing) return FrameMode.enum.editing;
  return folded ? FrameMode.enum.folded : FrameMode.enum.open;
};

type TFrameBox = {
  place: TPoint | null;
  width: number | null;
  height: number | null;
  layer: number;
};

/** The height of the frame: an open card's own, while the editor shows the whole markdown and a folded card its first line. */
const findFrameHeight = (mode: TFrameMode, height: number | null) => {
  switch (mode) {
    case FrameMode.enum.open:
      return height ?? "auto";
    case FrameMode.enum.folded:
    case FrameMode.enum.editing:
      return "auto";
    default:
      return assertNever(mode);
  }
};

/**
 * The frame's place and size on the board. A card without a width is as wide as its text, up to a column, and a card
 * without a place is hidden until the page gives it one.
 */
export const findFrameStyle = (
  mode: TFrameMode,
  { place, width, height, layer }: TFrameBox,
): CSSProperties => ({
  left: place?.x ?? 0,
  top: place?.y ?? 0,
  width: width ?? "max-content",
  height: findFrameHeight(mode, height),
  minWidth: leastCardWidth,
  maxWidth: width === null ? columnWidth : "none",
  zIndex: layer,
  visibility: place === null ? "hidden" : "visible",
});
