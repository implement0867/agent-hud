/**
 * The page's text highlights, which paint marks on words without changing the elements React renders: the words of
 * each thread, the words each arrow starts at, and the words of a thread being written. Each card keeps its ranges
 * under its id, and each kind is one highlight of all the cards' ranges.
 */
export type THighlightKind = "thread" | "arrow" | "quote";

const kept: Record<THighlightKind, Map<string, Range[]>> = {
  thread: new Map(),
  arrow: new Map(),
  quote: new Map(),
};

/** Sets the ranges of the kind that the owner marks; no ranges takes the owner's marks away. */
export const markRanges = (
  kind: THighlightKind,
  owner: string,
  ranges: Range[],
) => {
  if (ranges.length === 0) kept[kind].delete(owner);
  else kept[kind].set(owner, ranges);
  // A browser without the highlight API shows the bubbles and the arrows, without the marks on the words.
  if (typeof CSS === "undefined" || !("highlights" in CSS)) return;
  CSS.highlights.set(kind, new Highlight(...[...kept[kind].values()].flat()));
};
