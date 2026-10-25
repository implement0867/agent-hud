import { Trash2 } from "lucide-react";
import { useLayoutEffect, useState } from "react";
import type { RefObject } from "react";

import { useBoard, useStore } from "~/data/context";
import { ActionKind, Author } from "~/domain/actions";
import type { TArrow, TPoint } from "~/domain/board";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import type { TLinking } from "~/hooks/useWhiteboard";
import { endOnBoard } from "~/lib/dom";
import { arrowCurve } from "~/lib/geometry";

/** An arrow as measured on the board: its path and the middle of the path, where its label goes. */
type TDrawn = {
  id: string;
  arrow: TArrow;
  path: string;
  middle: TPoint;
};

type TArrowTone = "rest" | "selected" | "drawing";

const strokeTones: Record<TArrowTone, string> = {
  rest: "stroke-ink-muted",
  selected: "stroke-accent",
  drawing: "stroke-draw",
};

const headTones: Record<TArrowTone, string> = {
  rest: "fill-ink-muted",
  selected: "fill-accent",
  drawing: "fill-draw",
};

type TArrowLabelProps = { drawn: TDrawn; selected: boolean };

/** The label of an arrow: a button that selects the arrow, or, while it is selected, an input for the text and a remove button. */
const ArrowLabel = ({
  drawn: { id, arrow, middle },
  selected,
}: TArrowLabelProps) => {
  const store = useStore();
  const { select, unlink } = useWhiteboard();
  const [text, setText] = useState(arrow.text);
  const relabel = () => {
    if (text !== arrow.text)
      void store.act({
        kind: ActionKind.enum.link,
        id,
        src: arrow.src,
        dst: arrow.dst,
        text,
      });
  };
  if (!selected)
    return arrow.text === "" ? null : (
      <button
        type="button"
        aria-label={`Arrow ${id}: ${arrow.text}`}
        className="pointer-events-auto absolute -translate-x-1/2 -translate-y-[calc(100%+4px)] cursor-pointer rounded-full bg-surface px-2 py-0.5 text-xs whitespace-nowrap text-ink-soft shadow-sm ring-1 ring-outline hover:ring-accent-ring"
        style={{ left: middle.x, top: middle.y }}
        onPointerDown={(event) => {
          event.stopPropagation();
        }}
        onClick={(event) => {
          event.stopPropagation();
          select({ kind: SelectionKind.enum.arrow, id });
        }}
      >
        {arrow.text}
      </button>
    );
  return (
    <span
      className="pointer-events-auto absolute z-10 flex -translate-x-1/2 -translate-y-[calc(100%+4px)] animate-pop items-center gap-1 rounded-full bg-surface py-0.5 pr-0.5 pl-2 shadow-md ring-2 ring-accent-ring"
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
        autoFocus
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
        className="grid size-5 place-items-center rounded-full text-ink-faint hover:bg-danger-faint hover:text-danger"
        onPointerDown={(event) => {
          event.preventDefault();
        }}
        onClick={() => {
          unlink(id);
        }}
      >
        <Trash2 className="size-3" />
      </button>
    </span>
  );
};

type TArrowLayerProps = {
  world: RefObject<HTMLDivElement | null>;
  /** The arrow that the user draws, which follows the pointer. */
  linking: TLinking | null;
};

/**
 * The arrows between parts, measured from the cards whenever the board or a card's size changes, with each label above
 * the middle of its arrow. A click on an arrow or its label selects it, to label or remove it. The arrows and their
 * labels paint under the cards, so that neither covers a card's controls; the selected label paints over them, with
 * its input.
 */
export const ArrowLayer = ({ world, linking }: TArrowLayerProps) => {
  const { model } = useBoard();
  const { selection, select } = useWhiteboard();
  const [drawn, setDrawn] = useState<TDrawn[]>([]);

  useLayoutEffect(() => {
    const root = world.current;
    if (root === null) return;
    const measure = () => {
      setDrawn(
        Object.entries(model.board.arrows).flatMap(([id, arrow]) => {
          const from = endOnBoard(root, arrow.src);
          const to = endOnBoard(root, arrow.dst);
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
  }, [model, world]);

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
          {Object.entries(headTones).map(([tone, fill]) => (
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
              <path d="M 0 1 L 9 5 L 0 9 z" className={fill} />
            </marker>
          ))}
        </defs>
        {drawn.map(({ id, arrow, path }) => {
          const tone: TArrowTone = id === selectedId ? "selected" : "rest";
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
                className={`fill-none ${strokeTones[tone]}`}
                strokeWidth={tone === "selected" ? 2.5 : 1.75}
                strokeDasharray={
                  arrow.author === Author.enum.agent ? "6 5" : undefined
                }
                strokeLinecap="round"
                markerEnd={`url(#head-${tone})`}
              />
            </g>
          );
        })}
        {band !== null && (
          <path
            d={band}
            className={`fill-none ${strokeTones.drawing}`}
            strokeWidth={2}
            strokeDasharray="4 4"
            markerEnd="url(#head-drawing)"
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
