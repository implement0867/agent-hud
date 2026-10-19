import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { invariant } from "~/lib/invariant";

const root = document.getElementById("root");
invariant(root !== null, "index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <h1>agent-hud</h1>
  </StrictMode>,
);
