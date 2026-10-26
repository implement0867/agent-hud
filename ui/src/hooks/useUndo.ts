import { useCallback, useEffect, useState } from "react";
import { z } from "zod";

import type { TAct } from "~/data/boardStore";
import { ActionKind } from "~/domain/actions";
import type { TArrow, TPoint } from "~/domain/board";
import { assertNever } from "~/lib/assertNever";

export const RemovedKind = z
  .enum(["card", "arrow"])
  .describe("What the user removed last");

/** The last card the user removed, with where it was, or the last arrow. */
export type TRemoved =
  | { kind: typeof RemovedKind.enum.card; id: string; at: TPoint | null }
  | { kind: typeof RemovedKind.enum.arrow; id: string; arrow: TArrow };

/** Removes cards and arrows, and offers the last one back for eight seconds: a card returns where it was, an arrow links again. */
export const useUndo = (act: TAct) => {
  const [removed, setRemoved] = useState<TRemoved | null>(null);

  useEffect(() => {
    if (removed === null) return;
    const timer = setTimeout(() => {
      setRemoved(null);
    }, 8000);
    return () => {
      clearTimeout(timer);
    };
  }, [removed]);

  const remove = useCallback(
    (id: string, at: TPoint | null) => {
      void act({ kind: ActionKind.enum.remove, id }).then((taken) => {
        if (taken) setRemoved({ kind: RemovedKind.enum.card, id, at });
      });
    },
    [act],
  );

  /** Resolves true when the server took the unlink. */
  const unlink = useCallback(
    async (id: string, arrow: TArrow) => {
      const taken = await act({ kind: ActionKind.enum.unlink, id });
      if (taken) setRemoved({ kind: RemovedKind.enum.arrow, id, arrow });
      return taken;
    },
    [act],
  );

  const restore = (offer: TRemoved) => {
    setRemoved(null);
    switch (offer.kind) {
      case RemovedKind.enum.arrow: {
        const { card, quote, occurrence, dst, text } = offer.arrow;
        void act({
          kind: ActionKind.enum.link,
          id: offer.id,
          card,
          quote,
          occurrence: quote === "" ? null : occurrence,
          dst,
          text,
        });
        return;
      }
      case RemovedKind.enum.card: {
        const { id, at } = offer;
        void act({ kind: ActionKind.enum.restore, id }).then((taken) => {
          if (taken && at !== null)
            void act({ kind: ActionKind.enum.move, id, ...at });
        });
        return;
      }
      default:
        assertNever(offer);
    }
  };

  return { removed, remove, unlink, restore };
};
