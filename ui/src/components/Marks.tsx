import { useEffect, useEffectEvent, useState } from "react";
import type { RefObject } from "react";

import { useBoard } from "~/data/context";
import type { TThread } from "~/domain/board";
import { threadsOn } from "~/domain/board";
import { short } from "~/domain/text";
import { unreadOf } from "~/domain/threads";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import { rangeOf } from "~/lib/anchor";
import { markRanges } from "~/lib/highlights";

/** A speech bubble's outline, in a 24 unit box. */
const bubblePath =
  "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z";

type TBubbleMarkProps = {
  id: string;
  thread: TThread;
  unread: number;
  unsent: boolean;
  at: { x: number; y: number };
};

/**
 * The bubble of a thread: filled with the accent and the count of the agent's new comments inside it, or an outline
 * when nothing is new; a comment that the agent does not have yet gives it a dashed outline. A click opens the thread.
 */
const BubbleMark = ({ id, thread, unread, unsent, at }: TBubbleMarkProps) => {
  const { select } = useWhiteboard();
  const words = thread.quote === "" ? "the card" : `“${short(thread.quote)}”`;
  return (
    <button
      type="button"
      data-thread={id}
      data-unsent={unsent ? "" : undefined}
      aria-label={`Thread on ${words}${unread > 0 ? `, ${String(unread)} new from the agent` : ""}${unsent ? ", unsent" : ""}`}
      title={unsent ? "A comment not sent yet" : undefined}
      className={`pointer-events-auto absolute grid size-5 place-items-center rounded-full ${unread > 0 ? "" : "text-ink-faint hover:text-ink-soft"} ${unsent ? "outline-1 outline-offset-1 outline-warning outline-dashed" : ""}`}
      style={{ left: at.x, top: at.y }}
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
        select({ kind: SelectionKind.enum.thread, id });
      }}
    >
      {unread > 0 ? (
        <svg viewBox="0 0 24 24" aria-hidden className="block size-5">
          <path d={bubblePath} className="fill-accent" />
          <text
            x="12"
            y="10.2"
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-on-accent font-sans text-[11px] font-semibold"
          >
            {unread}
          </text>
        </svg>
      ) : (
        <svg
          viewBox="0 0 24 24"
          aria-hidden
          className="block size-3.5 fill-none stroke-current stroke-2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d={bubblePath} />
        </svg>
      )}
    </button>
  );
};

type TPlaced = { id: string; thread: TThread; x: number; y: number };

/** The rects that show where the words are: theirs, or the heading's of the outermost folded section they are in. */
const findShownRects = (range: Range): DOMRect[] => {
  let heading: Element | null = null;
  for (
    let section = range.startContainer.parentElement?.closest("[data-folded]");
    section != null;
    section = section.parentElement?.closest("[data-folded]")
  )
    heading = section.querySelector(":scope > [data-section-heading]");
  if (heading === null) return [...range.getClientRects()];
  const shown = document.createRange();
  shown.selectNodeContents(heading);
  return [...shown.getClientRects()];
};

type TThreadMarksProps = {
  card: string;
  /** The element that scrolls the card's text, which the bubbles sit in. */
  body: RefObject<HTMLElement | null>;
  /** What the marks measure again on: the card's text and size. */
  version: string;
  /** Whether the card shows its first line alone, with the bubble of each thread at the top. */
  folded: boolean;
};

/**
 * The marks of the card's threads and arrows: a highlight on the words of each, and the bubble of each thread level
 * with its first line, in the card's right margin, side by side when two share a line, or just after its words when
 * the look puts the marks in line. A thread on the card as a whole has its bubble at the top, each thread of a folded
 * card has its bubble level with the card's one line, and a thread on words in a folded section has its bubble level
 * with the section's heading.
 */
export const ThreadMarks = ({
  card,
  body,
  version,
  folded,
}: TThreadMarksProps) => {
  const { model } = useBoard();
  const { seen, look } = useWhiteboard();
  const [placed, setPlaced] = useState<TPlaced[]>([]);
  const threads = threadsOn(model.board.threads, card);
  const arrows = Object.values(model.board.arrows).filter(
    (arrow) => arrow.card === card,
  );
  const key = JSON.stringify([
    version,
    folded,
    look.marks,
    threads.map(([id, t]) => [id, t.quote, t.occurrence]),
    arrows.map((a) => [a.quote, a.occurrence]),
  ]);

  /** Measures the words of each thread and arrow, marks them, and places the bubbles. */
  const measure = useEffectEvent((scroller: HTMLElement, root: Element) => {
    const box = scroller.getBoundingClientRect();
    const scale = box.width / scroller.offsetWidth || 1;
    const local = (rect: DOMRect) => ({
      x: (rect.left - box.left) / scale + scroller.scrollLeft,
      y: (rect.top - box.top) / scale + scroller.scrollTop,
      right: (rect.right - box.left) / scale + scroller.scrollLeft,
    });
    const ranges: Range[] = [];
    const lines = new Map<number, number>();
    const next = threads.flatMap(([id, thread]) => {
      const range =
        folded || thread.quote === ""
          ? null
          : rangeOf(root, thread.quote, thread.occurrence);
      if (!folded && thread.quote !== "" && range === null) return [];
      if (range !== null) ranges.push(range);
      // A folded card shows one line, which each bubble is level with.
      const rects = folded
        ? [root.getBoundingClientRect()]
        : range === null
          ? []
          : findShownRects(range);
      const first = rects[0];
      const last = rects.at(-1);
      const top =
        first === undefined
          ? 4
          : local(first).y + (first.height / scale - 20) / 2;
      if (!folded && look.marks === "inline" && last !== undefined) {
        const end = local(last);
        return [{ id, thread, x: end.right + 2, y: end.y - 10 }];
      }
      const line = Math.round(top / 8);
      const count = lines.get(line) ?? 0;
      lines.set(line, count + 1);
      return [
        {
          id,
          thread,
          // The visible width, as the bubbles themselves widen what scrolls.
          x: scroller.clientWidth - 40 + count * 20,
          y: top,
        },
      ];
    });
    markRanges("thread", card, ranges);
    markRanges(
      "arrow",
      card,
      arrows.flatMap((arrow) => {
        const range =
          folded || arrow.quote === ""
            ? null
            : rangeOf(root, arrow.quote, arrow.occurrence);
        return range === null ? [] : [range];
      }),
    );
    setPlaced(next);
  });

  // The key holds what the marks depend on: the card's text and size, the look, and the words of each thread and arrow.
  useEffect(() => {
    const scroller = body.current;
    const root = scroller?.querySelector("[data-text-root]");
    if (scroller == null || root == null) return;
    const remeasure = () => {
      measure(scroller, root);
    };
    remeasure();
    const observer = new ResizeObserver(remeasure);
    observer.observe(root);
    return () => {
      observer.disconnect();
      markRanges("thread", card, []);
      markRanges("arrow", card, []);
    };
  }, [key, body, card]);

  return placed.map(({ id, thread, x, y }) => {
    const live = model.board.threads[id] ?? thread;
    return (
      <BubbleMark
        key={id}
        id={id}
        thread={live}
        unread={unreadOf(live, seen[id])}
        unsent={live.comments.some(({ id: said }) =>
          model.unsent.ids.has(said),
        )}
        at={{ x, y }}
      />
    );
  });
};
