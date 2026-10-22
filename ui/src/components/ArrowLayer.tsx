import { Trash2 } from "lucide-react";
import { useLayoutEffect, useState } from "react";
import type { RefObject } from "react";

import { arrowCurve, endOnBoard } from "~/lib/geometry";
import { SelectionKind, useTools } from "~/lib/whiteboard";
import { ActionKind, Author } from "~/schemas/actions";
import type { TArrow, TPoint } from "~/schemas/board";

type TDrawn = {
  id: string;
  arrow: TArrow;
  path: string;
  middle: TPoint;
};

const ArrowLabel = ({
  drawn: { id, arrow, middle },
  selected,
}: {
  drawn: TDrawn;
  selected: boolean;
}) => {
  const { act } = useTools();
  const [text, setText] = useState(arrow.text);
  const relabel = () => {
    if (text !== arrow.text)
      void act({
        kind: ActionKind.enum.link,
        id,
        src: arrow.src,
        dst: arrow.dst,
        text,
      });
  };
  if (!selected)
    return arrow.text === "" ? null : (
      <span
        className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[calc(100%+4px)] rounded-full bg-white px-2 py-0.5 text-xs whitespace-nowrap text-stone-600 shadow-sm ring-1 ring-stone-200"
        style={{ left: middle.x, top: middle.y }}
      >
        {arrow.text}
      </span>
    );
  return (
    <span
      className="pointer-events-auto absolute z-10 flex -translate-x-1/2 -translate-y-[calc(100%+4px)] animate-pop items-center gap-1 rounded-full bg-white py-0.5 pr-0.5 pl-2 shadow-md ring-2 ring-sky-400"
      style={{ left: middle.x, top: middle.y }}
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <input
        aria-label={`Text of arrow ${id}`}
        placeholder="label"
        ref={(element) => {
          element?.focus();
        }}
        className="field-sizing-content min-w-12 bg-transparent text-xs outline-none"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
        onBlur={relabel}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === "Enter") event.currentTarget.blur();
          if (event.key === "Escape") {
            setText(arrow.text);
            event.currentTarget.blur();
          }
        }}
      />
      <button
        type="button"
        aria-label={`Remove arrow ${id}`}
        className="grid size-5 place-items-center rounded-full text-stone-400 hover:bg-rose-50 hover:text-rose-600"
        onPointerDown={(event) => {
          event.preventDefault();
        }}
        onClick={() => {
          void act({ kind: ActionKind.enum.unlink, id });
        }}
      >
        <Trash2 className="size-3" />
      </button>
    </span>
  );
};

/**
 * The arrows between parts, measured from the cards after each render of the board, with each label above the middle of its arrow.
 * A click on an arrow selects it, to label or remove it.
 */
export const ArrowLayer = ({
  world,
  scale,
  layout,
}: {
  world: RefObject<HTMLDivElement | null>;
  scale: number;
  layout: unknown;
}) => {
  const { board, selection, select, linking } = useTools();
  const [drawn, setDrawn] = useState<TDrawn[]>([]);

  useLayoutEffect(() => {
    const root = world.current;
    if (root === null) return;
    const measure = () => {
      setDrawn(
        Object.entries(board.arrows).flatMap(([id, arrow]) => {
          const from = endOnBoard(root, arrow.src, scale);
          const to = endOnBoard(root, arrow.dst, scale);
          return from === null || to === null
            ? []
            : [{ id, arrow, ...arrowCurve(from, to) }];
        }),
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    for (const card of root.querySelectorAll("article")) observer.observe(card);
    return () => {
      observer.disconnect();
    };
  }, [board, world, scale, layout]);

  const band =
    linking === null
      ? null
      : arrowCurve(linking.start, {
          card: { ...linking.to, width: 0, height: 0 },
          y: linking.to.y,
        }).path;

  const selectedId =
    selection?.kind === SelectionKind.enum.arrow ? selection.id : null;
  return (
    <>
      <svg
        className="pointer-events-none absolute top-0 left-0 size-px overflow-visible"
        aria-hidden="true"
      >
        <defs>
          {["stone", "sky", "violet"].map((tone) => (
            <marker
              key={tone}
              id={`head-${tone}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path
                d="M 0 1 L 9 5 L 0 9 z"
                className={
                  tone === "sky"
                    ? "fill-sky-500"
                    : tone === "violet"
                      ? "fill-violet-500"
                      : "fill-stone-500"
                }
              />
            </marker>
          ))}
        </defs>
        {drawn.map(({ id, arrow, path }) => {
          const selected = id === selectedId;
          return (
            <g key={id}>
              <path
                d={path}
                className="pointer-events-[stroke] cursor-pointer fill-none stroke-transparent"
                strokeWidth={16}
                onPointerDown={(event) => {
                  event.stopPropagation();
                }}
                onClick={(event) => {
                  event.stopPropagation();
                  select({ kind: SelectionKind.enum.arrow, id });
                }}
              />
              <path
                d={path}
                className={`fill-none ${selected ? "stroke-sky-500" : "stroke-stone-500"}`}
                strokeWidth={selected ? 2.5 : 1.75}
                strokeDasharray={
                  arrow.author === Author.enum.agent ? "6 5" : undefined
                }
                strokeLinecap="round"
                markerEnd={`url(#head-${selected ? "sky" : "stone"})`}
              />
            </g>
          );
        })}
        {band !== null && (
          <path
            d={band}
            className="fill-none stroke-violet-500"
            strokeWidth={2}
            strokeDasharray="4 4"
            markerEnd="url(#head-violet)"
          />
        )}
      </svg>
      {drawn.map((item) => (
        <ArrowLabel
          key={`${item.id}:${item.arrow.text}`}
          drawn={item}
          selected={item.id === selectedId}
        />
      ))}
    </>
  );
};
