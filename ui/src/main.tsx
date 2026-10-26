import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "~/App";
import { invariant } from "~/lib/invariant";
import { applyLook, readLook } from "~/lib/look";
import "~/index.css";

// The viewer's look applies before the first paint, so that a dark board does not flash light.
applyLook(readLook());

const root = document.getElementById("root");
invariant(root !== null, "index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
