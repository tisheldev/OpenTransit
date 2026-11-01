import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createQueryClient } from "./api/queries";
import { App } from "./App";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/shell.css";

async function start() {
  // Fixture mode exists only in the dev server (`vite --mode fixtures`); the condition
  // is constant-folded, so MSW and the fixtures never enter a production build.
  const fixtureMode = import.meta.env.MODE === "fixtures";
  if (fixtureMode) {
    const { startFixtureMode } = await import("./mocks/browser");
    await startFixtureMode();
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App queryClient={createQueryClient()} fixtureMode={fixtureMode} />
    </StrictMode>,
  );
}

void start();
