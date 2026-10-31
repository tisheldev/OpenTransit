import { useI18n } from "../../i18n/I18nProvider";
import { emptyScene, usePublishScene } from "../../map/scene";
import { useActiveTrip } from "../../nav/activeTrip";
import { choiceFromSaved } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { go, hrefFor } from "../../router";
import { FromTo } from "../../shell/FromTo";
import { useLocalState } from "../../shell/localStore";
import type { SavedPlace } from "../../storage/local";

// Home — C01 (design: Screens 1). Renders from storage only; the data status banner is
// the shell's and arrives after the first paint.

export function HomeScreen() {
  const { t } = useI18n();
  const local = useLocalState();
  const trip = useActiveTrip();
  const { draft, setTo } = usePlan();
  usePublishScene(emptyScene);

  const travelTo = (saved: SavedPlace) => {
    setTo({ type: "place", place: choiceFromSaved(saved) });
    go({ name: "compare" });
  };

  return (
    <div className="home">
      <div className="screen-header">
        <h1 className="visually-hidden">{t("home.title")}</h1>
      </div>

      {trip && (
        <button type="button" className="row-button active-trip" onClick={() => go({ name: "navigate" })}>
          <span className="row-icon" aria-hidden="true">
            ➤
          </span>
          <span className="row-text">{t("home.activeTrip")}</span>
        </button>
      )}

      <FromTo variant="full" />

      {draft.to !== null && (
        <button type="button" className="button button-primary block" onClick={() => go({ name: "compare" })}>
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
            {local.recents.slice(0, 10).map((recent) => (
              <li key={recent.id}>
                <button type="button" className="row-button" onClick={() => travelTo(recent)}>
                  <span className="row-icon" aria-hidden="true">
                    🕘
                  </span>
                  <bdi className="row-text">{recent.label}</bdi>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="muted small">
        {t("home.scheduledOnly")} · {t("banner.liveUnavailable")}
      </p>

      <a className="icon-button settings-link" href={hrefFor({ name: "settings" })} aria-label={t("screen.settings")}>
        <span aria-hidden="true">⚙</span>
      </a>
    </div>
  );
}
