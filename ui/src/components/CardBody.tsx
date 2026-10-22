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
  const { selection, select, linking } = useTools();
  return {
    ref,
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

/** A click selects the item; the click does not reach the items around it. */
const ListItem = ({ node, children }: ComponentProps<"li"> & ExtraProps) => {
  const part = usePart(node);
  return (
    <li
      data-ref={part.ref}
      className={`group/part relative -mx-2 cursor-pointer rounded-md px-2 pr-16 transition-colors ${partTone(part.selected, part.linkingFrom)}`}
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
      data-ref={part.ref}
      className={`group/part cursor-pointer transition-colors ${partTone(part.selected, part.linkingFrom)}`}
      onClick={(event) => {
        event.stopPropagation();
        part.select();
      }}
    >
      {children}
      <td className="relative w-16">
        <Marks target={part.ref} />
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

const CodeLine = ({
  node,
  children,
}: ExtraProps & { children?: ReactNode }) => {
  const part = usePart(node);
  return (
    <span
      data-ref={part.ref}
      className={`group/part relative block min-h-[1lh] cursor-pointer px-4 pr-16 transition-colors ${lineTone(part.selected, part.linkingFrom)}`}
      onClick={(event) => {
        event.stopPropagation();
        part.select();
      }}
    >
      {children}
      <Marks target={part.ref} />
      <Connector target={part.ref} />
    </span>
  );
};

/** The lines of code blocks are parts; Shiki's other spans colour the code. */
const Span = ({ node, ...props }: ComponentProps<"span"> & ExtraProps) =>
  node?.properties["dataPart"] === undefined ? (
    <span {...props} />
  ) : (
    <CodeLine node={node}>{props.children}</CodeLine>
  );

/** Header rows get an empty cell above the marks of the body rows. */
const TableRow = (props: ComponentProps<"tr"> & ExtraProps) =>
  props.node?.properties["dataPart"] === undefined ? (
    <tr>
      {props.children}
      <th />
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
  const { board, act } = useTools();
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
          placeholder={kind === ColumnKind.enum.number ? "0" : "…"}
          className="w-full min-w-12 border-b border-dashed border-stone-300 bg-transparent px-0.5 text-sm outline-none placeholder:text-stone-300 focus:border-solid focus:border-sky-500"
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
};

const remarkPlugins = [remarkGfm];

const plainPlugins = [numberParts];

const highlightPlugins = [highlight, numberParts];

/** The card's markdown, with each list item, table body row and code line as a part that takes feedback and arrows, and code blocks in colour. */
export const CardBody = memo(({ id, md }: { id: string; md: string }) => (
  <div className="prose prose-sm prose-stone max-w-none prose-headings:mb-2 prose-headings:font-semibold prose-headings:tracking-tight prose-p:my-1.5 prose-ol:my-1 prose-ul:my-1 prose-li:my-0.5 prose-table:my-2 prose-th:font-medium prose-th:text-stone-500 prose-code:font-normal prose-code:before:content-none prose-code:after:content-none prose-pre:overflow-visible prose-pre:px-0 prose-pre:break-words prose-pre:whitespace-pre-wrap [&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-stone-100 [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:py-0.5">
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
