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
  place: TPoint;
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

/** The frame's place and size on the board. A card without a width is as wide as its text, up to a column. */
export const findFrameStyle = (
  mode: TFrameMode,
  { place, width, height, layer }: TFrameBox,
): CSSProperties => ({
  left: place.x,
  top: place.y,
  width: width ?? "max-content",
  height: findFrameHeight(mode, height),
  minWidth: leastCardWidth,
  maxWidth: width === null ? columnWidth : "none",
  zIndex: layer,
});

/** The classes of the frame's body, which pads the card's content and scrolls it; a folded card has no padding below its first line. */
export const findBodyClass = (mode: TFrameMode) =>
  `relative min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-card py-[var(--pad-y)] pr-11 pl-[var(--pad)] [scrollbar-color:var(--ink-ghost)_transparent] [scrollbar-width:thin] ${mode === FrameMode.enum.folded ? "" : "pb-[var(--pad)]"}`;

/** The classes around an open card's markdown; a card with earlier versions keeps its first line clear of the links to its changes. */
export const findMarkdownClass = (versions: number) =>
  `animate-pop ${versions > 0 ? "[&_.markdown>:first-child]:pr-36" : ""}`;
