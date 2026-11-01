import { useMemo } from "react";

import { FoldButton } from "~/components/FoldButton";
import { assertNever } from "~/lib/assertNever";
import type { TCardFolds } from "~/lib/folds";
import { FrameMode } from "~/lib/frame";
import type { TFrameMode } from "~/lib/frame";
import { startsWithHeading } from "~/lib/sections";

type TCardFoldButtonProps = { mode: TFrameMode; md: string; folds: TCardFolds };

/**
 * The triangle that folds the card, in its left padding, level with its first line. An open card whose first block is
 * a heading has the triangle on the heading instead, and the editor has none.
 */
export const CardFoldButton = ({ mode, md, folds }: TCardFoldButtonProps) => {
  const leadHeading = useMemo(() => startsWithHeading(md), [md]);
  const button = (folded: boolean) => (
    <FoldButton
      folded={folded}
      label={folds.label}
      toggle={folds.toggleCard}
      className="absolute top-(--pad-y) left-0 z-10 h-[calc(var(--text-body)*var(--lh))] w-(--pad)"
    />
  );
  switch (mode) {
    case FrameMode.enum.open:
      return leadHeading ? null : button(false);
    case FrameMode.enum.folded:
      return button(true);
    case FrameMode.enum.editing:
      return null;
    default:
      return assertNever(mode);
  }
};
