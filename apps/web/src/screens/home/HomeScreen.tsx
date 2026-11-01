import { useId, useMemo } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { formatClock } from "../../lib/time";
import { DEFAULT_CENTER } from "../../map/layers";
import { emptyScene, usePublishScene, type MapPin, type MapScene } from "../../map/scene";
import { useActiveTrip, type ActiveTrip } from "../../nav/activeTrip";
import { choiceFromSaved, type Endpoint } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { go } from "../../router";
import { FromTo } from "../../shell/FromTo";
import { useLocalState } from "../../shell/localStore";
import type { SavedPlace } from "../../storage/local";

// Home — C01 (design: Screens 1). Renders from storage only; the data status banner is
// the shell's and arrives after the first paint. Settings is the gear in the sheet's
// handle row (the shell's), so Home itself holds only the trip being planned.

/** The engine names coordinate ends "START"/"END": never show those as a place. */
function journeyEndName(trip: ActiveTrip): string | null {
  if (trip.labels?.destination) return trip.labels.destination;
  const legs = trip.journey.legs as Array<{ to?: { name?: string | null } }>;
  const name = legs[legs.length - 1]?.to?.name?.trim();
  return name && name !== "END" && name !== "START" ? name : null;
}

function ActiveTripCard({ trip }: { trip: ActiveTrip }) {
  const { t, lang } = useI18n();
  const detailId = useId();
  const place = journeyEndName(trip);
  const arrival = trip.journey.timing.scheduledArrival;
  const time = Number.isFinite(Date.parse(arrival)) ? formatClock(arrival, lang) : null;
  let detail: string | null = null;
  if (time) detail = place ? t("home.activeTrip.detail", { place, time }) : t("home.activeTrip.detailNoPlace", { time });
  return (
    <button
      type="button"
      className="active-trip"
      aria-describedby={detail ? detailId : undefined}
      onClick={() => go({ name: "navigate" })}
    >
      <span className="active-trip-icon" aria-hidden="true">
        ➤
      </span>
      <span className="active-trip-text">
        <span className="active-trip-title">{t("home.activeTrip")}</span>
        {detail && (
          <span id={detailId} className="active-trip-detail tabular" aria-hidden="true">
            <bdi>{detail}</bdi>
          </span>
        )}
      </span>
      <span className="active-trip-go mirror" aria-hidden="true">
        ‹
      </span>
    </button>
  );
}

function endPin(endpoint: Endpoint | null, role: "origin" | "destination"): MapPin[] {
  if (endpoint?.type !== "place") return [];
  const { place } = endpoint;
  return [{ id: role, role, position: [place.longitude, place.latitude], label: place.label }];
}

/**
 * The map behind Home: the plan's chosen ends, or else the most recent place, or else
 * Tel Aviv, at a readable zoom above the sheet (never the whole country by accident).
 */
function homeScene(from: Endpoint | null, to: Endpoint | null, recent: SavedPlace | undefined): MapScene {
  const pins = [...endPin(from, "origin"), ...endPin(to, "destination")];
  const focus = recent
    ? { center: [recent.longitude, recent.latitude] as [number, number], zoom: 13 }
    : { center: DEFAULT_CENTER, zoom: 12 };
  return { ...emptyScene, pins, camera: "fit", focus };
}

export function HomeScreen() {
  const { t } = useI18n();
  const local = useLocalState();
  const trip = useActiveTrip();
  const { draft, setTo } = usePlan();
  const recent = local.recents[0];
  const scene = useMemo(() => homeScene(draft.from, draft.to, recent), [draft.from, draft.to, recent]);
  usePublishScene(scene);

  const travelTo = (saved: SavedPlace) => {
    setTo({ type: "place", place: choiceFromSaved(saved) });
    // Without a start yet, ask for it next (Search From then opens Compare).
    go(draft.from === null ? { name: "search", field: "from" } : { name: "compare" });
  };

  return (
    <div className="home">
      <h1 className="visually-hidden">{t("home.title")}</h1>

      {trip && <ActiveTripCard trip={trip} />}

      <FromTo variant="full" />

      {draft.to !== null && (
        <button
          type="button"
          className="button button-primary block"
          onClick={() => go(draft.from === null ? { name: "search", field: "from" } : { name: "compare" })}
        >
          {t("home.compare")}
        </button>
      )}

      <section aria-label={t("home.saved")}>
        <ul className="chips">
          <li>
            {local.home ? (
              <button type="button" className="chip chip-filled" onClick={() => travelTo(local.home!)}>
                <span aria-hidden="true">⌂</span> {t("place.home")}
              </button>
            ) : (
              <button type="button" className="chip" onClick={() => go({ name: "search", field: "home" })}>
                <span aria-hidden="true">⌂</span> {t("home.setHome")}
              </button>
            )}
          </li>
          <li>
            {local.work ? (
              <button type="button" className="chip chip-filled" onClick={() => travelTo(local.work!)}>
                <span aria-hidden="true">▣</span> {t("place.work")}
              </button>
            ) : (
              <button type="button" className="chip" onClick={() => go({ name: "search", field: "work" })}>
                <span aria-hidden="true">▣</span> {t("home.setWork")}
              </button>
            )}
          </li>
          {local.favourites.map((favourite) => (
            <li key={favourite.id}>
              <button type="button" className="chip chip-filled" onClick={() => travelTo(favourite)}>
                <span aria-hidden="true">★</span> <bdi>{favourite.label}</bdi>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              className="chip chip-add"
              aria-label={t("home.addFavourite")}
              onClick={() => go({ name: "search", field: "favourite" })}
            >
              <span aria-hidden="true">+</span>
            </button>
          </li>
        </ul>
      </section>

      <section aria-labelledby="home-recents">
        <h2 id="home-recents" className="section-title">
          {t("home.recents")}
        </h2>
        {local.recents.length === 0 ? (
          <p className="muted">{t("home.noRecents")}</p>
        ) : (
          <ul className="rows">
            {local.recents.slice(0, 10).map((item) => (
              <li key={item.id}>
                <button type="button" className="row-button" onClick={() => travelTo(item)}>
                  <span className="row-icon" aria-hidden="true">
                    🕘
                  </span>
                  <bdi className="row-text">{item.label}</bdi>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
