import type { Element, ElementContent, Root, RootContent } from "hast";

import { ColumnKind, columnFromHeader } from "~/lib/columns";
import type { TColumn } from "~/lib/columns";

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

/**
 * A rehype plugin, after highlight, as the server's outline reads parts:
 * data-part on each list item, table body row and line of a code block is its number in the document, from 1;
 * each header cell shows its title, and each cell of an input column has data-input (row/column), data-kind and data-options.
 */
export const numberParts = () => (tree: Root) => {
  let count = 0;
  let columns: TColumn[] = [];
  const visit = (node: Root | RootContent, parent: Root | Element) => {
    if (node.type === "element" && node.tagName === "li") {
      count += 1;
      node.properties["dataPart"] = count;
    }
    if (node.type === "element" && node.tagName === "th") {
      const { title, column } = columnFromHeader(textOf(node).trim());
      columns.push(column);
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
        const column = columns[index];
        if (column === undefined || column.kind === ColumnKind.enum.static)
          return;
        cell.properties["dataInput"] = `${String(count)}/${String(index + 1)}`;
        cell.properties["dataKind"] = column.kind;
        cell.properties["dataOptions"] = column.options;
      });
    }
    if ("children" in node) {
      for (const child of node.children) visit(child, node);
    }
  };
  visit(tree, tree);
};
