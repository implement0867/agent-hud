import { Bot, SendHorizontal, User, X } from "lucide-react";
import { useState } from "react";

import {
  reactionIcons,
  reactionKeys,
  reactionTones,
  userReaction,
} from "~/lib/reactions";
import { splitRefs, useTools } from "~/lib/whiteboard";
import { ActionKind, Author, Reaction, messageSchema } from "~/schemas/actions";
import type { TSaid } from "~/schemas/board";

/** The text, with each ref to a part on the board, such as plan/2, as a link that shows the part. */
const RefText = ({ text }: { text: string }) => {
  const { board, show } = useTools();
  return splitRefs(text, board).map(({ text: piece, ref, at }) =>
    ref === null ? (
      <span key={at}>{piece}</span>
    ) : (
      <button
        key={at}
        type="button"
        className="font-mono underline decoration-dotted underline-offset-2"
        onClick={() => {
          show(ref);
        }}
      >
        {piece}
      </button>
    ),
  );
};

/** When it was said, for a hover, as the browser writes the time. */
const timeOf = (at: string | null) =>
  at === null ? undefined : new Date(at).toLocaleString();

/** A message or comment, with the time it was said on hover; with its ref, a comment starts with a link to the part it is on. */
export const Bubble = ({
  said,
  withRef = false,
}: {
  said: TSaid;
  withRef?: boolean;
}) => {
  const { show } = useTools();
  const mine = said.author === Author.enum.user;
  const Icon = mine ? User : Bot;
  const ref = withRef ? said.ref : null;
  return (
    <li
      className={`flex items-end gap-1.5 ${mine ? "flex-row-reverse" : ""}`}
      title={timeOf(said.at)}
    >
      <span
        className={`grid size-5 shrink-0 place-items-center rounded-full ${mine ? "bg-sky-100 text-sky-700" : "bg-stone-200 text-stone-600"}`}
      >
        <Icon className="size-3" />
      </span>
      <span
        className={`max-w-[85%] rounded-2xl px-3 py-1.5 text-sm whitespace-pre-wrap ${mine ? "rounded-br-sm bg-sky-600 text-white" : "rounded-bl-sm bg-stone-100 text-stone-800"}`}
      >
        {ref !== null && (
          <button
            type="button"
            aria-label={`Show ${ref}`}
            className="mr-1.5 rounded bg-black/10 px-1 font-mono text-[11px]"
            onClick={() => {
              show(ref);
            }}
          >
            {ref}
          </button>
        )}
        <RefText text={said.text} />
      </span>
    </li>
  );
};

/**
 * Enter sends and Shift+Enter starts a new line. The text stays until the server takes it, in the draft when the
 * parent keeps one, so that it survives the composer closing.
 */
export const Composer = ({
  label,
  id,
  send,
  draft,
}: {
  label: string;
  id: string;
  send: (text: string) => Promise<boolean>;
  draft?: { text: string; set: (text: string) => void };
}) => {
  const [own, setOwn] = useState("");
  const text = draft?.text ?? own;
  const setText = draft?.set ?? setOwn;
  const [sending, setSending] = useState(false);
  const ready = !sending && messageSchema.safeParse(text).success;
  const submit = async () => {
    if (!ready) return;
    setSending(true);
    if (await send(text)) setText("");
    setSending(false);
  };
  return (
    <div className="flex items-end gap-1 rounded-2xl bg-stone-100 p-1 focus-within:ring-2 focus-within:ring-sky-300">
      <textarea
        rows={1}
        aria-label={label}
        placeholder={label}
        id={id}
        className="field-sizing-content max-h-40 min-h-8 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
        value={text}
        readOnly={sending}
        onChange={(event) => {
          setText(event.target.value);
        }}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void submit();
          }
        }}
      />
      <button
        type="button"
        aria-label="Send"
        disabled={!ready}
        className="grid size-8 place-items-center rounded-full bg-sky-600 text-white transition-opacity disabled:opacity-30"
        onClick={() => {
          void submit();
        }}
      >
        <SendHorizontal className="size-4" />
      </button>
    </div>
  );
};

/**
 * The reactions and comments of the selected part, in the viewport beside its card, at most as tall as the given height,
 * with the comments scrolling inside; a half-written comment stays in its draft.
 */
export const FeedbackPanel = ({
  target,
  draft,
  maxHeight,
  measure,
}: {
  target: string;
  draft: { text: string; changed: boolean; set: (text: string) => void };
  maxHeight: number;
  /** Gets the panel's element, for the board to place it where it fits. */
  measure: (element: HTMLElement | null) => void;
}) => {
  const { board, act, select } = useTools();
  const thread = board.threads[target];
  const reaction = userReaction(thread);
  const agents = thread?.reactions.agent;
  return (
    <section
      ref={measure}
      aria-label={`Feedback on ${target}`}
      style={{ maxHeight }}
      className="pointer-events-auto flex w-72 animate-pop flex-col select-text rounded-2xl bg-white p-3 shadow-xl ring-1 ring-stone-900/10"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <header className="mb-2 flex shrink-0 items-center justify-between">
        <span className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-xs text-stone-500">
          {target}
        </span>
        <button
          type="button"
          aria-label="Close"
          className="rounded p-0.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
          onClick={() => {
            select(null);
          }}
        >
          <X className="size-4" />
        </button>
      </header>
      <div className="mb-3 grid shrink-0 grid-cols-3 gap-1">
        {Reaction.options.map((option) => {
          const Icon = reactionIcons[option];
          const on = reaction === option;
          return (
            <button
              key={option}
              type="button"
              aria-pressed={on}
              className={`flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-xs capitalize transition-colors ${on ? reactionTones[option] : "text-stone-500 hover:bg-stone-100"}`}
              onClick={() => {
                void act(
                  on
                    ? { kind: ActionKind.enum.unreact, ref: target }
                    : {
                        kind: ActionKind.enum.react,
                        ref: target,
                        reaction: option,
                      },
                );
              }}
            >
              <Icon className="size-4" strokeWidth={2.5} />
              <span>
                {option}{" "}
                <kbd className="text-[10px] text-stone-400">
                  {reactionKeys[option].toUpperCase()}
                </kbd>
              </span>
            </button>
          );
        })}
      </div>
      {agents !== undefined && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-stone-500">
          <Bot className="size-3.5" />
          the agent says{" "}
          <span
            className={`rounded-full px-1.5 py-px ${reactionTones[agents]}`}
          >
            {agents}
          </span>
        </p>
      )}
      {(thread?.comments.length ?? 0) > 0 && (
        <ul
          aria-label={`Comments on ${target}`}
          className="mb-2 flex min-h-16 flex-col gap-1.5 overflow-y-auto"
        >
          {thread?.comments.map((said) => (
            <Bubble key={said.id} said={said} />
          ))}
        </ul>
      )}
      {draft.changed && draft.text !== "" ? (
        <p className="mb-1.5 text-[11px] text-amber-800">
          The card changed since you started this comment.
        </p>
      ) : null}
      <Composer
        label="Comment"
        id="comment-box"
        send={(text) =>
          act({ kind: ActionKind.enum.comment, ref: target, text })
        }
        draft={draft}
      />
    </section>
  );
};
