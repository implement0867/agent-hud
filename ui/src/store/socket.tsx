import { createContext, useContext } from "react";

import type { ClientMsg } from "~/protocol/schema";

export type Send = (msg: ClientMsg) => void;

export const SocketContext = createContext<Send | null>(null);

export const useSend = (): Send => {
  const send = useContext(SocketContext);
  if (send === null)
    throw new Error("useSend must be used inside SocketContext");
  return send;
};
