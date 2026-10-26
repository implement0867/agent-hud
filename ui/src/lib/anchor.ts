import { placesIn, squeeze, tidy } from "~/domain/text";

/**
 * The words of a card on the page, and the places of quotes in them. A card's text root holds its rendered markdown;
 * what the page adds to it, such as a code line's number or the words a change removed, carries data-chrome and is
 * no part of the text. Positions count the text squeezed, without white space, as quotes match it.
 */

/** Each character of the text that is not white space, at its node and offset. */
type TIndex = { squeezed: string; at: { node: Text; offset: number }[] };

const indexOf = (root: Element): TIndex => {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.parentElement?.closest("[data-chrome]") == null
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT,
  });
  const at: TIndex["at"] = [];
  let squeezed = "";
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    const text = node as Text;
    const value = text.data;
    for (let offset = 0; offset < value.length; offset += 1) {
      const char = value.charAt(offset);
      if (/\s/.test(char)) continue;
      squeezed += char;
      at.push({ node: text, offset });
    }
  }
  return { squeezed, at };
};

/** The range of the quote at its occurrence in the card's text, or null when the text does not have it there. */
export const rangeOf = (
  root: Element,
  quote: string,
  occurrence: number,
): Range | null => {
  const index = indexOf(root);
  const wanted = squeeze(quote);
  if (wanted === "") return null;
  const starts = placesIn(index.squeezed, wanted);
  const start = starts[Math.min(occurrence, starts.length - 1)];
  if (start === undefined) return null;
  const first = index.at[start];
  const last = index.at[start + wanted.length - 1];
  if (first === undefined || last === undefined) return null;
  const range = document.createRange();
  range.setStart(first.node, first.offset);
  range.setEnd(last.node, last.offset + 1);
  return range;
};

/** The block that a text node is in, where the words of a quote break with a space. */
const blockOf = (node: Node) =>
  node.parentElement?.closest(
    "p, li, h1, h2, h3, h4, h5, h6, td, th, [data-line], pre, blockquote",
  ) ?? null;

/** The words of the selection in the card, and which place of them it is; null when it holds no words of the card. */
export const anchorOfRange = (
  root: Element,
  range: Range,
): { quote: string; occurrence: number } | null => {
  const index = indexOf(root);
  const inside = index.at.flatMap((at, position) =>
    range.comparePoint(at.node, at.offset) === 0 &&
    !(range.endContainer === at.node && range.endOffset === at.offset)
      ? [position]
      : [],
  );
  const start = inside[0];
  const end = inside.at(-1);
  if (start === undefined || end === undefined) return null;
  const wanted = index.squeezed.slice(start, end + 1);
  const occurrence = placesIn(index.squeezed, wanted).indexOf(start);
  // The words as they show, a space between blocks, without the page's own text.
  let quote = "";
  let block: Element | null = null;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node.parentElement?.closest("[data-chrome]") != null) continue;
    if (!range.intersectsNode(node)) continue;
    const text = node as Text;
    const from = text === range.startContainer ? range.startOffset : 0;
    const to = text === range.endContainer ? range.endOffset : text.length;
    const within = blockOf(text);
    quote += `${within === block ? "" : " "}${text.data.slice(from, to)}`;
    block = within;
  }
  return occurrence === -1 ? null : { quote: tidy(quote), occurrence };
};
