import { useMemo } from "react";
import type { RefObject } from "react";

import { ThreadMarks } from "~/components/Marks";
import { firstLine, plainText } from "~/domain/text";

type TFoldedCardProps = {
  id: string;
  md: string;
  body: RefObject<HTMLElement | null>;
};

/** A folded card: the first line of its text that is not blank, with the bubble of each of its threads level with it. */
export const FoldedCard = ({ id, md, body }: TFoldedCardProps) => {
  const line = useMemo(() => firstLine(plainText(md)), [md]);
  return (
    <>
      <div data-text-root="" className="markdown truncate select-text">
        {line}
      </div>
      <ThreadMarks card={id} body={body} version={md} folded />
    </>
  );
};
