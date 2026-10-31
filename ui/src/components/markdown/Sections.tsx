import { useContext } from "react";
import type { ComponentProps } from "react";
import type { ExtraProps } from "react-markdown";

import { FoldButton } from "~/components/FoldButton";
import { FoldContext } from "~/components/markdown/contexts";
import { textOf } from "~/domain/text";
import { invariant } from "~/lib/invariant";
import { readTextProperty } from "~/lib/properties";

/** A section of the card, which shows its heading alone while it is folded. */
export const Section = ({
  node,
  children,
  ...props
}: ComponentProps<"section"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  const { sections } = useContext(FoldContext);
  const key = readTextProperty(node, "dataSection");
  const folded = key !== undefined && sections.includes(key);
  return (
    <section {...props} data-folded={folded ? "" : undefined}>
      {children}
    </section>
  );
};

type THeadingTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6";

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
  const folds = useContext(FoldContext);
  const key = readTextProperty(node, "dataSectionHeading");
  return (
    <Tag {...props}>
      {readTextProperty(node, "dataLeadHeading") !== undefined && (
        <FoldButton
          folded={false}
          label={folds.label}
          toggle={folds.toggleCard}
          className="-ml-[var(--pad)] inline-grid h-[1lh] w-[var(--pad)] align-top"
        />
      )}
      {key !== undefined && (
        <FoldButton
          folded={folds.sections.includes(key)}
          label={`the section ${textOf(node)}`}
          toggle={() => {
            folds.toggleSection(key);
          }}
          className="mr-1.5 -ml-0.5 inline-grid h-[1lh] w-4 align-top"
        />
      )}
      {children}
    </Tag>
  );
};
