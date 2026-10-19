import { memo } from "react";

import { Editable } from "~/primitives/Editable";
import { Markdown } from "~/primitives/Markdown";
import type { TextEl } from "~/protocol/schema";
import { useSend } from "~/store/socket";

export const TextBody = memo(({ el }: { el: TextEl }) => {
  const send = useSend();
  return (
    <div className="text-body">
      <Editable
        value={el.body}
        placeholder="Empty"
        onCommit={(value) => {
          send({ t: "edit", id: el.id, anchor: "", value });
        }}
      >
        <Markdown text={el.body} />
      </Editable>
    </div>
  );
});
TextBody.displayName = "TextBody";
