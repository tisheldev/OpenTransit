import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { fixture } from "../api/fixtures";
import type { JourneyResponse } from "../api/types";
import { I18nProvider, useI18n } from "../i18n/I18nProvider";
import { applyTheme, getTheme, setTheme, useTheme } from "../lib/theme";
import "../styles/tokens.css";
import "../styles/design-system/bundle.css";
import "../styles/global.css";
import { journeyToScene } from "./fromJourney";
import { MapHost } from "./MapHost";
import { emptyScene, setBottomInset, usePublishScene, useMapState, type LonLat, type MapScene } from "./scene";

// Dev-server-only harness for e2e/map.spec.ts (src/map/e2e-harness.html). Query:
// ?lang=he|en&scene=empty|journey|pick[&active=<leg index>|none][&journey=routes|poi]
// [&focus=leg]. A fake sheet covers the bottom 35% like the shell's peek. The theme is the
// stored one (dark unless light was chosen), and the sheet's button switches it the way
// Settings does.

const params = new URLSearchParams(location.search);
const lang = params.get("lang") === "en" ? "en" : "he";
const kind = params.get("scene") ?? "empty";
const activeParam = params.get("active");
const activeLeg = activeParam === "none" ? null : Number(activeParam ?? 2);
const journeyFixture = params.get("journey") === "poi" ? "recorded-journey-poi" : "recorded-journey-routes";
const focusLeg = params.get("focus") === "leg";

applyTheme(getTheme());

const same = (a: LonLat, b: LonLat) => Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) < 1e-6;

/** The scene the query asks for; built once, so its identity is stable. */
function harnessScene(): MapScene {
  if (kind === "journey") {
    const body = fixture(journeyFixture).body as { data: JourneyResponse["data"] };
    const journey = body.data.journeys[0]!;
    const drawn = journeyToScene(journey, { activeLeg, destinationLabel: "Technion" });
    const leg = activeLeg === null ? undefined : drawn.route[activeLeg];
    if (focusLeg && leg) {
      // Like Navigate: the current leg, the pins at its ends, and the passenger at its start.
      const pins = drawn.pins.filter((pin) => same(pin.position, leg.from) || same(pin.position, leg.to));
      return { ...emptyScene, route: [leg], pins, user: { position: leg.from, accuracyMeters: 25 }, camera: "fit" };
    }
    return { ...emptyScene, ...drawn, camera: "fit" };
  }
  if (kind === "pick") return { ...emptyScene, pick: true };
  return emptyScene;
}
const scene = harnessScene();

function Harness() {
  const { t } = useI18n();
  const theme = useTheme();
  const { center } = useMapState();
  usePublishScene(scene);
  useEffect(() => {
    const report = () => setBottomInset(Math.round(window.innerHeight * 0.35));
    report();
    window.addEventListener("resize", report);
    return () => window.removeEventListener("resize", report);
  }, []);
  const other = theme === "dark" ? "light" : "dark";

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
          background: "var(--surface)",
          color: "var(--ink)",
          zIndex: 3,
          padding: "var(--space-4)",
        }}
      >
        <h1>{t("app.name")}</h1>
        <p data-testid="harness-center">{center ? center.map((n) => n.toFixed(4)).join(",") : "-"}</p>
        <button type="button" className="ot-btn ot-btn--secondary" data-testid="harness-theme" onClick={() => setTheme(other)}>
          {t(`settings.theme.${other}`)}
        </button>
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
