import { memo } from "react";
import type { ComponentProps } from "react";
import type { Components, ExtraProps } from "react-markdown";
import type { Pluggable } from "unified";

import { Anchor } from "~/components/markdown/Anchor";
import {
  Cell,
  HeaderCell,
  TaskBox,
  VersionCell,
  VersionTaskBox,
} from "~/components/markdown/Boxes";
import { CardMarkdown } from "~/components/markdown/CardMarkdown";
import { Pre, Span } from "~/components/markdown/Code";
import { BoxToggleContext, FoldContext } from "~/components/markdown/contexts";
import type { TToggleBox } from "~/components/markdown/contexts";
import { Heading, Section } from "~/components/markdown/Sections";
import type { THeadingTag } from "~/components/markdown/Sections";
import { markBoxRanges } from "~/lib/boxes";
import { showChanges } from "~/lib/changes";
import type { TDiffStyle } from "~/lib/changes";
import type { TCardFolds } from "~/lib/folds";
import { wrapSections } from "~/lib/sections";

/** The component of a heading of the tag, with the triangle that folds its section. */
const makeHeading = (tag: THeadingTag) => {
  const TagHeading = (props: ComponentProps<THeadingTag> & ExtraProps) => (
    <Heading tag={tag} {...props} />
  );
  return TagHeading;
};

const openCardComponents: Components = {
  section: Section,
  h1: makeHeading("h1"),
  h2: makeHeading("h2"),
  h3: makeHeading("h3"),
  h4: makeHeading("h4"),
  h5: makeHeading("h5"),
  h6: makeHeading("h6"),
  a: Anchor,
  span: Span,
  pre: Pre,
  td: Cell,
  th: HeaderCell,
  input: TaskBox,
};

const versionComponents: Components = {
  a: Anchor,
  span: Span,
  pre: Pre,
  td: VersionCell,
  th: HeaderCell,
  input: VersionTaskBox,
};

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
        components={openCardComponents}
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
  <CardMarkdown
    md={md}
    plugins={[wrapSections]}
    components={versionComponents}
  />
);

/** An earlier version's markdown, whose boxes do not flip and whose sections do not fold. */
export const VersionBody = memo(VersionMarkdown);
