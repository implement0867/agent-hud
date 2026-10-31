import type { ComponentProps, ComponentType, ReactNode } from "react";
import type { ExtraProps } from "react-markdown";
import type { Element } from "hast";

import { useBoxToggle } from "~/components/markdown/contexts";
import { textOf } from "~/domain/text";
import { readBoxRange } from "~/lib/boxes";
import { invariant } from "~/lib/invariant";
import { hasProperty } from "~/lib/properties";

type TBoxProps = { checked: boolean; node: Element };

/** An open card's box as a checkbox; a click flips it in the markdown, which the agent gets as an edit. */
const FlipBox = ({ checked, node }: TBoxProps) => {
  const toggle = useBoxToggle();
  const range = readBoxRange(node);
  return (
    <input
      type="checkbox"
      aria-label="Done"
      checked={checked}
      disabled={range === null}
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.stopPropagation();
      }}
      onChange={() => {
        invariant(range !== null, "a box without a range is disabled");
        toggle(range.start, range.end);
      }}
    />
  );
};

/** An earlier version's box, which shows its state and does not flip. */
const InertBox = ({ checked }: TBoxProps) => (
  <input
    type="checkbox"
    aria-label="Done"
    checked={checked}
    disabled
    onPointerDown={(event) => {
      event.stopPropagation();
    }}
    onClick={(event) => {
      event.stopPropagation();
    }}
  />
);

type TBoxCellProps = ComponentProps<"td"> &
  ExtraProps & {
    Box: ComponentType<TBoxProps>;
  };

/** A cell of a box alone shows the box as a checkbox, and an empty cell a dash. */
const BoxCell = ({ node, children, Box }: TBoxCellProps): ReactNode => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  if (hasProperty(node, "dataBox"))
    return (
      <td className="w-6">
        <Box
          checked={/x/i.test(node.children.map(textOf).join(""))}
          node={node}
        />
      </td>
    );
  return (
    <td>
      {textOf(node).trim() === "" ? (
        <span data-chrome="" className="text-ink-ghost">
          —
        </span>
      ) : (
        children
      )}
    </td>
  );
};

/** The box of an open card's task item. */
export const TaskBox = ({
  node,
  checked,
}: ComponentProps<"input"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  return <FlipBox checked={checked === true} node={node} />;
};

/** The box of an earlier version's task item. */
export const VersionTaskBox = ({
  node,
  checked,
}: ComponentProps<"input"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  return <InertBox checked={checked === true} node={node} />;
};

/** A cell of an open card's table. */
export const Cell = (props: ComponentProps<"td"> & ExtraProps) => (
  <BoxCell {...props} Box={FlipBox} />
);

/** A cell of an earlier version's table. */
export const VersionCell = (props: ComponentProps<"td"> & ExtraProps) => (
  <BoxCell {...props} Box={InertBox} />
);

/** A header cell over a column of boxes has no title. */
export const HeaderCell = ({
  node,
  children,
}: ComponentProps<"th"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  return hasProperty(node, "dataBox") ? (
    <th className="w-6" />
  ) : (
    <th>{children}</th>
  );
};
