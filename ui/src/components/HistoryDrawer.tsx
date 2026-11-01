import { X } from "lucide-react";

import { VersionBody } from "~/components/CardBody";
import { IconButton } from "~/components/IconButton";
import { TextButton } from "~/components/TextButton";
import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";
import { earlierVersions } from "~/domain/board";
import type { TThread } from "~/domain/board";
import { short } from "~/domain/text";
import { useWhiteboard } from "~/hooks/useWhiteboard";
import { Text } from "~/components/primitives/Text";

type TThreadsProps = { threads: Record<string, TThread> };

/** The comments of each thread of an earlier version, under the words they were on. */
const Threads = ({ threads }: TThreadsProps) => {
  const entries = Object.entries(threads);
  if (entries.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1.5 border-t border-divider pt-2 text-md">
      {entries.map(([id, thread]) => (
        <li key={id}>
          <span className="border-l-2 border-selection pl-1.5 text-ink-muted">
            {thread.quote === "" ? "the card" : short(thread.quote)}
          </span>
          {thread.comments.map((said) => (
            <p key={said.id} className="mt-0.5 text-ink-soft">
              <Text tone="faint">
                {said.author === "user" ? "you" : "agent"}:
              </Text>{" "}
              {said.text}
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
        <Text as="h2" size="xl" tone="ink" weight={600}>
          History
        </Text>
        {card !== null && (
          <>
            <Text size="md" tone="faint" mono>
              {card}
            </Text>
            <Text size="md">
              <TextButton
                variant="link"
                onClick={() => {
                  openHistory(null);
                }}
              >
                all cards
              </TextButton>
            </Text>
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
              className="rounded-card px-3 pt-2 pb-3 ring-1 ring-outline"
            >
              <header className="mb-1 flex justify-between font-mono text-sm text-ink-faint">
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
              <VersionBody md={version.card.md} />
              <Threads threads={version.threads} />
            </section>
          ),
        )}
      </div>
    </aside>
  );
};
