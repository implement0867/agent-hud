import { useCallback, useState } from "react";
import type { RefObject } from "react";

import type { TAct } from "~/data/boardStore";
import { ActionKind } from "~/domain/actions";
import { newId } from "~/domain/board";
import type { TAnchor, TPoint } from "~/domain/board";
import { SelectionKind } from "~/hooks/useWhiteboard";
import type { TLinking, TWhiteboard } from "~/hooks/useWhiteboard";
import { cardAt, pointOnBoard } from "~/lib/dom";
import { invariant } from "~/lib/invariant";

/**
 * The arrow that the user draws from words of a card: it starts at the end of the words and its loose end follows the
 * pointer; the card under the pointer shows as the drop target, and a press on it links the words to that card and
 * selects the new arrow for its label. A press elsewhere, or Esc, drops the arrow.
 */
export const useLinking = (
  world: RefObject<HTMLElement | null>,
  act: TAct,
  select: TWhiteboard["select"],
) => {
  const [linking, setLinking] = useState<TLinking | null>(null);

  const beginLink = useCallback(
    (
      from: TAnchor,
      start: TPoint,
      pointer: { clientX: number; clientY: number },
    ) => {
      const root = world.current;
      invariant(root !== null, "cards render in the world");
      const follow = (at: { clientX: number; clientY: number }) => {
        setLinking({
          from,
          start,
          to: pointOnBoard(root, at),
          over: cardAt(at),
        });
      };
      follow(pointer);
      const listening = new AbortController();
      const { signal } = listening;
      const stop = () => {
        listening.abort();
        setLinking(null);
      };
      window.addEventListener("pointermove", follow, { signal });
      window.addEventListener(
        "pointerdown",
        (down) => {
          down.preventDefault();
          down.stopPropagation();
          stop();
          const dst = cardAt(down);
          if (dst === null || dst === from.card) return;
          const id = newId("arrow");
          void act({
            kind: ActionKind.enum.link,
            id,
            card: from.card,
            quote: from.quote,
            occurrence: from.quote === "" ? null : from.occurrence,
            dst,
            text: "",
          }).then((taken) => {
            if (taken) select({ kind: SelectionKind.enum.arrow, id });
          });
        },
        { signal, capture: true },
      );
      window.addEventListener(
        "keydown",
        (key) => {
          if (key.key === "Escape") {
            key.stopPropagation();
            stop();
          }
        },
        { signal, capture: true },
      );
    },
    [world, act, select],
  );

  return { linking, beginLink };
};
