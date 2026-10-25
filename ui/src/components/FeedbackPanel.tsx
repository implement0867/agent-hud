import { Bot, SendHorizontal, User, X } from "lucide-react";
import { useState } from "react";

import { IconButton } from "~/components/IconButton";
import { useBoard, useThread } from "~/data/useBoard";
import { ActionKind, Author, Reaction, messageSchema } from "~/domain/actions";
import type { TSaid } from "~/domain/board";
import { reactionKeys, userReaction } from "~/domain/reactions";
import { splitRefs } from "~/domain/ref";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import { reactionIcons, reactionTones } from "~/theme";

type TRefTextProps = { text: string };

/** The text, with each ref to a part on the board, such as plan/2, as a link that shows the part. */
const RefText = ({ text }: TRefTextProps) => {
  const { model } = useBoard();
  const { show } = useWhiteboard();
  return splitRefs(text, (card) => Object.hasOwn(model.board.cards, card)).map(
    ({ text: piece, ref, at }) =>
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

type TBubbleProps = { said: TSaid; withRef?: boolean };

/** A message or comment, with the time it was said on hover; with its ref, a comment starts with a link to the part it is on. */
export const Bubble = ({ said, withRef = false }: TBubbleProps) => {
  const { show } = useWhiteboard();
  const mine = said.author === Author.enum.user;
  const Icon = mine ? User : Bot;
  const ref = withRef ? said.ref : null;
  return (
    <li
      className={`flex items-end gap-1.5 ${mine ? "flex-row-reverse" : ""}`}
      title={said.at === null ? undefined : new Date(said.at).toLocaleString()}
    >
      <span
        className={`grid size-5 shrink-0 place-items-center rounded-full ${mine ? "bg-accent-soft text-accent-strong" : "bg-outline text-ink-soft"}`}
      >
        <Icon className="size-3" />
      </span>
      <span
        className={`max-w-[85%] rounded-2xl px-3 py-1.5 text-sm whitespace-pre-wrap ${mine ? "rounded-br-sm bg-accent text-white" : "rounded-bl-sm bg-surface-sunken text-ink"}`}
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

/** Text that the user is writing, kept by the composer's parent so that it survives the composer closing. */
export type TDraft = { text: string; set: (text: string) => void };

type TComposerProps = {
  label: string;
  id: string;
  send: (text: string) => Promise<boolean>;
  draft: TDraft;
};

/** Enter sends and Shift+Enter starts a new line; the text stays until the server takes it. */
export const Composer = ({ label, id, send, draft }: TComposerProps) => {
  const [sending, setSending] = useState(false);
  const ready = !sending && messageSchema.safeParse(draft.text).success;
  const submit = async () => {
    if (!ready) return;
    setSending(true);
    if (await send(draft.text)) draft.set("");
    setSending(false);
  };
  return (
    <div className="flex items-end gap-1 rounded-2xl bg-surface-sunken p-1 focus-within:ring-2 focus-within:ring-accent-ring">
      <textarea
        rows={1}
        aria-label={label}
        placeholder={label}
        id={id}
        className="field-sizing-content max-h-40 min-h-8 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
        value={draft.text}
        readOnly={sending}
        onChange={(event) => {
          draft.set(event.target.value);
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
        className="grid size-8 place-items-center rounded-full bg-accent text-white transition-opacity disabled:opacity-30"
        onClick={() => {
          void submit();
        }}
      >
        <SendHorizontal className="size-4" />
      </button>
    </div>
  );
};

type TFeedbackPanelProps = {
  target: string;
  /** The half-written comment, and whether the card changed since the user started it. */
  draft: TDraft & { changed: boolean };
  maxHeight: number;
  /** Takes the panel's element, for the board to place it where it fits; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
};

/**
 * The reactions and comments of the selected part, in the viewport beside its card, at most as tall as the given height,
 * with the comments scrolling inside.
 */
export const FeedbackPanel = ({
  target,
  draft,
  maxHeight,
  measure,
}: TFeedbackPanelProps) => {
  const { store } = useBoard();
  const { select } = useWhiteboard();
  const thread = useThread(target);
  const reaction = userReaction(thread);
  const agents = thread.reactions.agent;
  return (
    <section
      ref={measure}
      aria-label={`Feedback on ${target}`}
      style={{ maxHeight }}
      className="panel pointer-events-auto flex w-72 animate-pop flex-col p-3 select-text"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
      // Esc anywhere in the panel, the comment box too, closes the panel and keeps the part selected.
      onKeyDownCapture={(event) => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        select({ kind: SelectionKind.enum.ref, ref: target }, false);
      }}
    >
      <header className="mb-2 flex shrink-0 items-center justify-between">
        <span className="rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-xs text-ink-muted">
          {target}
        </span>
        <IconButton
          variant="close"
          label="Close"
          onClick={() => {
            select(null);
          }}
        >
          <X className="size-4" />
        </IconButton>
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
              className={`flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-xs capitalize transition-colors ${on ? reactionTones[option] : "text-ink-muted hover:bg-surface-sunken"}`}
              onClick={() => {
                void store.act(
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
                <kbd className="text-[10px] text-ink-faint">
                  {reactionKeys[option].toUpperCase()}
                </kbd>
              </span>
            </button>
          );
        })}
      </div>
      {agents !== undefined && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-ink-muted">
          <Bot className="size-3.5" />
          the agent says{" "}
          <span
            className={`rounded-full px-1.5 py-px ${reactionTones[agents]}`}
          >
            {agents}
          </span>
        </p>
      )}
      {thread.comments.length > 0 && (
        <ul
          aria-label={`Comments on ${target}`}
          className="mb-2 flex min-h-16 flex-col gap-1.5 overflow-y-auto"
        >
          {thread.comments.map((said) => (
            <Bubble key={said.id} said={said} />
          ))}
        </ul>
      )}
      {draft.changed && draft.text !== "" ? (
        <p className="mb-1.5 text-[11px] text-warning-strong">
          The card changed since you started this comment.
        </p>
      ) : null}
      <Composer
        label="Comment"
        id="comment-box"
        send={(text) =>
          store.act({ kind: ActionKind.enum.comment, ref: target, text })
        }
        draft={draft}
      />
    </section>
  );
};
