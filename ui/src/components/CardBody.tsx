import { memo } from "react";
import type { ComponentProps, ReactNode } from "react";
import Markdown, { MarkdownHooks } from "react-markdown";
import type { ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Connector, Marks } from "~/components/Marks";
import { ColumnKind } from "~/lib/columns";
import { invariant } from "~/lib/invariant";
import { highlight } from "~/lib/highlight";
import { numberParts } from "~/lib/numberParts";
import {
  CardContext,
  SelectionKind,
  isSelected,
  useCardId,
  useTools,
} from "~/lib/whiteboard";
import { ActionKind } from "~/schemas/actions";
import type { TValue } from "~/schemas/actions";

const usePart = (node: ExtraProps["node"]) => {
  const number = node?.properties["dataPart"];
  invariant(typeof number === "number", "numberParts numbers each part");
  const ref = `${useCardId()}/${String(number)}`;
  const { selection, select, linking, readOnly } = useTools();
  return {
    ref,
    /** An earlier version's parts have no data-ref, so that the board finds only the parts of the cards on it. */
    dataRef: readOnly ? undefined : ref,
    selected: isSelected(selection, ref),
    linkingFrom: linking?.from === ref,
    select: () => {
      select({ kind: SelectionKind.enum.ref, ref });
    },
  };
};

const partTone = (selected: boolean, linkingFrom: boolean) =>
  linkingFrom
    ? "bg-violet-50 ring-2 ring-violet-400"
    : selected
      ? "bg-sky-50 ring-1 ring-sky-300"
      : "hover:bg-stone-100/80";

/** A paragraph outside a list item is a part; one in a list item is text of the item. */
const Paragraph = ({ node, children }: ComponentProps<"p"> & ExtraProps) =>
  node?.properties["dataPart"] === undefined ? (
    <p>{children}</p>
  ) : (
    <Block node={node} tag="p">
      {children}
    </Block>
  );

const headingTags = ["h1", "h2", "h3", "h4", "h5", "h6"] as const;

/** A heading is a part, under its own tag. */
const Heading = ({ node, children }: ComponentProps<"h1"> & ExtraProps) => {
  const tag = headingTags.find((name) => name === node?.tagName) ?? "h2";
  return (
    <Block node={node} tag={tag}>
      {children}
    </Block>
  );
};

/** A block of prose as a part: a click selects it, as for a list item. */
const Block = ({
  node,
  tag: Tag,
  children,
}: ExtraProps & {
  tag: "p" | (typeof headingTags)[number];
  children?: ReactNode;
}) => {
  const part = usePart(node);
  return (
    <Tag
      data-ref={part.dataRef}
      className={`group/part relative -mx-2 cursor-pointer rounded-md px-2 pr-24 transition-colors ${partTone(part.selected, part.linkingFrom)}`}
      onClick={(event) => {
        event.stopPropagation();
        part.select();
      }}
    >
      {children}
      <Marks target={part.ref} />
      <Connector target={part.ref} />
    </Tag>
  );
};

/** A click selects the item; the click does not reach the items around it. */
const ListItem = ({ node, children }: ComponentProps<"li"> & ExtraProps) => {
  const part = usePart(node);
  return (
    <li
      data-ref={part.dataRef}
      className={`group/part relative -mx-2 cursor-pointer rounded-md px-2 pr-24 transition-colors ${partTone(part.selected, part.linkingFrom)}`}
      onClick={(event) => {
        event.stopPropagation();
        part.select();
      }}
    >
      {children}
      <Marks target={part.ref} />
      <Connector target={part.ref} />
    </li>
  );
};

const BodyRow = ({ node, children }: ComponentProps<"tr"> & ExtraProps) => {
  const part = usePart(node);
  return (
    <tr
      data-ref={part.dataRef}
      className={`group/part cursor-pointer transition-colors ${partTone(part.selected, part.linkingFrom)}`}
      onClick={(event) => {
        event.stopPropagation();
        part.select();
      }}
    >
      <td className="relative w-20">
        <Marks
          target={part.ref}
          place="absolute top-1/2 left-0 -translate-y-1/2"
        />
      </td>
      {children}
      <td className="relative w-0 p-0">
        <Connector target={part.ref} />
      </td>
    </tr>
  );
};

const lineTone = (selected: boolean, linkingFrom: boolean) =>
  linkingFrom
    ? "bg-violet-400/25 ring-2 ring-violet-400"
    : selected
      ? "bg-sky-400/20 ring-1 ring-sky-400"
      : "hover:bg-white/10";

const diffTone = (diff: unknown) =>
  diff === "add"
    ? "bg-emerald-500/15"
    : diff === "remove"
      ? "bg-rose-500/15"
      : "";

/** A line of code: its number in the file when the fence gives a file or a first line, and a tint for an added or removed line of a diff. */
const CodeLine = ({
  node,
  children,
}: ExtraProps & { children?: ReactNode }) => {
  const part = usePart(node);
  const line = node?.properties["dataLine"];
  return (
    <span
      data-ref={part.dataRef}
      className={`group/part relative block min-h-[1lh] cursor-pointer px-4 pr-28 transition-colors ${diffTone(node?.properties["dataDiff"])} ${lineTone(part.selected, part.linkingFrom)}`}
      onClick={(event) => {
        event.stopPropagation();
        part.select();
      }}
    >
      {typeof line === "number" && (
        <span className="mr-4 inline-block w-8 text-right text-stone-500 select-none">
          {line}
        </span>
      )}
      {children}
      <Marks
        target={part.ref}
        place="absolute top-1/2 right-1 -translate-y-1/2"
      />
      <Connector target={part.ref} />
    </span>
  );
};

/** A code block whose fence gives a file shows the file's name above the code. */
const Pre = ({
  node,
  className,
  ...props
}: ComponentProps<"pre"> & ExtraProps) => {
  const file = node?.properties["dataFile"];
  return typeof file === "string" ? (
    <figure className="my-3">
      <figcaption className="mt-0 rounded-t-md bg-stone-700 px-4 py-1 font-mono text-[11px] text-stone-300">
        {file}
      </figcaption>
      <pre {...props} className={`${className ?? ""} mt-0 rounded-t-none`} />
    </figure>
  ) : (
    <pre {...props} className={className} />
  );
};

/** The lines of code blocks are parts; Shiki's other spans colour the code. */
const Span = ({ node, ...props }: ComponentProps<"span"> & ExtraProps) =>
  node?.properties["dataPart"] === undefined ? (
    <span {...props} />
  ) : (
    <CodeLine node={node}>{props.children}</CodeLine>
  );

/** Header rows get an empty cell above the marks of the body rows, which sit before the row's text, clear of its inputs. */
const TableRow = (props: ComponentProps<"tr"> & ExtraProps) =>
  props.node?.properties["dataPart"] === undefined ? (
    <tr>
      <th />
      {props.children}
      <th className="p-0" />
    </tr>
  ) : (
    <BodyRow {...props} />
  );

/** Text and number cells fill when they lose focus or on Enter, checks and choices on each change; empty clears. */
const CellInput = ({
  target,
  kind,
  options,
}: {
  target: string;
  kind: unknown;
  options: unknown;
}) => {
  const { board, act, readOnly } = useTools();
  const value = board.values[target] ?? null;
  const fill = (next: TValue) => {
    if (next !== value)
      void act({ kind: ActionKind.enum.fill, ref: target, value: next });
  };
  const label = `Input ${target}`;
  const stop = (event: React.SyntheticEvent) => {
    event.stopPropagation();
  };
  switch (kind) {
    case ColumnKind.enum.check:
      return (
        <input
          type="checkbox"
          aria-label={label}
          disabled={readOnly}
          className="size-4 cursor-pointer accent-emerald-600"
          checked={value === true}
          onClick={stop}
          onChange={(event) => {
            fill(event.target.checked);
          }}
        />
      );
    case ColumnKind.enum.select:
      invariant(
        Array.isArray(options),
        "numberParts gives a select its options",
      );
      return (
        <select
          aria-label={label}
          disabled={readOnly}
          className={`cursor-pointer rounded-full border-0 px-2 py-0.5 text-xs font-medium outline-none focus:ring-2 focus:ring-sky-300 ${value === null ? "bg-stone-100 text-stone-400" : "bg-sky-100 text-sky-800"}`}
          value={typeof value === "string" ? value : ""}
          onClick={stop}
          onChange={(event) => {
            fill(event.target.value === "" ? null : event.target.value);
          }}
        >
          <option value="">choose</option>
          {options.map((option) => (
            <option key={String(option)}>{String(option)}</option>
          ))}
        </select>
      );
    case ColumnKind.enum.text:
    case ColumnKind.enum.number:
      return (
        <input
          key={String(value)}
          type={kind}
          aria-label={label}
          disabled={readOnly}
          placeholder="…"
          className={`border-b border-dashed border-stone-300 bg-transparent px-0.5 text-sm outline-none placeholder:text-stone-300 focus:border-solid focus:border-sky-500 ${kind === ColumnKind.enum.number ? "w-16" : "w-40"}`}
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
                : kind === ColumnKind.enum.number
                  ? Number(text)
                  : text,
            );
          }}
        />
      );
    default:
      throw new Error(`numberParts gives no input of kind ${String(kind)}`);
  }
};

const TableCell = ({ node, children }: ComponentProps<"td"> & ExtraProps) => {
  const target = node?.properties["dataInput"];
  const id = useCardId();
  return (
    <td>
      {typeof target === "string" ? (
        <CellInput
          target={`${id}/${target}`}
          kind={node?.properties["dataKind"]}
          options={node?.properties["dataOptions"]}
        />
      ) : (
        children
      )}
    </td>
  );
};

/** Links open in a new tab and do not select the part. */
const Anchor = ({ href, children }: ComponentProps<"a"> & ExtraProps) => (
  <a
    href={href}
    target="_blank"
    rel="noreferrer"
    onClick={(event) => {
      event.stopPropagation();
    }}
  >
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

/** The card's markdown, with each heading, paragraph, list item, table body row and code line as a part that takes feedback and arrows, and code blocks in colour. */
export const CardBody = memo(({ id, md }: { id: string; md: string }) => (
  <div className="prose prose-sm prose-stone max-w-none prose-headings:mb-2 prose-headings:font-semibold prose-headings:tracking-tight prose-p:my-1.5 prose-ol:my-1 prose-ul:my-1 prose-li:my-0.5 prose-table:my-2 prose-th:font-medium prose-th:text-stone-500 prose-code:font-normal prose-code:before:content-none prose-code:after:content-none prose-pre:overflow-visible prose-pre:px-0 prose-pre:text-[13px] prose-pre:leading-relaxed prose-pre:break-words prose-pre:whitespace-pre-wrap [&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-stone-100 [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:py-0.5">
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
));
CardBody.displayName = "CardBody";
