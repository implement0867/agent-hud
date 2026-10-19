import { memo, useCallback } from "react";

import { Editable } from "~/primitives/Editable";
import { Markdown } from "~/primitives/Markdown";
import type { TextEl } from "~/protocol/schema";
import { useSend } from "~/store/socket";

export const TextBody = memo(({ el }: { el: TextEl }) => {
  const send = useSend();
  const commit = useCallback(
    (value: string) => {
      send({ t: "edit", id: el.id, anchor: "", value });
    },
    [send, el.id],
  );
  return (
    <div className="text-body">
      <Editable value={el.body} onCommit={commit} placeholder="Empty">
        <Markdown text={el.body} />
      </Editable>
    </div>
  );
});
TextBody.displayName = "TextBody";
