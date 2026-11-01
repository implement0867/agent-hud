import type { ComponentProps } from "react";
import type { ExtraProps } from "react-markdown";

import { FoldButton } from "~/components/FoldButton";
import { useCardFolds } from "~/components/markdown/contexts";
import { textOf } from "~/domain/text";
import { invariant } from "~/lib/invariant";
import { hasProperty, readTextProperty } from "~/lib/properties";

/** A section of the card, which shows its heading alone while it is folded. */
export const Section = ({
  node,
  children,
  ...props
}: ComponentProps<"section"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  const { sections } = useCardFolds();
  const folded =
    hasProperty(node, "dataSection") &&
    sections.includes(readTextProperty(node, "dataSection"));
  return (
    <section {...props} data-folded={folded ? "" : undefined}>
      {children}
    </section>
  );
};

type TSectionFoldButtonProps = { section: string; title: string };

/** The triangle before a heading that folds its section to the heading. */
const SectionFoldButton = ({ section, title }: TSectionFoldButtonProps) => {
  const folds = useCardFolds();
  return (
    <FoldButton
      folded={folds.sections.includes(section)}
      label={`the section ${title}`}
      toggle={() => {
        folds.toggleSection(section);
      }}
      className="mr-1.5 -ml-0.5 inline-grid h-lh w-4 align-top"
    />
  );
};

export type THeadingTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6";

type THeadingProps = ComponentProps<THeadingTag> &
  ExtraProps & { tag: THeadingTag };

/**
 * A heading, with the triangle that folds its section. A heading that is the card's first block has the card's own
 * triangle instead, in the card's left padding, level with the heading's line.
 */
export const Heading = ({
  tag: Tag,
  node,
  children,
  ...props
}: THeadingProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  const folds = useCardFolds();
  return (
    <Tag {...props}>
      {hasProperty(node, "dataLeadHeading") && (
        <FoldButton
          folded={false}
          label={folds.label}
          toggle={folds.toggleCard}
          className="-ml-(--pad) inline-grid h-lh w-(--pad) align-top"
        />
      )}
      {hasProperty(node, "dataSectionHeading") && (
        <SectionFoldButton
          section={readTextProperty(node, "dataSectionHeading")}
          title={textOf(node)}
        />
      )}
      {children}
    </Tag>
  );
};
