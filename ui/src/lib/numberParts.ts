import type { Element, ElementContent, Root, RootContent } from "hast";
import { z } from "zod";

import { ColumnKind, InputKind, columnFromHeader } from "~/domain/columns";
import type { TColumn, TInputKind } from "~/domain/columns";

/** The mark of a line of a diff: added or removed. */
export const DiffKind = z.enum(["add", "remove"]);

const textOf = (node: Root | RootContent): string =>
  node.type === "text"
    ? node.value
    : "children" in node
      ? node.children.map(textOf).join("")
      : "";

const elements = (nodes: ElementContent[]) =>
  nodes.filter((node): node is Element => node.type === "element");

/** The lines of a code block: Shiki's line spans, or spans of the plain text, which ends in one newline as Shiki strips. */
const codeLines = (code: Element): Element[] => {
  const lines = elements(code.children);
  return lines.length > 0
    ? lines
    : textOf(code)
        .replace(/\n$/, "")
        .split("\n")
        .map((line) => ({
          type: "element",
          tagName: "span",
          properties: {},
          children: line === "" ? [] : [{ type: "text", value: line }],
        }));
};

/** The key=value words after the language of a fenced code block, such as file=src/app.py start=40. */
const fenceOptions = (meta: string): Record<string, string> =>
  Object.fromEntries(
    meta
      .split(/\s+/)
      .flatMap((word) =>
        word.includes("=")
          ? [
              [
                word.slice(0, word.indexOf("=")),
                word.slice(word.indexOf("=") + 1),
              ],
            ]
          : [],
      ),
  );

/** The language and the info after it of a code block, from Shiki's pre or from the plain code element. */
const codeInfo = (pre: Element, code: Element) => {
  const className = code.properties.className;
  const plainLang = Array.isArray(className)
    ? className
        .map(String)
        .find((name) => name.startsWith("language-"))
        ?.slice("language-".length)
    : undefined;
  const lang = pre.properties["dataLang"] ?? plainLang ?? "";
  const meta = pre.properties["dataMeta"] ?? code.data?.meta ?? "";
  return { lang: String(lang), meta: String(meta) };
};

/** Data for the lines of a code block: the line numbers when the fence has a file or a first line, and the diff marks of a diff. */
const markLines = (pre: Element, code: Element, lines: Element[]) => {
  const { lang, meta } = codeInfo(pre, code);
  const options = fenceOptions(meta);
  const start = /^\d+$/.test(options["start"] ?? "")
    ? Number(options["start"])
    : 1;
  if (options["file"] !== undefined)
    pre.properties["dataFile"] = options["file"];
  lines.forEach((line, index) => {
    if (options["file"] !== undefined || options["start"] !== undefined)
      line.properties["dataLine"] = start + index;
    const first = textOf(line).charAt(0);
    if (lang === "diff" && (first === "+" || first === "-"))
      line.properties["dataDiff"] =
        first === "+" ? DiffKind.enum.add : DiffKind.enum.remove;
  });
};

/**
 * A rehype plugin, after highlight, as the server's outline reads parts:
 * data-part on each heading, paragraph outside a list item, list item, table body row and line of a code block is its
 * number in the document, from 1;
 * a code line has data-line, its number in the file, when its fence has file= or start=, and data-diff in a diff;
 * each header cell shows its title, and each cell of an input column has data-row, data-column, data-kind and data-options,
 * which inputOf reads back.
 */
export const numberParts = () => (tree: Root) => {
  let count = 0;
  let columns: { title: string; column: TColumn }[] = [];
  const visit = (node: Root | RootContent, parent: Root | Element) => {
    if (
      node.type === "element" &&
      (/^h[1-6]$/.test(node.tagName) ||
        node.tagName === "li" ||
        (node.tagName === "p" &&
          !(parent.type === "element" && parent.tagName === "li")))
    ) {
      count += 1;
      node.properties["dataPart"] = count;
    }
    if (node.type === "element" && node.tagName === "th") {
      const { title, column } = columnFromHeader(textOf(node).trim());
      columns.push({ title, column });
      node.children = [{ type: "text", value: title }];
    }
    if (node.type === "element" && node.tagName === "thead") columns = [];
    if (
      node.type === "element" &&
      node.tagName === "code" &&
      parent.type === "element" &&
      parent.tagName === "pre"
    ) {
      const lines = codeLines(node);
      node.children = lines;
      markLines(parent, node, lines);
      for (const line of lines) {
        count += 1;
        line.properties["dataPart"] = count;
      }
    }
    if (
      node.type === "element" &&
      node.tagName === "tr" &&
      parent.type === "element" &&
      parent.tagName === "tbody"
    ) {
      count += 1;
      node.properties["dataPart"] = count;
      elements(node.children).forEach((cell, index) => {
        const found = columns[index];
        if (found === undefined || found.column.kind === ColumnKind.enum.static)
          return;
        cell.properties["dataRow"] = count;
        cell.properties["dataColumn"] = index + 1;
        cell.properties["dataTitle"] = found.title;
        cell.properties["dataKind"] = found.column.kind;
        cell.properties["dataOptions"] = found.column.options;
      });
    }
    if ("children" in node) {
      for (const child of node.children) visit(child, node);
    }
  };
  visit(tree, tree);
};

const inputSchema = z.object({
  dataRow: z.number().int().positive(),
  dataColumn: z.number().int().positive(),
  dataTitle: z.string(),
  dataKind: InputKind,
  dataOptions: z.array(z.string()),
});

/** The number that numberParts gave the part, or null for an element that is not a part. */
export const partNumberOf = (node: Element | undefined): number | null => {
  const number = node?.properties["dataPart"];
  return typeof number === "number" ? number : null;
};

/** The input of a cell in an input column: the row's part number, the column's number from 1 and its title, the kind and the options. */
export type TInput = {
  row: number;
  column: number;
  title: string;
  kind: TInputKind;
  options: string[];
};

/** The input that numberParts gave the cell, or null for a cell of a column of text. */
export const inputOf = (cell: Element): TInput | null => {
  if (cell.properties["dataKind"] === undefined) return null;
  const { dataRow, dataColumn, dataTitle, dataKind, dataOptions } =
    inputSchema.parse(cell.properties);
  return {
    row: dataRow,
    column: dataColumn,
    title: dataTitle,
    kind: dataKind,
    options: dataOptions,
  };
};
