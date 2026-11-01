import { Composer } from "~/components/Composer";
import type { TDraft } from "~/components/Composer";
import { useBoard, useStore } from "~/data/context";
import { ActionKind, Author } from "~/domain/actions";
import type { TAnchor, TSaid } from "~/domain/board";
import { useWhiteboard } from "~/hooks/useWhiteboard";
import { Text } from "~/components/primitives/Text";

type TCommentProps = { said: TSaid };

/** A comment: the user's as plain text, the agent's as a bubble at the right; the user's unsent words say so. */
const CommentLine = ({ said }: TCommentProps) => {
  const { model } = useBoard();
  const unsent = model.unsent.ids.has(said.id);
  const when =
    said.at === null ? undefined : new Date(said.at).toLocaleString();
  return said.author === Author.enum.agent ? (
    <li
      title={when}
      className="max-w-[90%] self-end rounded-bar bg-accent px-2 py-1 whitespace-pre-wrap text-on-accent"
    >
      {said.text}
    </li>
  ) : (
    <li
      title={unsent ? "Not sent yet" : when}
      data-unsent={unsent ? "" : undefined}
      className="whitespace-pre-wrap"
    >
      {said.text}
      {unsent ? (
        <span className="ml-1.5 rounded-sm px-1 text-xs text-warning-strong outline-1 outline-warning outline-dashed">
          unsent
        </span>
      ) : null}
    </li>
  );
};

type TThreadPopoverProps = {
  /** The thread to show, or the words of a new one. */
  thread: string | null;
  anchor: TAnchor;
  /** The half-written comment, and whether the card changed since the user started it. */
  draft: TDraft & { changed: boolean };
  maxHeight: number;
  /** Takes the popover's element, for the board to place it where it fits; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
  /** The first comment on new words started the thread with the id. */
  started: (id: string) => void;
};

/**
 * A thread in a small popover beside its words: the quoted words with a rule in the selection colour, the comments,
 * and a field to reply in. For words that have no thread yet, the first comment starts one there. Esc closes it.
 */
export const ThreadPopover = ({
  thread,
  anchor,
  draft,
  maxHeight,
  measure,
  started,
}: TThreadPopoverProps) => {
  const store = useStore();
  const { model } = useBoard();
  const { select } = useWhiteboard();
  const comments =
    thread === null ? [] : (model.board.threads[thread]?.comments ?? []);
  const words = anchor.quote === "" ? "The card as a whole" : anchor.quote;
  return (
    <section
      ref={measure}
      aria-label={`Thread on “${anchor.quote === "" ? anchor.card : anchor.quote}”`}
      style={{ maxHeight }}
      className="pointer-events-auto flex w-55 animate-pop flex-col gap-1.5 rounded-[10px] bg-surface px-2.5 py-2 text-md/4 text-ink-soft shadow-[var(--shadow-pop),0_0_0_1px_var(--edge)] select-text"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
      onKeyDownCapture={(event) => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        select(null);
      }}
    >
      <p className="line-clamp-3 shrink-0 border-l-2 border-selection pl-1.5 text-ink-muted">
        {words}
      </p>
      {comments.length > 0 && (
        <ul
          aria-label="Comments"
          className="flex min-h-0 flex-col gap-1.5 overflow-y-auto"
        >
          {comments.map((said) => (
            <CommentLine key={said.id} said={said} />
          ))}
        </ul>
      )}
      {draft.changed && draft.text !== "" ? (
        <Text as="p" size="sm" tone="warning">
          The card changed since you started this comment.
        </Text>
      ) : null}
      <Composer
        label={thread === null ? "Comment" : "Reply"}
        id="comment-box"
        send={async (text) => {
          const id = crypto.randomUUID().replaceAll("-", "");
          const taken = await store.act(
            {
              kind: ActionKind.enum.comment,
              card: anchor.card,
              quote: anchor.quote,
              occurrence: anchor.quote === "" ? null : anchor.occurrence,
              text,
            },
            id,
          );
          if (taken && thread === null) started(id);
          return taken;
        }}
        draft={draft}
      />
    </section>
  );
};
