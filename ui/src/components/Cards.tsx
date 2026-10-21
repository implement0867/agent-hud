import { createContext, useContext, useMemo, useState } from "react";
import type { ComponentProps } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ExtraProps } from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoardSocket } from "~/api/boardSocket";
import { ActionKind, Author, Reaction, messageSchema } from "~/schemas/actions";
import type { TValue } from "~/schemas/actions";
import { ColumnKind } from "~/lib/columns";
import type { TBoard, TCard, TThread } from "~/schemas/board";
import { invariant } from "~/lib/invariant";
import { numberParts } from "~/lib/numberParts";

type TAct = TBoardSocket["act"];

const emptyThread: TThread = { reaction: null, comments: [] };

const CardContext = createContext<{
  id: string;
  threads: TBoard["threads"];
  values: TBoard["values"];
  act: TAct;
} | null>(null);

const LinkContext = createContext<{
  from: string | null;
  setFrom: (from: string | null) => void;
} | null>(null);

const useCard = () => {
  const context = useContext(CardContext);
  invariant(context !== null, "parts render inside a card");
  return context;
};

/** Pressing the set reaction again clears it. */
const ReactionButtons = ({
  target,
  thread,
  act,
}: {
  target: string;
  thread: TThread;
  act: TAct;
}) => (
  <div
    role="group"
    aria-label={`Reactions on ${target}`}
    className="flex gap-1"
  >
    {Reaction.options.map((reaction) => (
      <button
        key={reaction}
        type="button"
        className="rounded border border-stone-300 px-2 text-xs text-stone-600 hover:bg-stone-100 aria-pressed:bg-stone-800 aria-pressed:text-white"
        aria-pressed={thread.reaction === reaction}
        onClick={() => {
          void act(
            thread.reaction === reaction
              ? { kind: ActionKind.enum.unreact, ref: target }
              : { kind: ActionKind.enum.react, ref: target, reaction },
          );
        }}
      >
        {reaction}
      </button>
    ))}
  </div>
);

/** The first press marks the arrow's source, a press on another part draws the arrow to it, and a second press on the source cancels. */
const LinkButton = ({ target, act }: { target: string; act: TAct }) => {
  const link = useContext(LinkContext);
  invariant(link !== null, "parts render inside the cards");
  const { from, setFrom } = link;
  const [label, text] =
    from === null
      ? [`Link from ${target}`, "link"]
      : from === target
        ? [`Cancel link from ${target}`, "cancel"]
        : [`Link ${from} to ${target}`, "link here"];
  return (
    <button
      type="button"
      aria-label={label}
      className="rounded border border-stone-300 px-2 text-xs text-stone-600 hover:bg-stone-100"
      onClick={() => {
        if (from !== null && from !== target) {
          const id = `u${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
          void act({
            kind: ActionKind.enum.link,
            id,
            src: from,
            dst: target,
            text: "",
          });
        }
        setFrom(from === null ? target : null);
      }}
    >
      {text}
    </button>
  );
};

/** The page clears the box when it sends the comment. */
const CommentForm = ({ target, act }: { target: string; act: TAct }) => {
  const [text, setText] = useState("");
  return (
    <div className="mt-2 flex gap-1">
      <input
        className="flex-1 rounded border border-stone-300 px-2 text-sm"
        placeholder="Comment"
        aria-label={`Comment on ${target}`}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
      <button
        type="button"
        className="rounded border border-stone-300 px-2 text-xs text-stone-600 hover:bg-stone-100 disabled:text-stone-300"
        disabled={!messageSchema.safeParse(text).success}
        onClick={() => {
          void act({ kind: ActionKind.enum.comment, ref: target, text });
          setText("");
        }}
      >
        Comment
      </button>
    </div>
  );
};

/** The reaction buttons, comments and comment box of one part of the board. */
const Feedback = ({
  target,
  thread,
  act,
}: {
  target: string;
  thread: TThread;
  act: TAct;
}) => (
  <div className="not-prose">
    <div className="mt-2 flex gap-1">
      <ReactionButtons target={target} thread={thread} act={act} />
      <LinkButton target={target} act={act} />
    </div>
    <ul className="mt-2 space-y-1 text-sm text-stone-700">
      {thread.comments.map(({ id, text }) => (
        <li key={id} className="rounded bg-stone-100 px-2 py-1">
          {text}
        </li>
      ))}
    </ul>
    <CommentForm target={target} act={act} />
  </div>
);

const PartFeedback = ({ node }: ExtraProps) => {
  const context = useCard();
  const number = node?.properties["dataPart"];
  invariant(typeof number === "number", "numberParts numbers each part");
  const target = `${context.id}/${String(number)}`;
  return (
    <Feedback
      target={target}
      thread={context.threads[target] ?? emptyThread}
      act={context.act}
    />
  );
};

const ListItem = ({ node, children }: ComponentProps<"li"> & ExtraProps) => (
  <li data-ref={`${useCard().id}/${String(node?.properties["dataPart"])}`}>
    {children}
    <PartFeedback node={node} />
  </li>
);

/** A header row gets an empty cell above the feedback column. */
const TableRow = ({ node, children }: ComponentProps<"tr"> & ExtraProps) => (
  <tr data-ref={`${useCard().id}/${String(node?.properties["dataPart"])}`}>
    {children}
    {node?.properties["dataPart"] === undefined ? (
      <th />
    ) : (
      <td>
        <PartFeedback node={node} />
      </td>
    )}
  </tr>
);

/** Text and number cells send their value when they lose focus; checks and selects on each change. Empty clears. */
const CellInput = ({
  target,
  kind,
  options,
}: {
  target: string;
  kind: unknown;
  options: unknown;
}) => {
  const { values, act } = useCard();
  const value = values[target] ?? null;
  const fill = (next: TValue) => {
    if (next !== value)
      void act({ kind: ActionKind.enum.fill, ref: target, value: next });
  };
  const label = `Input ${target}`;
  switch (kind) {
    case ColumnKind.enum.check:
      return (
        <input
          type="checkbox"
          aria-label={label}
          checked={value === true}
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
          className="rounded border border-stone-300 text-sm"
          value={typeof value === "string" ? value : ""}
          onChange={(event) => {
            fill(event.target.value === "" ? null : event.target.value);
          }}
        >
          <option value="" />
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
          className="w-full rounded border border-stone-300 px-1 text-sm"
          defaultValue={value === null ? "" : String(value)}
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
  const { id } = useCard();
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

const CardView = ({
  id,
  card,
  threads,
  values,
  act,
}: {
  id: string;
  card: TCard;
  threads: TBoard["threads"];
  values: TBoard["values"];
  act: TAct;
}) => {
  const context = useMemo(
    () => ({ id, threads, values, act }),
    [id, threads, values, act],
  );
  return (
    <article
      data-ref={id}
      className={`rounded-lg border p-4 shadow-sm ${card.author === Author.enum.user ? "border-amber-200 bg-amber-50" : "border-stone-200 bg-white"}`}
    >
      <header className="mb-2 flex justify-between font-mono text-xs text-stone-400">
        {id}
        {card.author === Author.enum.user && (
          <button
            type="button"
            aria-label={`Remove ${id}`}
            className="rounded px-1 hover:bg-stone-200"
            onClick={() => {
              void act({ kind: ActionKind.enum.remove, id });
            }}
          >
            ×
          </button>
        )}
      </header>
      <div className="prose prose-sm prose-stone max-w-none">
        <CardContext value={context}>
          <Markdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[numberParts]}
            components={{ li: ListItem, tr: TableRow, td: TableCell }}
          >
            {card.md}
          </Markdown>
        </CardContext>
      </div>
      <Feedback target={id} thread={threads[id] ?? emptyThread} act={act} />
    </article>
  );
};

export const Cards = ({ board, act }: { board: TBoard; act: TAct }) => {
  const [from, setFrom] = useState<string | null>(null);
  const link = useMemo(() => ({ from, setFrom }), [from]);
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return (
    <LinkContext value={link}>
      {cards.map(([id, card]) => (
        <CardView
          key={id}
          id={id}
          card={card}
          threads={board.threads}
          values={board.values}
          act={act}
        />
      ))}
    </LinkContext>
  );
};
