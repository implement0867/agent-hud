import { useState } from "react";
import type { RefObject } from "react";

import { invariant } from "~/lib/invariant";

/** Whether the element scrolls past its top and short of its bottom, measured again on each call of measureEnds. */
export const useScrollEnds = (scroller: RefObject<HTMLElement | null>) => {
  const [ends, setEnds] = useState({ top: false, bottom: false });
  const measureEnds = () => {
    const element = scroller.current;
    invariant(
      element !== null,
      "the scroller measures its ends once it mounts",
    );
    const next = {
      top: element.scrollTop > 1,
      bottom:
        element.scrollHeight - element.scrollTop - element.clientHeight > 1,
    };
    if (next.top !== ends.top || next.bottom !== ends.bottom) setEnds(next);
  };
  return { ends, measureEnds };
};
