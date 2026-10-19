import { memo } from "react";

import { Anchor } from "~/feedback/Anchor";
import { AddRow } from "~/primitives/AddRow";
import { Editable } from "~/primitives/Editable";
import { Markdown } from "~/primitives/Markdown";
import type { ListEl, ListItem } from "~/protocol/schema";
import { useSend } from "~/store/socket";

export const ListBody = memo(({ el }: { el: ListEl }) => {
  const send = useSend();
  return (
    <div className="list-body">
      <ol className="items">
        {el.items.map((item, n) => (
          <Item
            key={item.id}
            el={el}
            item={item}
            marker={el.ordered ? `${String(n + 1)}.` : "•"}
          />
        ))}
      </ol>
      <AddRow
        label="Add item"
        onAdd={(value) => {
          send({ t: "add", id: el.id, value });
        }}
      />
    </div>
  );
});
ListBody.displayName = "ListBody";

type ItemProps = { el: ListEl; item: ListItem; marker: string };

const Item = memo(({ el, item, marker }: ItemProps) => {
  const send = useSend();
  return (
    <li className="item">
      <Anchor
        el={el}
        anchor={item.id}
        onRemove={() => {
          send({ t: "remove", id: el.id, anchor: item.id });
        }}
      >
        <div className="item-row">
          <span className="item-marker">{marker}</span>
          <Editable
            value={item.text}
            className="item-text"
            onCommit={(value) => {
              if (value.trim() !== "")
                send({ t: "edit", id: el.id, anchor: item.id, value });
            }}
          >
            <Markdown text={item.text} inline />
          </Editable>
          {item.author === "user" ? <span className="by-user">you</span> : null}
        </div>
      </Anchor>
    </li>
  );
});
Item.displayName = "Item";
