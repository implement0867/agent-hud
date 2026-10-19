import { assertNever } from "~/lib/assertNever";
import { ListBody } from "~/primitives/ListBody";
import { TableBody } from "~/primitives/TableBody";
import { TextBody } from "~/primitives/TextBody";
import type { BoxEl } from "~/protocol/schema";

export const Body = ({ el }: { el: BoxEl }) => {
  switch (el.kind) {
    case "text":
      return <TextBody el={el} />;
    case "list":
      return <ListBody el={el} />;
    case "table":
      return <TableBody el={el} />;
    default:
      return assertNever(el);
  }
};
