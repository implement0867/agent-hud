import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "~/App";
import { invariant } from "~/lib/invariant";
import "~/index.css";

const root = document.getElementById("root");
invariant(root !== null, "index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
