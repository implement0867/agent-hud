import { memo } from "react";
import type { Pluggable } from "unified";

import { CardMarkdown } from "~/components/markdown/CardMarkdown";
import { BoxToggleContext, FoldContext } from "~/components/markdown/contexts";
import type { TToggleBox } from "~/components/markdown/contexts";
import { markBoxRanges } from "~/lib/boxes";
import { showChanges } from "~/lib/changes";
import type { TDiffStyle } from "~/lib/changes";
import type { TCardFolds } from "~/lib/folds";
import { wrapSections } from "~/lib/sections";

type TCardBodyProps = {
  md: string;
  before: string | null;
  diffStyle: TDiffStyle;
  toggle: TToggleBox;
  folds: TCardFolds;
};

const OpenCardMarkdown = ({
  md,
  before,
  diffStyle,
  toggle,
  folds,
}: TCardBodyProps) => (
  <FoldContext value={folds}>
    <BoxToggleContext value={toggle}>
      <CardMarkdown
        md={md}
        plugins={[
          markBoxRanges,
          wrapSections,
          ...(before === null
            ? []
            : [
                [showChanges, { before, style: diffStyle }] satisfies Pluggable,
              ]),
        ]}
      />
    </BoxToggleContext>
  </FoldContext>
);

/**
 * The open card's markdown: a click on a box flips it, each heading's triangle folds its section, and, with the
 * markdown before, the changes since it show.
 */
export const CardBody = memo(OpenCardMarkdown);

const VersionMarkdown = ({ md }: { md: string }) => (
  <CardMarkdown md={md} plugins={[]} />
);

/** An earlier version's markdown, whose boxes do not flip and whose sections do not fold. */
export const VersionBody = memo(VersionMarkdown);
