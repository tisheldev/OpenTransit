import { useId, useMemo } from "react";
import { Icon } from "../../components/ds";
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

// Home — C01 (design: Screens 1; TripFields, PlaceChips, PlaceRow). Renders from storage
// only; the data status banner is the shell's and arrives after the first paint. Settings
// is the icon in the sheet's handle row (the shell's), so Home holds only the trip.

/** The engine names coordinate ends "START"/"END": never show those as a place. */
function journeyEndName(trip: ActiveTrip): string | null {
  if (trip.labels?.destination) return trip.labels.destination;
  const legs = trip.journey.legs as Array<{ to?: { name?: string | null } }>;
  const name = legs[legs.length - 1]?.to?.name?.trim();
  return name && name !== "END" && name !== "START" ? name : null;
}

/** The trip in progress leads, in the navigation hero's colours (design: NavStep hero). */
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
      <Icon name="route" className="active-trip-icon" />
      <span className="active-trip-text">
        <span className="active-trip-title">{t("home.activeTrip")}</span>
        {detail && (
          <span id={detailId} className="active-trip-detail tabular" aria-hidden="true">
            <bdi>{detail}</bdi>
          </span>
        )}
      </span>
      <Icon name="chevron" className="active-trip-go" />
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

      <FromTo />

      {draft.to !== null && (
        <button
          type="button"
          className="button button-primary block"
          onClick={() => go(draft.from === null ? { name: "search", field: "from" } : { name: "compare" })}
        >
          {t("home.compare")}
        </button>
      )}

      {/* PlaceChips: Home, Work, favourites in their order, then Add. An unset Home or Work
          keeps its slot in the Add style. The row scrolls sideways from the inline start. */}
      <section aria-label={t("home.saved")}>
        <ul className="ot-chips home-chips">
          <li>
            {local.home ? (
              <button type="button" className="ot-chip" onClick={() => travelTo(local.home!)}>
                <Icon name="home" />
                {t("place.home")}
              </button>
            ) : (
              <button type="button" className="ot-chip ot-chip--add" onClick={() => go({ name: "search", field: "home" })}>
                <Icon name="home" />
                {t("home.setHome")}
              </button>
            )}
          </li>
          <li>
            {local.work ? (
              <button type="button" className="ot-chip" onClick={() => travelTo(local.work!)}>
                <Icon name="work" />
                {t("place.work")}
              </button>
            ) : (
              <button type="button" className="ot-chip ot-chip--add" onClick={() => go({ name: "search", field: "work" })}>
                <Icon name="work" />
                {t("home.setWork")}
              </button>
            )}
          </li>
          {local.favourites.map((favourite) => (
            <li key={favourite.id}>
              <button type="button" className="ot-chip" onClick={() => travelTo(favourite)}>
                <Icon name="star" />
                <bdi>{favourite.label}</bdi>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              className="ot-chip ot-chip--add"
              aria-label={t("home.addFavourite")}
              onClick={() => go({ name: "search", field: "favourite" })}
            >
              <Icon name="plus" />
              {t("home.add")}
            </button>
          </li>
        </ul>
      </section>

      <section aria-labelledby="home-recents">
        <h2 id="home-recents" className="section-title">
          {t("home.recents")}
        </h2>
        {local.recents.length === 0 ? (
          <p className="muted small">{t("home.noRecents")}</p>
        ) : (
          <ul className="ot-list place-list">
            {local.recents.slice(0, 10).map((item) => (
              <li key={item.id}>
                <button type="button" className="ot-row" onClick={() => travelTo(item)}>
                  <span className="ot-row__icon">
                    <Icon name="clock" />
                  </span>
                  <span className="ot-row__body">
                    <bdi className="ot-row__title">{item.label}</bdi>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
