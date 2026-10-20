import { useState } from "react";

export const SendForm = ({ send }: { send: (message: string) => void }) => {
  const [message, setMessage] = useState("");
  return (
    <div className="flex gap-2">
      <textarea
        className="flex-1 rounded-lg border border-stone-300 bg-white p-2"
        placeholder="Message to the agent"
        aria-label="Message to the agent"
        value={message}
        onChange={(event) => {
          setMessage(event.target.value);
        }}
      />
      <button
        type="button"
        className="rounded-lg bg-stone-800 px-4 text-white hover:bg-stone-700"
        onClick={() => {
          send(message);
          setMessage("");
        }}
      >
        Send
      </button>
    </div>
  );
};
