import { useContext } from "react";
import type { ComponentProps } from "react";
import type { ExtraProps } from "react-markdown";

import { BoxToggleContext } from "~/components/markdown/contexts";
import { textOf } from "~/domain/text";
import { readBoxRange } from "~/lib/boxes";
import type { TBoxRange } from "~/lib/boxes";
import { invariant } from "~/lib/invariant";

type TBoxProps = { checked: boolean; range: TBoxRange | null };

/** A box of the markdown as a checkbox; a click flips it in the markdown, which the agent gets as an edit. */
const Box = ({ checked, range }: TBoxProps) => {
  const toggle = useContext(BoxToggleContext);
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

/** The box of a task item. */
export const TaskBox = ({
  node,
  checked,
}: ComponentProps<"input"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  return <Box checked={checked === true} range={readBoxRange(node)} />;
};

/** A cell of a box alone shows a checkbox, and an empty cell a dash. */
export const Cell = ({ node, children }: ComponentProps<"td"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  if (node.properties["dataBox"] !== undefined)
    return (
      <td className="w-6">
        <Box
          checked={/x/i.test(node.children.map(textOf).join(""))}
          range={readBoxRange(node)}
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

/** A header cell over a column of boxes has no title. */
export const HeaderCell = ({
  node,
  children,
}: ComponentProps<"th"> & ExtraProps) => {
  invariant(node !== undefined, "react-markdown passes each element's node");
  return node.properties["dataBox"] !== undefined ? (
    <th className="w-6" />
  ) : (
    <th>{children}</th>
  );
};
