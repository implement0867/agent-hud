import { useCallback, useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";

import { Icon } from "~/chrome/icons";

type AddRowProps = {
  label: string;
  onAdd: (value: string) => void;
  allowEmpty?: boolean;
};

/** "+ Add item" that turns into a one-line input. */
export const AddRow = ({ label, onAdd, allowEmpty = false }: AddRowProps) => {
  const [draft, setDraft] = useState<string | null>(null);
  const open = useCallback(() => {
    if (allowEmpty) onAdd("");
    else setDraft("");
  }, [allowEmpty, onAdd]);
  const onChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setDraft(e.target.value);
  }, []);
  const finish = useCallback(() => {
    if (draft !== null && draft.trim() !== "") onAdd(draft.trim());
    setDraft(null);
  }, [draft, onAdd]);
  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      e.stopPropagation();
      if (e.key === "Enter") finish();
      if (e.key === "Escape") setDraft(null);
    },
    [finish],
  );
  if (draft === null) {
    return (
      <button type="button" className="add-row" onClick={open}>
        <Icon name="plus" size={13} /> {label}
      </button>
    );
  }
  return (
    <input
      className="add-input"
      value={draft}
      onChange={onChange}
      onKeyDown={onKeyDown}
      onBlur={finish}
      placeholder={`${label}… Enter to add`}
      autoFocus
    />
  );
};
