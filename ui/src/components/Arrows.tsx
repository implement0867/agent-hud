import { useEffect, useState } from "react";
import type { RefObject } from "react";

import type { TBoardSocket } from "~/api/boardSocket";
import { ActionKind } from "~/schemas/actions";
import type { TBoard } from "~/schemas/board";

type TPoint = { x: number; y: number };
type TPath = { id: string; from: TPoint; to: TPoint; text: string };

/** The right end of the first line of the part, in the board's coordinates. */
const anchorOf = (board: HTMLElement, ref: string): TPoint | null => {
  const part = board.querySelector(`[data-ref="${CSS.escape(ref)}"]`);
  if (part === null) return null;
  const box = board.getBoundingClientRect();
  const rect = part.getBoundingClientRect();
  return { x: rect.right - box.left, y: rect.top - box.top + 12 };
};

/** Each arrow curves out to the right of the board, from its source part to its target part. */
export const Arrows = ({
  board,
  container,
  act,
}: {
  board: TBoard;
  container: RefObject<HTMLDivElement | null>;
  act: TBoardSocket["act"];
}) => {
  const [paths, setPaths] = useState<TPath[]>([]);
  useEffect(() => {
    const root = container.current;
    if (root === null) return;
    const measure = () => {
      setPaths(
        Object.entries(board.arrows).flatMap(([id, { src, dst, text }]) => {
          const from = anchorOf(root, src);
          const to = anchorOf(root, dst);
          return from === null || to === null ? [] : [{ id, from, to, text }];
        }),
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    return () => {
      observer.disconnect();
    };
  }, [board, container]);

  return (
    <>
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
        aria-hidden="true"
      >
        <defs>
          <marker
            id="arrowhead"
            viewBox="0 0 10 10"
            refX="10"
            refY="5"
            markerWidth="8"
            markerHeight="8"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" className="fill-stone-500" />
          </marker>
        </defs>
        {paths.map(({ id, from, to }) => {
          const bend = Math.max(from.x, to.x) + 48;
          return (
            <path
              key={id}
              d={`M ${String(from.x)} ${String(from.y)} C ${String(bend)} ${String(from.y)}, ${String(bend)} ${String(to.y)}, ${String(to.x)} ${String(to.y)}`}
              className="fill-none stroke-stone-500"
              strokeWidth={1.5}
              markerEnd="url(#arrowhead)"
            />
          );
        })}
      </svg>
      {paths.map(({ id, from, to, text }) => (
        <div
          key={id}
          className="absolute flex items-center gap-1 text-xs text-stone-600"
          style={{
            left: Math.max(from.x, to.x) + 40,
            top: (from.y + to.y) / 2 - 8,
          }}
        >
          {text}
          <button
            type="button"
            aria-label={`Remove arrow ${id}`}
            className="rounded px-1 text-stone-400 hover:bg-stone-200"
            onClick={() => {
              void act({ kind: ActionKind.enum.unlink, id });
            }}
          >
            ×
          </button>
        </div>
      ))}
    </>
  );
};
