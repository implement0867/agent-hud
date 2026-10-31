import type { ComponentProps } from "react";
import type { ExtraProps } from "react-markdown";

import { textOf } from "~/domain/text";
import { assertNever } from "~/lib/assertNever";
import { DiffKind } from "~/lib/codeLines";
import { invariant } from "~/lib/invariant";
import { readTextProperty } from "~/lib/properties";

/** The tint of a line of a diff, or none for a line that is no diff's. */
const findDiffTone = (diff: string | undefined) => {
  if (diff === undefined) return "";
  const kind = DiffKind.parse(diff);
  switch (kind) {
    case DiffKind.enum.add:
      return "bg-ins-bg";
    case DiffKind.enum.remove:
      return "bg-del-bg";
    default:
      return assertNever(kind);
  }
};

/** A line of code, a row of the block that does not wrap: its number when the fence gives a file or a first line, and a tint in a diff. */
export const Span = ({
  node,
  children,
  className,
  style,
}: ComponentProps<"span"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  if (node.properties["dataCodeLine"] !== undefined) {
    const diff = readTextProperty(node, "dataDiff");
    return (
      <span
        data-code-line=""
        data-diff={diff}
        className={`block min-h-[1lh] px-3 whitespace-pre ${findDiffTone(diff)}`}
      >
        {children}
      </span>
    );
  }
  if (node.properties["dataLineNumber"] !== undefined)
    return (
      <span
        data-chrome=""
        className="mr-3 inline-block w-7 text-right text-ink-ghost select-none"
      >
        {children}
      </span>
    );
  if (node.properties["dataSign"] !== undefined)
    return (
      <span
        className={
          textOf(node) === "+" ? "text-success-strong" : "text-danger-strong"
        }
      >
        {children}
      </span>
    );
  return (
    <span className={className} style={style}>
      {children}
    </span>
  );
};

/** A code block on the sunken ground, with the file's name above it when the fence gives one; long lines scroll sideways. */
export const Pre = ({ node, children }: ComponentProps<"pre"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  const file = readTextProperty(node, "dataFile");
  return (
    <figure className="my-3">
      {file !== undefined && (
        <figcaption
          data-chrome=""
          className="mb-1 font-mono text-[0.75em] leading-[1.45] text-ink-muted"
        >
          {file}
        </figcaption>
      )}
      <pre className="my-0 overflow-x-auto rounded-code bg-surface-sunken py-2 font-mono text-[0.875em] leading-[1.625] text-ink-soft">
        {children}
      </pre>
    </figure>
  );
};
