import { boardListSchema } from "~/domain/events";
import type { TBoardList } from "~/domain/events";

/** The name of the board that the page shows, from the board query parameter of its URL; null without one. */
export const boardInUrl = () =>
  new URLSearchParams(window.location.search).get("board");

/** The page's URL for a board, with the token kept. */
export const linkTo = (name: string) => {
  const url = new URL(window.location.href);
  url.searchParams.set("board", name);
  return url.toString();
};

/** Every board on the server, as /boards lists them; /boards takes the token of the page's URL. */
export const fetchBoards = async (): Promise<TBoardList> => {
  const url = new URL(`/boards${window.location.search}`, window.location.href);
  const response = await fetch(url);
  return boardListSchema.parse(await response.json());
};
