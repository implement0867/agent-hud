import type { Element, Root, RootContent } from "hast";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";

/**
 * A card's text is the words it shows, without markdown. A quote names words of the text, and matches it squeezed,
 * without white space, as the server matches it, so that the page and the server agree where blocks and lines join.
 */

const parser = unified().use(remarkParse).use(remarkGfm).use(remarkRehype);

/** The markdown as the page renders it before the code is coloured: the tree of HTML elements. */
export const treeOf = (md: string): Root => parser.runSync(parser.parse(md));

/** A table cell of a box alone, [ ] or [x], which the page shows as a checkbox. */
export const boxPattern = /^\s*\[[ xX]\]\s*$/;

/** The text of an element, without what shows no words: a cell that is a checkbox, and inputs. */
export const textOf = (node: Root | RootContent): string => {
  if (node.type === "text") return node.value;
  if (node.type !== "element" && node.type !== "root") return "";
  if (node.type === "element" && isBoxCell(node)) return "";
  return node.children.map(textOf).join("");
};

/** Whether the element is a table cell that holds a box alone. */
export const isBoxCell = (node: Element) =>
  (node.tagName === "td" || node.tagName === "th") &&
  boxPattern.test(node.children.map(textOf).join(""));

/** The words of the markdown as the page shows them. */
export const plainText = (md: string) => textOf(treeOf(md));

/** The text without its white space. */
export const squeeze = (text: string) => text.replace(/\s+/g, "");

/** Where the quote starts in the text, squeezed, at each place it occurs; [0] for an empty quote. */
export const placesIn = (text: string, quote: string): number[] => {
  const squeezed = squeeze(text);
  const wanted = squeeze(quote);
  if (wanted === "") return [0];
  const found: number[] = [];
  for (
    let at = squeezed.indexOf(wanted);
    at !== -1;
    at = squeezed.indexOf(wanted, at + 1)
  )
    found.push(at);
  return found;
};

/** The quote with its white space collapsed, as a thread names it. */
export const tidy = (quote: string) => quote.replace(/\s+/g, " ").trim();

/** Whether the markdown still shows the words of the anchor. */
export const keeps = (md: string, quote: string) =>
  quote === "" || placesIn(plainText(md), quote).length > 0;

/** The first line of the text that is not blank. */
export const firstLine = (text: string) =>
  text
    .split("\n")
    .find((line) => line.trim() !== "")
    ?.trim() ?? "";

/** The first line of the markdown without its markers: the heading's text, or the first cell of a table's header. */
export const cardTitle = (md: string): string => {
  const first = firstLine(md);
  if (first.startsWith("|"))
    return (first.split("|").find((piece) => piece.trim() !== "") ?? "").trim();
  return first.replace(/^[\s#>*+-]+|^\s*\d+[.)]\s*/g, "").trim();
};

const most = 60;

/** The text cut to a length that reads in a line. */
export const short = (text: string) =>
  text.length > most ? `${text.slice(0, most - 1)}…` : text;

/** Flips the box whose markdown runs from start to end: [ ] becomes [x], and [x] becomes [ ]. */
export const toggledBox = (md: string, start: number, end: number) => {
  const found = /\[([ xX])\]/.exec(md.slice(start, end));
  if (found === null) return md;
  const at = start + found.index;
  return `${md.slice(0, at)}[${found[1] === " " ? "x" : " "}]${md.slice(at + 3)}`;
};
