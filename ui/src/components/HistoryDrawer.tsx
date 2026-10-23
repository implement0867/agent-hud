import { X } from "lucide-react";

import { CardBody } from "~/components/CardBody";
import { reactionTones, reactionsOf } from "~/lib/reactions";
import { ToolContext, readOnlyTools, useTools } from "~/lib/whiteboard";
import { ActionKind } from "~/schemas/actions";
import type { TThread } from "~/schemas/board";

/** The reaction of each author and the comments of each part of an earlier version. */
const Threads = ({ threads }: { threads: Record<string, TThread> }) => {
  const entries = Object.entries(threads);
  if (entries.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1.5 border-t border-stone-100 pt-2 text-xs">
      {entries.map(([ref, thread]) => (
        <li key={ref}>
          <span className="font-mono text-stone-500">{ref}</span>
          {reactionsOf(thread).map(([author, reaction]) => (
            <span
              key={author}
              className={`ml-1.5 rounded-full px-1.5 py-px ${reactionTones[reaction]}`}
            >
              {author}: {reaction}
            </span>
          ))}
          {thread.comments.map((said) => (
            <p key={said.id} className="mt-0.5 text-stone-700">
              <span className="text-stone-400">{said.author}:</span> {said.text}
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
};

/** The earlier versions of one card, or of all cards, newest first, each with the feedback it had; a removed card has Restore. */
export const HistoryDrawer = ({
  card,
  choose,
  close,
}: {
  card: string | null;
  choose: (card: string | null) => void;
  close: () => void;
}) => {
  const tools = useTools();
  const { board, act } = tools;
  const ids = card === null ? Object.keys(board.history) : [card];
  const removed = (id: string, number: number) =>
    !Object.hasOwn(board.cards, id) &&
    number === (board.history[id]?.length ?? 0);
  return (
    <aside
      aria-label="History"
      className="pointer-events-auto absolute top-16 bottom-20 left-4 flex w-96 animate-pop flex-col rounded-2xl bg-white shadow-xl ring-1 ring-stone-900/10"
    >
      <header className="flex items-center gap-2 border-b border-stone-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-stone-800">History</h2>
        {card !== null && (
          <>
            <span className="font-mono text-xs text-stone-400">{card}</span>
            <button
              type="button"
              className="text-xs text-sky-700 hover:underline"
              onClick={() => {
                choose(null);
              }}
            >
              all cards
            </button>
          </>
        )}
        <button
          type="button"
          aria-label="Close the history"
          className="ml-auto rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
          onClick={close}
        >
          <X className="size-4" />
        </button>
      </header>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
        {ids.every((id) => (board.history[id]?.length ?? 0) === 0) && (
          <p className="m-auto max-w-52 text-center text-sm text-stone-400">
            The earlier versions of the cards show here.
          </p>
        )}
        {ids.flatMap((id) =>
          (board.history[id] ?? [])
            .map((version, index) => ({ version, number: index + 1 }))
            .toReversed()
            .map(({ version, number }) => (
              <section
                key={`${id}/${String(number)}`}
                aria-label={`${id} version ${String(number)}`}
                className="rounded-xl px-3 pt-2 pb-3 ring-1 ring-stone-200"
              >
                <header className="mb-1 flex justify-between font-mono text-[11px] text-stone-400">
                  <span>
                    {id} · v{number}
                  </span>
                  {removed(id, number) ? (
                    <span className="flex gap-2">
                      removed
                      <button
                        type="button"
                        aria-label={`Restore ${id}`}
                        className="font-semibold text-sky-700 hover:underline"
                        onClick={() => {
                          void act({ kind: ActionKind.enum.restore, id });
                        }}
                      >
                        Restore
                      </button>
                    </span>
                  ) : (
                    <span>replaced</span>
                  )}
                </header>
                <ToolContext value={readOnlyTools(tools, version)}>
                  <CardBody id={id} md={version.card.md} />
                </ToolContext>
                <Threads threads={version.threads} />
              </section>
            )),
        )}
      </div>
    </aside>
  );
};
