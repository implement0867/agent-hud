import { MessageCircle } from "lucide-react";

import { SelectionKind, useTools } from "~/lib/whiteboard";
import { ActionKind, Author, Reaction } from "~/schemas/actions";
import {
  reactionIcons,
  reactionTones,
  reactionsOf,
  userReaction,
} from "~/lib/reactions";

/** The reactions with a button on the part: a question wants words, so it is set in the thread. */
const quick = Reaction.options.filter(
  (option) => option !== Reaction.enum.question,
);

/**
 * The marks of the ref, the reaction of each author and the comment count, and, while the pointer is on the part, a
 * button for approve and for reject before them, so that the marks stay where they are and a click on the comment
 * count opens the thread. The user's own reaction shows as the pressed button meanwhile. The agent's reaction has a
 * ring. A question is a comment with its mark, in the thread. The place puts the marks in the part, at the top right
 * unless it says otherwise; a place without "absolute" makes the marks a flex item of the part, as in a card's header.
 */
export const Marks = ({
  target,
  place = "absolute top-0.5 right-1",
}: {
  target: string;
  place?: string;
}) => {
  const { board, act, select, readOnly } = useTools();
  const thread = board.threads[target];
  const reaction = userReaction(thread);
  const comments = thread?.comments.length ?? 0;
  const open = () => {
    select({ kind: SelectionKind.enum.ref, ref: target });
  };
  return (
    <span
      className={`not-prose flex items-center gap-1 text-xs select-none ${place}`}
    >
      {!readOnly && (
        <span className="-my-0.5 hidden items-center gap-0.5 rounded-full bg-white/90 p-0.5 shadow-sm ring-1 ring-stone-200 group-hover/part:flex">
          {quick.map((option) => {
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
                className={`grid size-5 place-items-center rounded-full transition-colors ${on ? reactionTones[option] : "text-stone-400 hover:bg-stone-100 hover:text-stone-700"}`}
                onClick={(event) => {
                  event.stopPropagation();
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
                <Icon className="size-3.5" strokeWidth={2.5} />
              </button>
            );
          })}
        </span>
      )}
      {comments > 0 && (
        <button
          type="button"
          aria-label={`Thread on ${target}`}
          className="flex items-center gap-0.5 rounded-full bg-sky-100 px-1.5 py-0.5 text-sky-700 hover:bg-sky-200"
          onClick={(event) => {
            event.stopPropagation();
            open();
          }}
        >
          <MessageCircle className="size-3" />
          {comments}
        </button>
      )}
      {reactionsOf(thread).map(([author, reacted]) => {
        const Icon = reactionIcons[reacted];
        const own = author === Author.enum.user && !readOnly;
        return (
          <span
            key={author}
            role="img"
            aria-label={`${author}: ${reacted}`}
            className={`grid size-5 place-items-center rounded-full ${reactionTones[reacted]} ${author === "agent" ? "ring-2 ring-current ring-inset" : ""} ${own ? "group-hover/part:hidden" : ""}`}
          >
            <Icon className="size-3.5" strokeWidth={3} />
          </span>
        );
      })}
    </span>
  );
};

/**
 * A dot beside the right edge of a part or card; a drag from it draws an arrow. The dot sits in a strip that joins the
 * part's edge, so that the pointer stays on the part on its way to the dot. The strip is there, unseen, while the part
 * is not hovered, so that a pointer that jumps onto it from outside finds it and the dot shows. A click on the dot
 * draws nothing and selects nothing.
 */
export const Connector = ({ target }: { target: string }) => {
  const { beginLink, readOnly } = useTools();
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
      <span className="size-3 rounded-full border-2 border-violet-500 bg-white shadow transition-transform group-hover/dot:scale-125 group-hover/dot:bg-violet-500" />
    </span>
  );
};
