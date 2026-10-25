import type { Root, RootContent } from "hast";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";

import type { TBoard } from "~/domain/board";
import { columnFromHeader } from "~/domain/columns";
import { cardOf, isCardRef, rowOf } from "~/domain/ref";
import { numberParts } from "~/lib/numberParts";

/** The text of the node; a table row's cells joined with " | ", as the server's outline joins them. */
const textOf = (node: Root | RootContent): string =>
  node.type === "text"
    ? node.value
    : node.type === "element" && node.tagName === "tr"
      ? node.children
          .filter((cell) => cell.type === "element")
          .map((cell) => textOf(cell).trim())
          .join(" | ")
      : "children" in node
        ? node.children.map(textOf).join("")
        : "";

const parser = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkRehype)
  .use(numberParts);

/** The text of each part of the markdown, in order, as numberParts numbers them from 1, and as the page shows them. */
export const partTexts = (md: string): string[] => {
  const tree = parser.runSync(parser.parse(md));
  const texts: string[] = [];
  const visit = (node: Root | RootContent) => {
    if (
      node.type === "element" &&
      typeof node.properties["dataPart"] === "number"
    )
      texts[node.properties["dataPart"] - 1] =
        node.tagName === "tr" ? textOf(node) : textOf(node).trim();
    if ("children" in node) for (const child of node.children) visit(child);
  };
  visit(tree);
  return texts;
};

/** What a new version of a card changed, for the page to mark: the numbers of the parts whose text is new, and the texts that went. */
export type TChanges = { parts: number[]; removed: string[] };

/** The parts of the new version that the old one did not have, by number, and the old version's texts that the new one does not have. */
export const changesBetween = (before: string, after: string): TChanges => {
  const was = partTexts(before);
  const is = partTexts(after);
  return {
    parts: is.flatMap((text, index) => (was.includes(text) ? [] : [index + 1])),
    removed: was.filter((text) => !is.includes(text)),
  };
};

/** The first line of the text that is not blank. */
export const firstLine = (text: string) =>
  text
    .split("\n")
    .find((line) => line.trim() !== "")
    ?.trim() ?? "";

/** The first line of the markdown without its markers: the first cell of a table's header, or the heading's text. */
export const cardTitle = (md: string): string => {
  const first = firstLine(md);
  if (first.startsWith("|")) {
    const cell = first.split("|").find((piece) => piece.trim() !== "") ?? "";
    return columnFromHeader(cell.trim()).title;
  }
  return first.replace(/^[\s#>*+-]+|^\s*\d+[.)]\s*/g, "").trim();
};

/** The titles of a table card's columns, from its header row; empty for a card without a table. */
export const columnsOf = (md: string): string[] => {
  const header = md.split("\n").find((line) => line.trim().startsWith("|"));
  return header === undefined
    ? []
    : header
        .split("|")
        .slice(1, -1)
        .map((cell) => columnFromHeader(cell.trim()).title);
};

/** The first cell of a table row's text, as the server joins the cells with " | ". */
export const rowName = (text: string) => text.split("|")[0]?.trim() ?? text;

const most = 60;

const short = (text: string) =>
  text.length > most ? `${text.slice(0, most - 1)}…` : text;

/**
 * How the page names the ref to the user, who reads text, not refs: a card by its title, a part by its text, a table
 * row by its first cell, and a cell by its row and column; the ref itself when the card is not on the board.
 */
export const nameOf = (board: TBoard, ref: string): string => {
  const md = board.cards[cardOf(ref)]?.md;
  if (md === undefined) return ref;
  if (isCardRef(ref)) return cardTitle(md) || ref;
  const row = rowOf(ref);
  const part = isCardRef(row) ? ref : row;
  const number = Number(part.slice(part.lastIndexOf("/") + 1));
  const text = partTexts(md)[number - 1];
  if (text === undefined) return ref;
  const name = short(rowName(text));
  if (part === ref) return name;
  const column = Number(ref.slice(ref.lastIndexOf("/") + 1));
  const title = columnsOf(md)[column - 1] ?? "";
  return title === "" ? name : `${name}: ${title}`;
};
