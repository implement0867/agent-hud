import { useState } from "react";

import { Icon } from "~/chrome/icons";

type AddRowProps = {
  label: string;
  onAdd: (value: string) => void;
  /** Add an empty entry at once instead of asking for text. */
  allowEmpty?: boolean;
};

export const AddRow = ({ label, onAdd, allowEmpty = false }: AddRowProps) => {
  const [draft, setDraft] = useState<string | null>(null);
  const finish = () => {
    if (draft !== null && draft.trim() !== "") onAdd(draft.trim());
    setDraft(null);
  };
  if (draft === null) {
    return (
      <button
        type="button"
        className="add-row"
        onClick={() => {
          if (allowEmpty) onAdd("");
          else setDraft("");
        }}
      >
        <Icon name="plus" size={13} /> {label}
      </button>
    );
  }
  return (
    <input
      className="add-input"
      value={draft}
      onChange={(e) => {
        setDraft(e.target.value);
      }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") finish();
        if (e.key === "Escape") setDraft(null);
      }}
      onBlur={finish}
      placeholder={`${label}… Enter to add`}
      autoFocus
    />
  );
};
