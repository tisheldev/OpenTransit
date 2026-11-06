import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createQueryClient } from "./api/queries";
import { App } from "./App";
import { applyTheme, getTheme } from "./lib/theme";
import "./styles/tokens.css";
import "./styles/design-system/bundle.css";
import "./styles/global.css";
import "./styles/shell.css";

async function start() {
  // public/theme.js set it before first paint; this keeps it right if that script failed.
  applyTheme(getTheme());
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
