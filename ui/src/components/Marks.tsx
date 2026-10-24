import { MessageCircle } from "lucide-react";

import { SelectionKind, useTools } from "~/lib/whiteboard";
import { ActionKind, Reaction } from "~/schemas/actions";
import {
  reactionIcons,
  reactionTones,
  reactionsOf,
  userReaction,
} from "~/lib/reactions";

/**
 * The reaction of each author and the comment count of the ref, and, while the pointer is on the part, a button for each reaction.
 * The agent's reaction has a ring. The place puts the marks in the part, at the top right unless it says otherwise.
 * A question wants words, so the question button also opens the part's feedback with the comment box focused.
 */
export const Marks = ({
  target,
  place = "top-0.5 right-1",
}: {
  target: string;
  place?: string;
}) => {
  const { board, act, select, readOnly } = useTools();
  const thread = board.threads[target];
  const reaction = userReaction(thread);
  const comments = thread?.comments.length ?? 0;
  return (
    <span
      className={`not-prose absolute flex items-center gap-1 text-xs select-none ${place}`}
    >
      <span
        className={`flex items-center gap-1 ${readOnly ? "" : "group-hover/part:hidden"}`}
      >
        {comments > 0 && (
          <span className="flex items-center gap-0.5 rounded-full bg-sky-100 px-1.5 py-0.5 text-sky-700">
            <MessageCircle className="size-3" />
            {comments}
          </span>
        )}
        {reactionsOf(thread).map(([author, reacted]) => {
          const Icon = reactionIcons[reacted];
          return (
            <span
              key={author}
              className={`grid size-5 place-items-center rounded-full ${reactionTones[reacted]} ${author === "agent" ? "ring-2 ring-current ring-inset" : ""}`}
              title={`${author}: ${reacted}`}
            >
              <Icon className="size-3.5" strokeWidth={3} />
            </span>
          );
        })}
      </span>
      <span
        className={`hidden items-center gap-0.5 rounded-full bg-white/90 p-0.5 shadow-sm ring-1 ring-stone-200 ${readOnly ? "" : "group-hover/part:flex"}`}
      >
        {Reaction.options.map((option) => {
          const Icon = reactionIcons[option];
          const on = reaction === option;
          return (
            <button
              key={option}
              type="button"
              aria-label={`${option} ${target}`}
              aria-pressed={on}
              title={option}
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
                if (on || option !== Reaction.enum.question) return;
                select({ kind: SelectionKind.enum.ref, ref: target });
                requestAnimationFrame(() => {
                  document.getElementById("comment-box")?.focus();
                });
              }}
            >
              <Icon className="size-3.5" strokeWidth={2.5} />
            </button>
          );
        })}
      </span>
    </span>
  );
};

/**
 * A dot beside the right edge of a part or card; a drag from it draws an arrow. The dot sits in a strip that joins the
 * part's edge, so that the pointer stays on the part on its way to the dot.
 */
export const Connector = ({ target }: { target: string }) => {
  const { beginLink, readOnly } = useTools();
  if (readOnly) return null;
  return (
    <span
      role="button"
      tabIndex={-1}
      aria-label={`Draw an arrow from ${target}`}
      className="group/dot absolute inset-y-0 left-full hidden w-[1.4rem] cursor-crosshair items-center justify-end group-hover/part:flex"
      onPointerDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
        beginLink(target, event);
      }}
    >
      <span className="size-3 rounded-full border-2 border-violet-500 bg-white shadow transition-transform group-hover/dot:scale-125 group-hover/dot:bg-violet-500" />
    </span>
  );
};
