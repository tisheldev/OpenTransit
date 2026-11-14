import { useEffect, useId, useMemo } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { BUS_PATH, CanvasIcon } from "../../map/stops/markers";
import { compassOf } from "../../map/stops/geometry";
import { pickInGroup, type OpenGroup } from "../../map/stops/view";
import { openStop } from "../stop/intent";
import { groupLines, type StopLine } from "../stop/lines";
import { Badge, Due } from "../stop/parts";
import type { HomeStops } from "./homeStops";
import "./stopGroup.css";

// A tapped group, opened (board 9, "Tap a group: pick the stop"; user, 12 November: "open
// its list and zoom in"): the map has zoomed in on the stops, and the sheet lists them by
// direction of travel with their lines and next departure. The row picked is highlighted
// and its marker becomes the chosen one; tapping the picked row again opens its stop.
// Departures come from Home's one nearby-departures answer around the group.

/** The name the stops share before "/" (stops at one junction: "דיזנגוף סנטר/…"), else the first one's. */
export function groupName(names: readonly (string | null)[]): string {
  const heads = names.map((name) => (name ?? "").split("/")[0]!.trim()).filter(Boolean);
  if (heads.length === 0) return "";
  const counts = new Map<string, number>();
  for (const head of heads) counts.set(head, (counts.get(head) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]![0];
}

interface Row {
  stopId: string;
  name: string;
  direction: string | null;
  lines: StopLine[];
  next: string | null;
}

export function StopGroupList({ group, nearby, now }: { group: OpenGroup; nearby: HomeStops; now: Date }) {
  const { t } = useI18n();
  const hintId = useId();
  const rows = useMemo<Row[]>(() => {
    const list = group.stops.map((stop) => {
      const index = nearby.stops.findIndex((item) => item.stopId === stop.stopId);
      const lines =
        index >= 0
          ? groupLines(nearby.departures[index] ?? [], nearby.routes[index] ?? [], { trainLabel: t("stop.train"), now: new Date(0) })
          : [];
      const compass = compassOf(stop.bearingDegrees);
      return {
        stopId: stop.stopId,
        name: stop.name?.trim() || t("stops.unnamed"),
        direction: compass ? t(`stops.dir.${compass}`) : null,
        lines,
        next: lines[0]?.next ?? null,
      };
    });
    // Soonest departure first; stops without one keep their order at the end.
    return list.sort((a, b) => (a.next === null ? 1 : 0) - (b.next === null ? 1 : 0) || (a.next && b.next ? Date.parse(a.next) - Date.parse(b.next) : 0));
  }, [group.stops, nearby.stops, nearby.departures, nearby.routes, t]);

  // The first row is picked when the group opens (as drawn).
  const first = rows[0]?.stopId ?? null;
  useEffect(() => {
    if (group.picked === null && first) pickInGroup(first);
  }, [group.picked, first]);

  const title = t("stops.group.title", { name: groupName(group.stops.map((stop) => stop.name)) || t("stops.unnamed"), count: group.stops.length });
  return (
    <section className="stop-group" aria-label={t("stops.group.list")}>
      <div className="stop-group__head">
        <h1 className="stop-group__title">
          <bdi>{title}</bdi>
        </h1>
        <span className="b-mu">{t("stops.group.ask")}</span>
      </div>
      <ul className="stop-group__rows">
        {rows.map((row) => {
          const picked = row.stopId === group.picked;
          // Distinct line numbers, as the badges on the board.
          const badges = row.lines.filter((line, index, all) => all.findIndex((other) => other.label === line.label) === index).slice(0, 4);
          return (
            <li key={row.stopId}>
              <button
                type="button"
                className={`stop-group__row${picked ? " stop-group__row--picked" : ""}`}
                aria-pressed={picked}
                aria-describedby={picked ? hintId : undefined}
                onClick={() => (picked ? openStop(row.stopId) : pickInGroup(row.stopId))}
              >
                <span className="stop-group__sign" aria-hidden="true">
                  <CanvasIcon path={BUS_PATH} />
                </span>
                <span className="stop-group__text">
                  <span className="stop-group__name">
                    <bdi>{row.name}</bdi>
                  </span>
                  <span className="stop-group__lines">
                    {row.direction && <span className="b-mu">{row.direction}</span>}
                    {badges.map((line) => (
                      <Badge key={line.key} line={line} />
                    ))}
                  </span>
                </span>
                {row.next && <Due instant={row.next} now={now} />}
              </button>
            </li>
          );
        })}
      </ul>
      <span id={hintId} className="visually-hidden">
        {t("stops.group.openHint")}
      </span>
      <p className="b-mu stop-group__note">{t("stop.scheduled")}</p>
    </section>
  );
}
