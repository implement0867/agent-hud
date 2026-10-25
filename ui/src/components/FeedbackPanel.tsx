import { Bot, X } from "lucide-react";

import { Bubble } from "~/components/Bubble";
import { Composer } from "~/components/Composer";
import type { TDraft } from "~/components/Composer";
import { IconButton } from "~/components/IconButton";
import { useBoard, useStore, useThread } from "~/data/context";
import { ActionKind, Reaction } from "~/domain/actions";
import { nameOf } from "~/domain/parts";
import { cardOf, isCardRef } from "~/domain/ref";
import { reactionKeys, toggleReaction, userReaction } from "~/domain/reactions";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import { reactionIcons, reactionTones } from "~/theme";

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
  const store = useStore();
  const { model } = useBoard();
  const { select } = useWhiteboard();
  const thread = useThread(target);
  const name = nameOf(model.board, target);
  const card = isCardRef(target) ? null : nameOf(model.board, cardOf(target));
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
        <span
          title={target}
          className="min-w-0 truncate text-xs text-ink-muted"
        >
          <span className="font-medium text-ink">
            {card === null ? name : `“${name}”`}
          </span>
          {card !== null && <span> in {card}</span>}
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
                void store.act(toggleReaction(thread, target, option));
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
