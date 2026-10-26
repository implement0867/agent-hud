import type { Element, ElementContent, Root, RootContent } from "hast";
import { z } from "zod";

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
    meta.split(/\s+/).flatMap((word) => {
      const at = word.indexOf("=");
      return at === -1 ? [] : [[word.slice(0, at), word.slice(at + 1)]];
    }),
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
  const lang = plainLang ?? pre.properties["dataLang"] ?? "";
  const meta = pre.properties["dataMeta"] ?? code.data?.meta ?? "";
  return { lang: String(lang), meta: String(meta) };
};

/**
 * A rehype plugin, after the colouring: each line of a code block is a block of its own with data-code-line, which
 * starts with its number in the file, as page chrome, when the fence gives file= or start=; a line of a diff has
 * data-diff and its sign apart; the pre has data-file when the fence gives a file.
 */
export const markCodeLines = () => (tree: Root) => {
  // Shiki puts each coloured block in a root of its own, inside the tree's root.
  const visit = (node: Root | Element) => {
    for (const child of node.children) {
      const nested = child as RootContent | Root;
      if (nested.type === "root") visit(nested);
      if (child.type !== "element") continue;
      if (
        child.tagName === "code" &&
        node.type === "element" &&
        node.tagName === "pre"
      ) {
        const { lang, meta } = codeInfo(node, child);
        const options = fenceOptions(meta);
        const start = /^\d+$/.test(options["start"] ?? "")
          ? Number(options["start"])
          : 1;
        const numbered =
          options["file"] !== undefined || options["start"] !== undefined;
        if (options["file"] !== undefined)
          node.properties["dataFile"] = options["file"];
        const lines = codeLines(child);
        lines.forEach((line, index) => {
          line.properties["dataCodeLine"] = "";
          const text = textOf(line);
          const sign = text.charAt(0);
          if (lang === "diff" && (sign === "+" || sign === "-")) {
            line.properties["dataDiff"] =
              sign === "+" ? DiffKind.enum.add : DiffKind.enum.remove;
            line.children = [
              {
                type: "element",
                tagName: "span",
                properties: { dataSign: "" },
                children: [{ type: "text", value: sign }],
              },
              { type: "text", value: text.slice(1) },
            ];
          }
          if (numbered)
            line.children = [
              {
                type: "element",
                tagName: "span",
                properties: { dataChrome: "", dataLineNumber: "" },
                children: [{ type: "text", value: String(start + index) }],
              },
              ...line.children,
            ];
        });
        child.children = lines;
        continue;
      }
      visit(child);
    }
  };
  visit(tree);
};
