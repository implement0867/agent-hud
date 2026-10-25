import { memo } from "react";
import type {
  ComponentProps,
  MouseEvent,
  ReactNode,
  SyntheticEvent,
} from "react";
import Markdown, { MarkdownHooks } from "react-markdown";
import type { ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";
import { z } from "zod";

import { Connector, Marks } from "~/components/Marks";
import {
  CardContext,
  useCardId,
  useCellValue,
  useReadOnly,
  useStore,
} from "~/data/context";
import { ActionKind } from "~/domain/actions";
import type { TValue } from "~/domain/actions";
import { ColumnKind } from "~/domain/columns";
import { cellRef, partRef } from "~/domain/ref";
import {
  SelectionKind,
  isSelected,
  useWhiteboard,
} from "~/hooks/useWhiteboard";
import { assertNever } from "~/lib/assertNever";
import { highlight } from "~/lib/highlight";
import { invariant } from "~/lib/invariant";
import {
  DiffKind,
  inputOf,
  numberParts,
  partNumberOf,
} from "~/lib/numberParts";
import type { TInput } from "~/lib/numberParts";

type TPartTone = "idle" | "selected" | "linking";

const partTones: Record<TPartTone, string> = {
  idle: "hover:bg-surface-sunken/80",
  selected: "bg-accent-faint ring-1 ring-accent-ring",
  linking: "bg-draw-soft ring-2 ring-draw",
};

/** The tones of a code line, on the dark of the code block. */
const lineTones: Record<TPartTone, string> = {
  idle: "hover:bg-white/10",
  selected: "bg-accent-ring/20 ring-1 ring-accent-ring",
  linking: "bg-draw/25 ring-2 ring-draw",
};

const diffTones: Record<z.infer<typeof DiffKind>, string> = {
  add: "bg-success/15",
  remove: "bg-danger/15",
};

type TPart = {
  ref: string;
  dataRef: string | undefined;
  tone: TPartTone;
  onClick: ((event: MouseEvent) => void) | undefined;
};

/**
 * The ref of the part that numberParts numbered, its tone, and its click, which selects it. An earlier version's parts
 * have no data-ref, so that the board finds only the parts of the cards on it, and no click.
 */
const usePart = (node: ExtraProps["node"]): TPart => {
  const number = partNumberOf(node);
  invariant(number !== null, "numberParts numbers each part");
  const ref = partRef(useCardId(), number);
  const { selection, select, linkingFrom } = useWhiteboard();
  const readOnly = useReadOnly();
  if (readOnly)
    return { ref, dataRef: undefined, tone: "idle", onClick: undefined };
  return {
    ref,
    dataRef: ref,
    tone:
      linkingFrom === ref
        ? "linking"
        : isSelected(selection, ref)
          ? "selected"
          : "idle",
    onClick: (event) => {
      event.stopPropagation();
      select({ kind: SelectionKind.enum.ref, ref });
    },
  };
};

const HeadingTag = z.enum(["h1", "h2", "h3", "h4", "h5", "h6"]);

type TPartProps = ExtraProps & {
  tag: "p" | "li" | z.infer<typeof HeadingTag>;
  children?: ReactNode;
};

/** A heading, paragraph or list item as a part: a click selects it, and does not reach the parts around it. */
const Part = ({ node, tag: Tag, children }: TPartProps) => {
  const part = usePart(node);
  return (
    <Tag
      data-ref={part.dataRef}
      className={`group/part relative -mx-2 cursor-pointer rounded-md px-2 pr-24 transition-colors ${partTones[part.tone]}`}
      onClick={part.onClick}
    >
      {children}
      <Marks target={part.ref} placement="part" />
      <Connector target={part.ref} />
    </Tag>
  );
};

/** A paragraph outside a list item is a part; one in a list item is text of the item. */
const Paragraph = ({ node, children }: ComponentProps<"p"> & ExtraProps) =>
  partNumberOf(node) === null ? (
    <p>{children}</p>
  ) : (
    <Part node={node} tag="p">
      {children}
    </Part>
  );

/** A heading is a part under its own tag. */
const Heading = ({ node, children }: ComponentProps<"h1"> & ExtraProps) => (
  <Part node={node} tag={HeadingTag.parse(node?.tagName)}>
    {children}
  </Part>
);

const ListItem = ({ node, children }: ComponentProps<"li"> & ExtraProps) => (
  <Part node={node} tag="li">
    {children}
  </Part>
);

/** A table body row as a part, with its marks in a cell before the row's text, clear of its inputs. */
const BodyRow = ({ node, children }: ComponentProps<"tr"> & ExtraProps) => {
  const part = usePart(node);
  return (
    <tr
      data-ref={part.dataRef}
      className={`group/part cursor-pointer transition-colors ${partTones[part.tone]}`}
      onClick={part.onClick}
    >
      <td className="relative w-20">
        <Marks target={part.ref} placement="row" />
      </td>
      {children}
      <td className="relative w-0 p-0">
        <Connector target={part.ref} />
      </td>
    </tr>
  );
};

/** Header rows get an empty cell above the marks of the body rows. */
const TableRow = (props: ComponentProps<"tr"> & ExtraProps) =>
  partNumberOf(props.node) === null ? (
    <tr>
      <th />
      {props.children}
      <th className="p-0" />
    </tr>
  ) : (
    <BodyRow {...props} />
  );

/** A line of code: its number in the file when the fence gives a file or a first line, and a tint for an added or removed line of a diff. */
const CodeLine = ({
  node,
  children,
}: ExtraProps & { children?: ReactNode }) => {
  const part = usePart(node);
  const line = node?.properties["dataLine"];
  const diff = DiffKind.safeParse(node?.properties["dataDiff"]);
  return (
    <span
      data-ref={part.dataRef}
      className={`group/part relative block min-h-[1lh] cursor-pointer px-4 pr-28 transition-colors ${diff.success ? diffTones[diff.data] : ""} ${lineTones[part.tone]}`}
      onClick={part.onClick}
    >
      {typeof line === "number" && (
        <span
          data-chrome
          className="mr-4 inline-block w-8 text-right text-ink-muted select-none"
        >
          {line}
        </span>
      )}
      {children}
      <Marks target={part.ref} placement="line" />
      <Connector target={part.ref} />
    </span>
  );
};

/** The lines of code blocks are parts; Shiki's other spans colour the code. */
const Span = ({ node, ...props }: ComponentProps<"span"> & ExtraProps) =>
  partNumberOf(node) === null ? (
    <span {...props} />
  ) : (
    <CodeLine node={node}>{props.children}</CodeLine>
  );

/** A code block whose fence gives a file shows the file's name above the code. */
const Pre = ({
  node,
  className,
  ...props
}: ComponentProps<"pre"> & ExtraProps) => {
  const file = node?.properties["dataFile"];
  return typeof file === "string" ? (
    <figure className="my-3">
      <figcaption className="mt-0 rounded-t-md bg-ink-soft px-4 py-1 font-mono text-[11px] text-ink-ghost">
        {file}
      </figcaption>
      <pre {...props} className={`${className ?? ""} mt-0 rounded-t-none`} />
    </figure>
  ) : (
    <pre {...props} className={className} />
  );
};

const stop = (event: SyntheticEvent) => {
  event.stopPropagation();
};

type TCellInputProps = { target: string; input: TInput };

/** Text and number cells fill when they lose focus or on Enter, checks and choices on each change; empty clears. */
const CellInput = ({ target, input }: TCellInputProps) => {
  const store = useStore();
  const value = useCellValue(target);
  const readOnly = useReadOnly();
  const fill = (next: TValue) => {
    if (next !== value)
      void store.act({ kind: ActionKind.enum.fill, ref: target, value: next });
  };
  const label = `Input ${target}`;
  switch (input.kind) {
    case ColumnKind.enum.check:
      return (
        <input
          type="checkbox"
          aria-label={label}
          disabled={readOnly}
          className="size-4 cursor-pointer accent-success"
          checked={value === true}
          onClick={stop}
          onChange={(event) => {
            fill(event.target.checked);
          }}
        />
      );
    case ColumnKind.enum.select:
      return (
        <select
          aria-label={label}
          disabled={readOnly}
          className={`cursor-pointer rounded-full border-0 px-2 py-0.5 text-xs font-medium outline-none focus:ring-2 focus:ring-accent-ring ${value === null ? "bg-surface-sunken text-ink-faint" : "bg-accent-soft text-accent-strong"}`}
          value={typeof value === "string" ? value : ""}
          onClick={stop}
          onChange={(event) => {
            fill(event.target.value === "" ? null : event.target.value);
          }}
        >
          <option value="">choose</option>
          {input.options.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
      );
    case ColumnKind.enum.text:
    case ColumnKind.enum.number:
      return (
        <input
          key={String(value)}
          type={input.kind}
          aria-label={label}
          disabled={readOnly}
          placeholder="…"
          className={`border-b border-dashed border-ink-ghost bg-transparent px-0.5 text-sm outline-none placeholder:text-ink-ghost focus:border-solid focus:border-accent ${input.kind === ColumnKind.enum.number ? "w-16" : "w-40"}`}
          defaultValue={value === null ? "" : String(value)}
          onClick={stop}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
          }}
          onBlur={(event) => {
            const text = event.target.value;
            fill(
              text === ""
                ? null
                : input.kind === ColumnKind.enum.number
                  ? Number(text)
                  : text,
            );
          }}
        />
      );
    default:
      return assertNever(input.kind);
  }
};

const TableCell = ({ node, children }: ComponentProps<"td"> & ExtraProps) => {
  const id = useCardId();
  const input = node === undefined ? null : inputOf(node);
  return (
    <td>
      {input === null ? (
        children
      ) : (
        <CellInput
          target={cellRef(id, input.row, input.column)}
          input={input}
        />
      )}
    </td>
  );
};

/** Links open in a new tab and do not select the part. */
const Anchor = ({ href, children }: ComponentProps<"a"> & ExtraProps) => (
  <a href={href} target="_blank" rel="noreferrer" onClick={stop}>
    {children}
  </a>
);

const components = {
  li: ListItem,
  tr: TableRow,
  td: TableCell,
  a: Anchor,
  span: Span,
  pre: Pre,
  p: Paragraph,
  h1: Heading,
  h2: Heading,
  h3: Heading,
  h4: Heading,
  h5: Heading,
  h6: Heading,
};

const remarkPlugins = [remarkGfm];

const plainPlugins = [numberParts];

const highlightPlugins = [highlight, numberParts];

type TCardBodyProps = { id: string; md: string };

const CardMarkdown = ({ id, md }: TCardBodyProps) => (
  <div className="markdown">
    <CardContext value={id}>
      <MarkdownHooks
        remarkPlugins={remarkPlugins}
        rehypePlugins={highlightPlugins}
        components={components}
        fallback={
          <Markdown
            remarkPlugins={remarkPlugins}
            rehypePlugins={plainPlugins}
            components={components}
          >
            {md}
          </Markdown>
        }
      >
        {md}
      </MarkdownHooks>
    </CardContext>
  </div>
);

/**
 * The card's markdown, with each heading, paragraph, list item, table body row and code line as a part that takes
 * feedback and arrows, and code blocks in colour once the highlighter loads.
 */
export const CardBody = memo(CardMarkdown);
