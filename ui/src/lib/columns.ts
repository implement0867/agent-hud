import { z } from "zod";

import { invariant } from "~/lib/invariant";

export const ColumnKind = z.enum([
  "static",
  "text",
  "check",
  "number",
  "select",
]);

export type TColumn = {
  kind: z.infer<typeof ColumnKind>;
  options: string[];
};

/** The title and column a header cell names, as the server reads them: cost {number}, done {check}, note {text}, size {S, M, L}. */
export const columnFromHeader = (
  header: string,
): { title: string; column: TColumn } => {
  const found = /^(.*?)\{([^{}]*)\}\s*$/s.exec(header);
  if (found === null)
    return {
      title: header,
      column: { kind: ColumnKind.enum.static, options: [] },
    };
  const [, title = "", spec = ""] = found;
  const kind = ColumnKind.safeParse(spec.trim());
  if (kind.success && kind.data !== ColumnKind.enum.select)
    return { title: title.trim(), column: { kind: kind.data, options: [] } };
  const options = spec
    .split(",")
    .map((option) => option.trim())
    .filter((option) => option !== "");
  invariant(
    options.length >= 2,
    "the server rejects a select of fewer than two options",
  );
  return {
    title: title.trim(),
    column: { kind: ColumnKind.enum.select, options },
  };
};
