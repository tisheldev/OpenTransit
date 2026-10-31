import { StrictMode, useEffect, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { fixture } from "../api/fixtures";
import type { JourneyResponse } from "../api/types";
import { I18nProvider, useI18n } from "../i18n/I18nProvider";
import "../styles/tokens.css";
import "../styles/global.css";
import { journeyToScene } from "./fromJourney";
import { MapHost } from "./MapHost";
import { emptyScene, setBottomInset, usePublishScene, useMapState, type MapScene } from "./scene";

// Dev-server-only harness for e2e/map.spec.ts (src/map/e2e-harness.html). Query:
// ?lang=he|en&scene=empty|journey|pick. A fake sheet covers the bottom 35% like the shell's peek.

const params = new URLSearchParams(location.search);
const lang = params.get("lang") === "en" ? "en" : "he";
const kind = params.get("scene") ?? "empty";

function Harness() {
  const { t } = useI18n();
  const { center } = useMapState();
  const scene = useMemo<MapScene>(() => {
    if (kind === "journey") {
      const body = fixture("recorded-journey-routes").body as { data: JourneyResponse["data"] };
      const journey = body.data.journeys[0]!;
      return { ...emptyScene, ...journeyToScene(journey, { activeLeg: 2, destinationLabel: "Technion" }), camera: "fit" };
    }
    if (kind === "pick") return { ...emptyScene, pick: true };
    return emptyScene;
  }, []);
  usePublishScene(scene);
  useEffect(() => {
    const report = () => setBottomInset(Math.round(window.innerHeight * 0.35));
    report();
    window.addEventListener("resize", report);
    return () => window.removeEventListener("resize", report);
  }, []);

  return (
    <div style={{ position: "fixed", inset: 0 }}>
      <MapHost />
      <main
        className="harness-sheet"
        data-testid="harness-sheet"
        style={{
          position: "absolute",
          insetInline: 0,
          insetBlockEnd: 0,
          blockSize: "35dvh",
          background: "var(--color-surface)",
          zIndex: 3,
          padding: "var(--space-4)",
        }}
      >
        <h1>{t("app.name")}</h1>
        <p data-testid="harness-center">{center ? center.map((n) => n.toFixed(4)).join(",") : "-"}</p>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider initialLang={lang}>
      <Harness />
    </I18nProvider>
  </StrictMode>,
);
