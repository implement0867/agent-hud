import { MessageCircle } from "lucide-react";

import { useBoard, useReadOnly, useStore, useThread } from "~/data/context";
import { Author } from "~/domain/actions";
import {
  quickReactions,
  reactionsOf,
  toggleReaction,
  userReaction,
} from "~/domain/reactions";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import { reactionIcons, reactionTones, unsentTone } from "~/theme";

/** Where the marks sit: at the top right of a part, before a table row, at the end of a code line, or in line in a card's header. */
export type TMarksPlacement = "part" | "row" | "line" | "header";

const placements: Record<TMarksPlacement, string> = {
  part: "absolute top-0.5 right-1",
  row: "absolute top-1/2 left-0 -translate-y-1/2",
  line: "absolute top-1/2 right-1 -translate-y-1/2",
  header: "shrink-0",
};

type TMarksProps = { target: string; placement: TMarksPlacement };

/**
 * The marks of the ref: the reaction of each author and the comment count, and, while the pointer is on the part, a
 * button for approve and for reject before them, so that the marks stay where they are and a click on the comment
 * count opens the thread. The user's own reaction shows as the pressed button meanwhile. The agent's reaction has a
 * ring. A question is a comment with its mark, in the thread.
 */
export const Marks = ({ target, placement }: TMarksProps) => {
  const store = useStore();
  const { select } = useWhiteboard();
  const thread = useThread(target);
  const readOnly = useReadOnly();
  const { unsent } = useBoard().model;
  const reaction = userReaction(thread);
  const comments = thread.comments.length;
  const commentUnsent =
    !readOnly && thread.comments.some(({ id }) => unsent.ids.has(id));
  const reactionUnsent =
    !readOnly && reaction !== null && unsent.refs.has(target);
  return (
    <span
      data-chrome
      className={`not-prose flex items-center gap-1 text-xs select-none ${placements[placement]}`}
    >
      {!readOnly && (
        <span className="-my-0.5 hidden items-center gap-0.5 rounded-full bg-surface/90 p-0.5 shadow-sm ring-1 ring-outline group-hover/part:flex">
          {quickReactions.map((option) => {
            const Icon = reactionIcons[option];
            const on = reaction === option;
            return (
              <button
                key={option}
                type="button"
                aria-label={`${option} ${target}`}
                aria-pressed={on}
                // The buttons are for the pointer; the keys A and R react to the selection, so Tab passes them.
                tabIndex={-1}
                className={`grid size-5 place-items-center rounded-full transition-colors ${on ? reactionTones[option] : "text-ink-faint hover:bg-surface-sunken hover:text-ink-soft"}`}
                onClick={(event) => {
                  event.stopPropagation();
                  void store.act(toggleReaction(thread, target, option));
                }}
              >
                <Icon className="size-3.5" strokeWidth={2.5} />
              </button>
            );
          })}
        </span>
      )}
      {comments > 0 && (
        <button
          type="button"
          aria-label={`Thread on ${target}${commentUnsent ? ", unsent" : ""}`}
          title={commentUnsent ? "A comment not sent yet" : undefined}
          data-unsent={commentUnsent ? "" : undefined}
          disabled={readOnly}
          className={`flex items-center gap-0.5 rounded-full bg-accent-soft px-1.5 py-0.5 text-accent-strong enabled:hover:bg-accent-muted ${commentUnsent ? `${unsentTone} outline-offset-1` : ""}`}
          onClick={(event) => {
            event.stopPropagation();
            select({ kind: SelectionKind.enum.ref, ref: target });
          }}
        >
          <MessageCircle className="size-3" />
          {comments}
        </button>
      )}
      {reactionsOf(thread).map(([author, reacted]) => {
        const Icon = reactionIcons[reacted];
        const pending = author === Author.enum.user && reactionUnsent;
        return (
          <span
            key={author}
            role="img"
            aria-label={`${author}: ${reacted}${pending ? ", unsent" : ""}`}
            title={pending ? "Not sent yet" : undefined}
            data-unsent={pending ? "" : undefined}
            className={`grid size-5 place-items-center rounded-full ${reactionTones[reacted]} ${author === Author.enum.agent ? "ring-2 ring-current ring-inset" : ""} ${author === Author.enum.user && !readOnly ? "group-hover/part:hidden" : ""} ${pending ? `${unsentTone} outline-offset-1` : ""}`}
          >
            <Icon className="size-3.5" strokeWidth={3} />
          </span>
        );
      })}
    </span>
  );
};

type TConnectorProps = { target: string };

/**
 * A dot beside the right edge of a part or card; a drag from it draws an arrow. The dot sits in a strip that joins the
 * part's edge, so that the pointer stays on the part on its way to the dot. The strip is there, unseen, while the part
 * is not hovered, so that a pointer that jumps onto it from outside finds it and the dot shows. A click on the dot
 * draws nothing and selects nothing. An earlier version's parts have none.
 */
export const Connector = ({ target }: TConnectorProps) => {
  const { beginLink } = useWhiteboard();
  const readOnly = useReadOnly();
  if (readOnly) return null;
  return (
    <span
      role="button"
      tabIndex={-1}
      aria-label={`Draw an arrow from ${target}`}
      className="group/dot absolute inset-y-0 left-full flex w-[1.4rem] cursor-crosshair items-center justify-end opacity-0 group-hover/part:opacity-100"
      onPointerDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
        beginLink(target, event);
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <span className="size-3 rounded-full border-2 border-draw bg-surface shadow transition-transform group-hover/dot:scale-125 group-hover/dot:bg-draw" />
    </span>
  );
};
