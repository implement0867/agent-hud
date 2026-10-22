import { MessageCircle } from "lucide-react";

import { useTools } from "~/lib/whiteboard";
import { ActionKind, Reaction } from "~/schemas/actions";
import { reactionIcons, reactionTones } from "~/lib/reactions";

/**
 * The reaction and comment count of the ref, and, while the pointer is on the part, a button for each reaction.
 * The place puts the marks in the part, at the top right unless it says otherwise.
 */
export const Marks = ({
  target,
  place = "top-0.5 right-1",
}: {
  target: string;
  place?: string;
}) => {
  const { board, act, readOnly } = useTools();
  const thread = board.threads[target];
  const reaction = thread?.reaction ?? null;
  const comments = thread?.comments.length ?? 0;
  const ReactionIcon = reaction === null ? null : reactionIcons[reaction];
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
        {reaction !== null && ReactionIcon !== null && (
          <span
            className={`grid size-5 place-items-center rounded-full ${reactionTones[reaction]}`}
            title={reaction}
          >
            <ReactionIcon className="size-3.5" strokeWidth={3} />
          </span>
        )}
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

/** A dot on the right edge of a part or card; a drag from it draws an arrow. */
export const Connector = ({ target }: { target: string }) => {
  const { beginLink, readOnly } = useTools();
  if (readOnly) return null;
  return (
    <span
      role="button"
      tabIndex={-1}
      aria-label={`Draw an arrow from ${target}`}
      title="Drag to draw an arrow"
      className="absolute top-1/2 -right-[1.4rem] hidden size-3 -translate-y-1/2 cursor-crosshair rounded-full border-2 border-violet-500 bg-white shadow group-hover/part:block hover:scale-125 hover:bg-violet-500"
      onPointerDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
        beginLink(target, event);
      }}
    />
  );
};
