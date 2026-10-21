import { createContext, useContext, useMemo, useState } from "react";
import type { ComponentProps } from "react";
import Markdown from "react-markdown";
import type { ExtraProps } from "react-markdown";

import { Notice } from "~/components/Notice";
import type { TBoardSocket } from "~/api/boardSocket";
import { ActionKind, Reaction, messageSchema } from "~/schemas/actions";
import type { TBoard, TCard, TThread } from "~/schemas/board";
import { invariant } from "~/lib/invariant";
import { numberListItems } from "~/lib/numberListItems";

type TAct = TBoardSocket["act"];

const emptyThread: TThread = { reaction: null, comments: [] };

const CardContext = createContext<{
  id: string;
  threads: TBoard["threads"];
  act: TAct;
} | null>(null);

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
    className="mt-2 flex gap-1"
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
    <ReactionButtons target={target} thread={thread} act={act} />
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

const ListItem = ({ node, children }: ComponentProps<"li"> & ExtraProps) => {
  const context = useContext(CardContext);
  const number = node?.properties["dataItem"];
  invariant(context !== null, "list items render inside a card");
  invariant(typeof number === "number", "numberListItems numbers each li");
  const target = `${context.id}/${String(number)}`;
  return (
    <li>
      {children}
      <Feedback
        target={target}
        thread={context.threads[target] ?? emptyThread}
        act={context.act}
      />
    </li>
  );
};

const CardView = ({
  id,
  card,
  threads,
  act,
}: {
  id: string;
  card: TCard;
  threads: TBoard["threads"];
  act: TAct;
}) => {
  const context = useMemo(() => ({ id, threads, act }), [id, threads, act]);
  return (
    <article className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <header className="mb-2 font-mono text-xs text-stone-400">{id}</header>
      <div className="prose prose-sm prose-stone max-w-none">
        <CardContext value={context}>
          <Markdown
            rehypePlugins={[numberListItems]}
            components={{ li: ListItem }}
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
  const cards = Object.entries(board.cards);
  if (cards.length === 0) return <Notice>No cards yet.</Notice>;
  return cards.map(([id, card]) => (
    <CardView key={id} id={id} card={card} threads={board.threads} act={act} />
  ));
};
