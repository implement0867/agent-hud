import { useCallback } from "react";
import type { RefObject } from "react";

import { CardBody } from "~/components/CardBody";
import { ThreadMarks } from "~/components/Marks";
import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";
import { versionsOf } from "~/domain/board";
import { toggledBox } from "~/domain/text";
import { useWhiteboard } from "~/hooks/useWhiteboard";
import type { TCardFolds } from "~/lib/folds";
import { invariant } from "~/lib/invariant";

type TChangeLinksProps = { id: string; changed: boolean };

/** The links at the right of the card's title line: hide or show the changes of the last version, and the history. */
const ChangeLinks = ({ id, changed }: TChangeLinksProps) => {
  const store = useStore();
  const { openHistory } = useWhiteboard();
  const link =
    "cursor-pointer text-ink-muted hover:text-ink-soft hover:underline";
  return (
    <span
      data-chrome=""
      className="absolute top-[calc(var(--pad-y)+4px)] right-11 z-10 flex gap-1.5 text-[0.6875rem] leading-4 text-ink-muted"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
      }}
    >
      <button
        type="button"
        className={link}
        onClick={(event) => {
          event.stopPropagation();
          if (changed) store.sawChanges(id);
          else store.showChanges(id);
        }}
      >
        {changed ? "Hide changes" : "Show changes"}
      </button>
      <span aria-hidden className="text-ink-ghost">
        ·
      </span>
      <button
        type="button"
        aria-label={`History of ${id}`}
        className={link}
        onClick={(event) => {
          event.stopPropagation();
          openHistory(id);
        }}
      >
        History
      </button>
    </span>
  );
};

type TOpenCardProps = {
  id: string;
  md: string;
  versions: number;
  width: number | null;
  body: RefObject<HTMLElement | null>;
  folds: TCardFolds;
};

/**
 * An open card's markdown with the marks of its threads, and, on a card with earlier versions, the links to its
 * changes and its history. A click on a box puts the card with the box flipped.
 */
export const OpenCard = ({
  id,
  md,
  versions,
  width,
  body,
  folds,
}: TOpenCardProps) => {
  const store = useStore();
  const { model } = useBoard();
  const { look } = useWhiteboard();
  const before = model.changed[id] ?? null;
  const toggle = useCallback(
    (start: number, end: number) => {
      const { board } = store.read();
      const current = board.cards[id];
      invariant(current !== undefined, `card ${id} is on the board`);
      void store.act({
        kind: ActionKind.enum.put,
        id,
        md: toggledBox(current.md, start, end),
        version: versionsOf(board, id),
      });
    },
    [store, id],
  );
  return (
    <>
      {versions > 0 && <ChangeLinks id={id} changed={before !== null} />}
      <div
        key={versions}
        className={`animate-pop ${versions > 0 ? "[&_.markdown>:first-child]:pr-36" : ""}`}
      >
        <CardBody
          md={md}
          before={before}
          diffStyle={look.diff}
          toggle={toggle}
          folds={folds}
        />
      </div>
      <ThreadMarks
        card={id}
        body={body}
        version={`${md}|${String(before)}|${String(width)}|${look.diff}`}
        folded={false}
      />
    </>
  );
};
