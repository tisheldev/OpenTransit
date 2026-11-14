import { VEHICLE_ICONS } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import type { LineItem } from "../../api/lines";
import { operatorColour } from "../../lib/lines";
import { useTheme } from "../../lib/theme";
import { lineMode } from "../../map/layers";
import type { RailKind } from "./lineModel";

/** "רכבת" with the train: a stop where rail can be caught (board 4, `.bdg.rail`). */
export function RailBadge({ kind }: { kind: RailKind }) {
  const { t } = useI18n();
  const icon = VEHICLE_ICONS.train;
  return (
    <span className="sl-rail">
      <svg viewBox={icon.viewBox} aria-hidden="true" focusable="false">
        <path fillRule="evenodd" d={icon.d} />
      </svg>
      <bdi>{kind === "light_rail" ? t("line.lightRail") : t("stop.train")}</bdi>
    </span>
  );
}

/** The line's own colour for its rail in the stop list (the map line's colour for this theme). */
export function useLineColour(line: Pick<LineItem, "mode" | "operatorId" | "operatorName"> | null): string {
  const theme = useTheme();
  if (!line) return "var(--mode-bus)";
  const colour = operatorColour({ mode: line.mode, operatorId: line.operatorId, operatorName: line.operatorName });
  return colour?.line[theme] ?? (lineMode(line.mode) === "rail" ? "var(--mode-rail)" : "var(--mode-bus)");
}

/** "אוטובוס", "רכבת", "רכבת קלה". */
export function useModeName(mode: string): string {
  const { t } = useI18n();
  const value = mode.toLowerCase();
  if (/light_rail|tram|subway|metro/.test(value)) return t("line.mode.lightRail");
  if (/rail|train/.test(value)) return t("line.mode.rail");
  return t("line.mode.bus");
}
