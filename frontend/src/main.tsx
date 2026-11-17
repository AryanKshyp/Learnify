import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ServerStateProvider } from "./api/server-state";
import { AuthGate } from "./auth/AuthGate";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthGate>
      <ServerStateProvider>
        <App />
      </ServerStateProvider>
    </AuthGate>
  </StrictMode>,
);
