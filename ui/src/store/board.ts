import { createStore } from "~/lib/store";
import { assertNever } from "~/lib/assertNever";
import type { Element, ServerMsg, Status } from "~/protocol/schema";

export type Connection = "connecting" | "open" | "closed";

export type BoardState = {
  project: string;
  /** Element ids in creation order. */
  order: readonly string[];
  elements: Readonly<Record<string, Element>>;
  status: Status;
  connection: Connection;
  /** Last error the server reported for one of our messages. */
  error: { message: string; at: number } | null;
  /** Ids the agent created since this tab connected, newest last. */
  fresh: readonly string[];
};

export const initialBoard: BoardState = {
  project: "",
  order: [],
  elements: {},
  status: { waiting: false, pending: 0, viewers: 0 },
  connection: "connecting",
  error: null,
  fresh: [],
};

export const reduceBoard = (state: BoardState, msg: ServerMsg): BoardState => {
  switch (msg.t) {
    case "hello":
      return {
        ...state,
        project: msg.project,
        order: msg.elements.map((el) => el.id),
        elements: Object.fromEntries(msg.elements.map((el) => [el.id, el])),
        status: msg.status,
        fresh: [],
      };
    case "upsert": {
      const { element } = msg;
      const known = element.id in state.elements;
      return {
        ...state,
        order: known ? state.order : [...state.order, element.id],
        elements: { ...state.elements, [element.id]: element },
        fresh:
          !known && element.author === "agent"
            ? [...state.fresh, element.id]
            : state.fresh,
      };
    }
    case "gone": {
      if (!(msg.id in state.elements)) return state;
      const { [msg.id]: _gone, ...elements } = state.elements;
      return {
        ...state,
        order: state.order.filter((id) => id !== msg.id),
        elements,
        fresh: state.fresh.filter((id) => id !== msg.id),
      };
    }
    case "status":
      return { ...state, status: msg.status };
    case "error":
      return { ...state, error: { message: msg.message, at: Date.now() } };
    default:
      return assertNever(msg);
  }
};

export const boardStore = createStore<BoardState>(initialBoard);
