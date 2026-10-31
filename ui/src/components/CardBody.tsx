import type { Element, Root } from "hast";
import { createContext, memo, useContext } from "react";
import type { ComponentProps, ReactNode, SyntheticEvent } from "react";
import Markdown, { MarkdownHooks } from "react-markdown";
import type { ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Pluggable, PluggableList } from "unified";

import { FoldButton } from "~/components/FoldButton";
import { isBoxCell } from "~/domain/text";
import { showChanges } from "~/lib/changes";
import type { TDiffStyle } from "~/lib/changes";
import { DiffKind, markCodeLines } from "~/lib/codeLines";
import { highlight } from "~/lib/highlight";
import { wrapSections } from "~/lib/sections";

/** Flips the box of a task item or a table cell, whose markdown runs from start to end; none for an earlier version. */
type TToggle = ((start: number, end: number) => void) | null;

const ToggleContext = createContext<TToggle>(null);

/**
 * The folds of an open card: the label of the card's own fold, its toggle, the keys of the folded sections and the
 * toggle of a section by its key; none where the card does not fold.
 */
type TCardFolds = {
  label: string;
  toggleCard: () => void;
  sections: readonly string[];
  toggle: (section: string) => void;
} | null;

const FoldContext = createContext<TCardFolds>(null);

const stop = (event: SyntheticEvent) => {
  event.stopPropagation();
};

/**
 * A rehype plugin, before the colouring, while the elements have their places in the markdown: a task item's box and
 * a table cell of a box alone get the range of their markdown, for a click to flip the box.
 */
const markBoxes = () => (tree: Root) => {
  const visit = (node: Root | Element) => {
    for (const child of node.children) {
      if (child.type !== "element") continue;
      const place = child.position;
      if (place?.start.offset !== undefined && place.end.offset !== undefined) {
        const range = {
          dataStart: place.start.offset,
          dataEnd: place.end.offset,
        };
        if (isBoxCell(child))
          Object.assign(child.properties, range, { dataBox: "" });
        if (child.tagName === "li")
          for (const box of child.children)
            if (box.type === "element" && box.tagName === "input")
              Object.assign(box.properties, range);
        if (child.tagName === "li")
          for (const p of child.children)
            if (p.type === "element" && p.tagName === "p")
              for (const box of p.children)
                if (box.type === "element" && box.tagName === "input")
                  Object.assign(box.properties, range);
      }
      visit(child);
    }
  };
  visit(tree);
};

const rangeOf = (node: Element | undefined) => {
  const start = node?.properties["dataStart"];
  const end = node?.properties["dataEnd"];
  return typeof start === "number" && typeof end === "number"
    ? { start, end }
    : null;
};

type TBoxProps = {
  checked: boolean;
  range: { start: number; end: number } | null;
  label: string;
};

/** A box of the markdown as a checkbox; a click flips it in the markdown, which the agent gets as an edit. */
const Box = ({ checked, range, label }: TBoxProps) => {
  const toggle = useContext(ToggleContext);
  return (
    <input
      type="checkbox"
      aria-label={label}
      checked={checked}
      disabled={toggle === null || range === null}
      onPointerDown={stop}
      onClick={stop}
      onChange={() => {
        if (toggle !== null && range !== null) toggle(range.start, range.end);
      }}
    />
  );
};

const Input = ({ node, checked }: ComponentProps<"input"> & ExtraProps) => (
  <Box checked={checked === true} range={rangeOf(node)} label="Done" />
);

const textIn = (node: Element | undefined): string =>
  node === undefined
    ? ""
    : node.children
        .map((child) =>
          child.type === "text"
            ? child.value
            : child.type === "element"
              ? textIn(child)
              : "",
        )
        .join("");

/** A cell of a box alone shows a checkbox, and an empty cell a dash. */
const Cell = ({ node, children }: ComponentProps<"td"> & ExtraProps) => {
  if (node?.properties["dataBox"] !== undefined)
    return (
      <td className="w-6">
        <Box
          checked={/x/i.test(textIn(node))}
          range={rangeOf(node)}
          label="Done"
        />
      </td>
    );
  return (
    <td>
      {textIn(node).trim() === "" ? (
        <span data-chrome="" className="text-ink-ghost">
          —
        </span>
      ) : (
        children
      )}
    </td>
  );
};

/** A header cell over a column of boxes has no title. */
const HeaderCell = ({ node, children }: ComponentProps<"th"> & ExtraProps) =>
  node?.properties["dataBox"] !== undefined ? (
    <th className="w-6" />
  ) : (
    <th>{children}</th>
  );

const diffTones: Record<string, string> = {
  [DiffKind.enum.add]: "bg-ins-bg",
  [DiffKind.enum.remove]: "bg-del-bg",
};

/** A line of code, a row of the block that does not wrap: its number when the fence gives a file or a first line, and a tint in a diff. */
const Span = ({
  node,
  children,
  className,
  style,
}: ComponentProps<"span"> & ExtraProps) => {
  if (node?.properties["dataCodeLine"] !== undefined) {
    const diff = node.properties["dataDiff"];
    return (
      <span
        data-code-line=""
        data-diff={typeof diff === "string" ? diff : undefined}
        className={`block min-h-[1lh] px-3 whitespace-pre ${typeof diff === "string" ? (diffTones[diff] ?? "") : ""}`}
      >
        {children}
      </span>
    );
  }
  if (node?.properties["dataLineNumber"] !== undefined)
    return (
      <span
        data-chrome=""
        className="mr-3 inline-block w-7 text-right text-ink-ghost select-none"
      >
        {children}
      </span>
    );
  if (node?.properties["dataSign"] !== undefined) {
    const add = textIn(node) === "+";
    return (
      <span className={add ? "text-success-strong" : "text-danger-strong"}>
        {children}
      </span>
    );
  }
  return (
    <span className={className} style={style}>
      {children}
    </span>
  );
};

/** A code block on the sunken ground, with the file's name above it when the fence gives one; long lines scroll sideways. */
const Pre = ({ node, children }: ComponentProps<"pre"> & ExtraProps) => {
  const file = node?.properties["dataFile"];
  const block = (
    <pre className="my-0 overflow-x-auto rounded-code bg-surface-sunken py-2 font-mono text-[0.875em] leading-[1.625] text-ink-soft">
      {children}
    </pre>
  );
  return (
    <figure className="my-3">
      {typeof file === "string" && (
        <figcaption
          data-chrome=""
          className="mb-1 font-mono text-[0.75em] leading-[1.45] text-ink-muted"
        >
          {file}
        </figcaption>
      )}
      {block}
    </figure>
  );
};

/** Whether the user folded the section of the key, which the plugin of the sections puts on the node. */
const useFolded = (key: unknown) => {
  const folds = useContext(FoldContext);
  return (
    folds !== null && typeof key === "string" && folds.sections.includes(key)
  );
};

/** A section of the card, which shows its heading alone while it is folded. */
const Section = ({
  node,
  children,
  ...props
}: ComponentProps<"section"> & ExtraProps) => {
  const folded = useFolded(node?.properties["dataSection"]);
  return (
    <section {...props} data-folded={folded ? "" : undefined}>
      {children}
    </section>
  );
};

type THeadingTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6";

type THeadingProps = ComponentProps<THeadingTag> &
  ExtraProps & { tag: THeadingTag };

/**
 * A heading, with the triangle that folds its section where the card folds. A heading that is the card's first block
 * has the card's own triangle instead, in the card's left padding, level with the heading's line.
 */
const Heading = ({ tag: Tag, node, children, ...props }: THeadingProps) => {
  const folds = useContext(FoldContext);
  const key = node?.properties["dataSectionHeading"];
  const folded = useFolded(key);
  return (
    <Tag {...props}>
      {folds !== null && node?.properties["dataLeadHeading"] !== undefined && (
        <FoldButton
          folded={false}
          label={folds.label}
          toggle={folds.toggleCard}
          className="-ml-[var(--pad)] inline-grid h-[1lh] w-[var(--pad)] align-top"
        />
      )}
      {folds !== null && typeof key === "string" && (
        <FoldButton
          folded={folded}
          label={`the section ${textIn(node)}`}
          toggle={() => {
            folds.toggle(key);
          }}
          className="mr-1.5 -ml-0.5 inline-grid h-[1lh] w-4 align-top"
        />
      )}
      {children}
    </Tag>
  );
};

/** Links open in a new tab. */
const Anchor = ({ href, children }: ComponentProps<"a"> & ExtraProps) => (
  <a href={href} target="_blank" rel="noreferrer" onClick={stop}>
    {children}
  </a>
);

const components = {
  section: Section,
  h1: (props: ComponentProps<"h1"> & ExtraProps) => (
    <Heading tag="h1" {...props} />
  ),
  h2: (props: ComponentProps<"h2"> & ExtraProps) => (
    <Heading tag="h2" {...props} />
  ),
  h3: (props: ComponentProps<"h3"> & ExtraProps) => (
    <Heading tag="h3" {...props} />
  ),
  h4: (props: ComponentProps<"h4"> & ExtraProps) => (
    <Heading tag="h4" {...props} />
  ),
  h5: (props: ComponentProps<"h5"> & ExtraProps) => (
    <Heading tag="h5" {...props} />
  ),
  h6: (props: ComponentProps<"h6"> & ExtraProps) => (
    <Heading tag="h6" {...props} />
  ),
  a: Anchor,
  span: Span,
  pre: Pre,
  td: Cell,
  th: HeaderCell,
  input: Input,
};

const remarkPlugins = [remarkGfm];

type TCardBodyProps = {
  md: string;
  /** The markdown before the changes the card shows, or null to show it plain. */
  before?: string | null;
  diffStyle?: TDiffStyle;
  toggle?: TToggle;
  /** The folds of the card's sections, or none for a card that does not fold, such as an earlier version. */
  folds?: TCardFolds;
};

/** Whether the markdown has a fenced code block, which the colouring loads the highlighter for. */
const hasFence = (md: string) => /^\s*(```|~~~)/m.test(md);

const plugins = (
  before: string | null,
  style: TDiffStyle,
  colour: boolean,
): PluggableList => [
  markBoxes,
  wrapSections,
  ...(before === null
    ? []
    : [[showChanges, { before, style }] satisfies Pluggable]),
  ...(colour ? [highlight] : []),
  markCodeLines,
];

const CardMarkdown = ({
  md,
  before = null,
  diffStyle = "word",
  toggle = null,
  folds = null,
}: TCardBodyProps): ReactNode => (
  <div data-text-root="" className="markdown select-text">
    <FoldContext value={folds}>
      <ToggleContext value={toggle}>
        {hasFence(md) ? (
          <MarkdownHooks
            remarkPlugins={remarkPlugins}
            rehypePlugins={plugins(before, diffStyle, true)}
            components={components}
            fallback={
              <Markdown
                remarkPlugins={remarkPlugins}
                rehypePlugins={plugins(before, diffStyle, false)}
                components={components}
              >
                {md}
              </Markdown>
            }
          >
            {md}
          </MarkdownHooks>
        ) : (
          <Markdown
            remarkPlugins={remarkPlugins}
            rehypePlugins={plugins(before, diffStyle, false)}
            components={components}
          >
            {md}
          </Markdown>
        )}
      </ToggleContext>
    </FoldContext>
  </div>
);

/**
 * The card's markdown on the design's scale: code blocks on the sunken ground, a table's boxes as checkboxes, a fold
 * triangle on each heading where the card folds, and, with the markdown before, the changes since it. A card with a
 * code block shows plain until the highlighter loads.
 */
export const CardBody = memo(CardMarkdown);
