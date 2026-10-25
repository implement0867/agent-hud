import { useCallback, useState } from "react";
import type { PointerEvent, RefObject } from "react";

import type { TAct } from "~/data/boardStore";
import { ActionKind } from "~/domain/actions";
import { newId } from "~/domain/board";
import { SelectionKind } from "~/hooks/useWhiteboard";
import type { TLinking, TWhiteboard } from "~/hooks/useWhiteboard";
import { endOnBoard, pointOnBoard, refAt } from "~/lib/dom";
import { invariant } from "~/lib/invariant";

/**
 * The arrow that the user drags from a part: its loose end follows the pointer, and when the button goes up it links to
 * the part under the pointer, which selects the new arrow for its label. Esc drops it.
 */
export const useLinking = (
  world: RefObject<HTMLElement | null>,
  act: TAct,
  select: TWhiteboard["select"],
) => {
  const [linking, setLinking] = useState<TLinking | null>(null);

  const beginLink = useCallback(
    (from: string, event: PointerEvent) => {
      const root = world.current;
      invariant(root !== null, "parts render in the world");
      const start = endOnBoard(root, from);
      invariant(start !== null, "an arrow starts at a part on the board");
      const follow = (pointer: { clientX: number; clientY: number }) => {
        setLinking({ from, start, to: pointOnBoard(root, pointer) });
      };
      follow(event);
      const listening = new AbortController();
      const { signal } = listening;
      const stop = () => {
        listening.abort();
        setLinking(null);
      };
      window.addEventListener("pointermove", follow, { signal });
      window.addEventListener(
        "pointerup",
        (up) => {
          stop();
          const dst = refAt(up);
          if (dst === null || dst === from) return;
          const id = newId("arrow");
          void act({
            kind: ActionKind.enum.link,
            id,
            src: from,
            dst,
            text: "",
          }).then((taken) => {
            if (taken) select({ kind: SelectionKind.enum.arrow, id });
          });
        },
        { signal },
      );
      window.addEventListener(
        "keydown",
        (key) => {
          if (key.key === "Escape") stop();
        },
        { signal },
      );
    },
    [world, act, select],
  );

  return { linking, beginLink };
};
