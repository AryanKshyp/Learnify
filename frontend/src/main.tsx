import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ServerStateProvider } from "./api/server-state";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ServerStateProvider>
      <App />
    </ServerStateProvider>
  </StrictMode>,
);
