import { X } from "lucide-react";

import { CardBody } from "~/components/CardBody";
import { IconButton } from "~/components/IconButton";
import { TextButton } from "~/components/TextButton";
import {
  FeedbackContext,
  ReadOnlyContext,
  useBoard,
  useStore,
} from "~/data/context";
import { ActionKind } from "~/domain/actions";
import { earlierVersions } from "~/domain/board";
import type { TThread } from "~/domain/board";
import { reactionsOf } from "~/domain/reactions";
import { useWhiteboard } from "~/hooks/useWhiteboard";
import { reactionTones } from "~/theme";

type TThreadsProps = { threads: Record<string, TThread> };

/** The reaction of each author and the comments of each part of an earlier version. */
const Threads = ({ threads }: TThreadsProps) => {
  const entries = Object.entries(threads);
  if (entries.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1.5 border-t border-divider pt-2 text-xs">
      {entries.map(([ref, thread]) => (
        <li key={ref}>
          <span className="font-mono text-ink-muted">{ref}</span>
          {reactionsOf(thread).map(([author, reaction]) => (
            <span
              key={author}
              className={`ml-1.5 rounded-full px-1.5 py-px ${reactionTones[reaction]}`}
            >
              {author}: {reaction}
            </span>
          ))}
          {thread.comments.map((said) => (
            <p key={said.id} className="mt-0.5 text-ink-soft">
              <span className="text-ink-faint">{said.author}:</span> {said.text}
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
};

type THistoryDrawerProps = {
  card: string | null;
  close: () => void;
  /** Takes the drawer's element, for the board to keep clear of it; returns what to do when it goes. */
  measure: (element: HTMLElement) => () => void;
};

/**
 * The earlier versions of one card, or of all cards, newest first, each with the feedback it had, in parts that take
 * no actions; a removed card has Restore. The drawer docks at the left: the board moves right to stay in view.
 */
export const HistoryDrawer = ({
  card,
  close,
  measure,
}: THistoryDrawerProps) => {
  const { model } = useBoard();
  const store = useStore();
  const { openHistory } = useWhiteboard();
  return (
    <aside
      ref={measure}
      aria-label="History"
      className="panel pointer-events-auto absolute top-16 bottom-20 left-4 flex w-96 animate-pop flex-col"
    >
      <header className="flex items-center gap-2 border-b border-divider px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">History</h2>
        {card !== null && (
          <>
            <span className="font-mono text-xs text-ink-faint">{card}</span>
            <span className="text-xs">
              <TextButton
                variant="link"
                onClick={() => {
                  openHistory(null);
                }}
              >
                all cards
              </TextButton>
            </span>
          </>
        )}
        <span className="ml-auto">
          <IconButton variant="close" label="Close the history" onClick={close}>
            <X className="size-4" />
          </IconButton>
        </span>
      </header>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        {earlierVersions(model.board, card).map(
          ({ card: id, number, version, removed }) => (
            <section
              key={`${id}/${String(number)}`}
              aria-label={`${id} version ${String(number)}`}
              className="rounded-xl px-3 pt-2 pb-3 ring-1 ring-outline"
            >
              <header className="mb-1 flex justify-between font-mono text-[11px] text-ink-faint">
                <span>
                  {id} · v{number}
                </span>
                {removed ? (
                  <span className="flex gap-2">
                    removed
                    <TextButton
                      variant="link"
                      label={`Restore ${id}`}
                      onClick={() => {
                        void store.act({ kind: ActionKind.enum.restore, id });
                      }}
                    >
                      Restore
                    </TextButton>
                  </span>
                ) : (
                  <span>replaced</span>
                )}
              </header>
              <ReadOnlyContext value>
                <FeedbackContext value={version}>
                  <CardBody id={id} md={version.card.md} />
                </FeedbackContext>
              </ReadOnlyContext>
              <Threads threads={version.threads} />
            </section>
          ),
        )}
      </div>
    </aside>
  );
};
