import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { usePlaceSearch, PLACES_MIN_CHARS } from "../../api/queries";
import { ApiFailure } from "../../api/result";
import type { Meta, PlaceCandidate, Places } from "../../api/schemas";
import { Empty, ErrorState } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { DEFAULT_CENTER } from "../../map/layers";
import { emptyScene, useMapState, usePublishScene, type MapFocus } from "../../map/scene";
import { choiceFromSaved, type Endpoint, type PlaceChoice, type PlanDraft } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { back, go, openerRoute, type SearchField } from "../../router";
import { addFavourite, addRecent, rememberOrigin, saveSlot, storable, useLocalState } from "../../shell/localStore";
import { useLocationAvailability } from "../../shell/location";
import { useSheet } from "../../shell/sheet";
import type { LocalState, SavedPlace } from "../../storage/local";
import { candidateKey, choiceFromCandidate, choiceFromPin, isStreetLevel, readableLocality } from "./choice";
import { useNearIfGranted } from "./near";

// Where to / Where from — C02 (design: Screens 2), also used to set Home, Work and a
// favourite. Place IDs and coordinates never enter the URL: the choice goes to the plan
// draft (session) or to saved places (local storage).

export const SEARCH_DEBOUNCE_MS = 250;

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

const KIND_ICON: Record<PlaceCandidate["kind"], string> = { stop: "🚏", station: "🚉", address: "📍", poi: "⭐" };
const SKELETON_ROWS = 4;

/**
 * Parts of a result's second line, joined by a quiet "·" that wraps with the part after
 * it (never left dangling at a line end). A tag needs no separator.
 */
function Parts({ children }: { children: Array<{ node: ReactNode; separated: boolean } | null> }) {
  const parts = children.filter((part) => part !== null);
  return (
    <span className="row-sub">
      {parts.map((part, index) => (
        <span key={index} className="row-part">
          {index > 0 && part.separated && (
            <span className="row-sep" aria-hidden="true">
              ·{" "}
            </span>
          )}
          {part.node}
        </span>
      ))}
    </span>
  );
}

function ResultRow({ candidate, meta, onChoose }: { candidate: PlaceCandidate; meta: Meta; onChoose: (choice: PlaceChoice) => void }) {
  const { t, lang } = useI18n();
  const locality = readableLocality(candidate.locality);
  const other = candidate.languageUsed !== lang && /^[a-z]{2}$/.test(candidate.languageUsed);
  const stopCode = candidate.kind === "stop" || candidate.kind === "station" ? candidate.stopCode : null;
  // A stop reads "Stop 43073 · street, city"; the code says what it is.
  const kind =
    candidate.kind === "stop" && stopCode ? (
      <bdi className="tabular">{t("place.stopCode", { code: stopCode })}</bdi>
    ) : (
      <span className="kind-label">
        {t(`place.${candidate.kind}`)}
        {stopCode && (
          <>
            {" "}
            <bdi className="tabular">{stopCode}</bdi>
          </>
        )}
      </span>
    );
  return (
    <li>
      <button type="button" className="row-button" onClick={() => onChoose(choiceFromCandidate(candidate, meta))}>
        <span className="row-icon" aria-hidden="true">
          {KIND_ICON[candidate.kind]}
        </span>
        <span className="row-text">
          <span className="row-title">
            <bdi lang={other ? candidate.languageUsed : undefined}>{candidate.displayName}</bdi>
          </span>
          <Parts>
            {[
              { node: kind, separated: true },
              isStreetLevel(candidate) ? { node: <span className="tag">{t("place.streetLevel")}</span>, separated: false } : null,
              locality ? { node: <bdi>{locality}</bdi>, separated: true } : null,
            ]}
          </Parts>
        </span>
      </button>
    </li>
  );
}

function SavedRow({ icon, title, place, onChoose }: { icon: string; title: string; place: SavedPlace; onChoose: (choice: PlaceChoice) => void }) {
  return (
    <li>
      <button type="button" className="row-button" onClick={() => onChoose(choiceFromSaved(place))}>
        <span className="row-icon" aria-hidden="true">
          {icon}
        </span>
        <span className="row-text">
          {/* A recent is its label alone: plain weight, as on Home. The block keeps the
              page's direction; only the name inside is isolated. */}
          <span className={title === place.label ? undefined : "row-title"}>
            <bdi>{title}</bdi>
          </span>
          {title !== place.label && (
            <span className="row-sub">
              <bdi>{place.label}</bdi>
            </span>
          )}
        </span>
      </button>
    </li>
  );
}

function PickOnMap({ onConfirm, onCancel }: { onConfirm: (choice: PlaceChoice) => void; onCancel: () => void }) {
  const { t } = useI18n();
  const { center } = useMapState();
  const [outside, setOutside] = useState(false);
  return (
    <div className="pick">
      <p>{t("search.pick.hint")}</p>
      {center === null && <p className="muted">{t("search.pick.waiting")}</p>}
      {outside && (
        <p className="state state-error" role="alert">
          {t("search.pick.outside")}
        </p>
      )}
      <div className="actions">
        <button
          type="button"
          className="button button-primary"
          disabled={center === null}
          onClick={() => {
            if (center === null) return;
            const choice = choiceFromPin(center, t("place.pin"));
            if (!storable(choice)) {
              setOutside(true);
              return;
            }
            onConfirm(choice);
          }}
        >
          {t("search.pick.confirm")}
        </button>
        <button type="button" className="button" onClick={onCancel}>
          {t("search.pick.cancel")}
        </button>
      </div>
    </div>
  );
}

function NameFavourite({ choice, onSave, onCancel }: { choice: PlaceChoice; onSave: (label: string) => void; onCancel: () => void }) {
  const { t } = useI18n();
  const inputId = useId();
  const defaultLabel = choice.label.slice(0, 200);
  const [label, setLabel] = useState(defaultLabel);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => inputRef.current?.focus(), []);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave(label.trim() || defaultLabel);
  };
  return (
    <form className="name-form" onSubmit={submit}>
      <label htmlFor={inputId}>{t("search.favourite.name")}</label>
      <input
        ref={inputRef}
        id={inputId}
        className="text-input"
        value={label}
        maxLength={200}
        onChange={(event) => setLabel(event.target.value)}
      />
      <div className="actions">
        <button type="submit" className="button button-primary">
          {t("search.favourite.save")}
        </button>
        <button type="button" className="button" onClick={onCancel}>
          {t("search.favourite.cancel")}
        </button>
      </div>
    </form>
  );
}


/** Where "choose on map" starts: the field's own place, the plan's other end, the last place, Tel Aviv. */
function pickFocus(field: SearchField, draft: PlanDraft, local: LocalState): MapFocus {
  const place = (endpoint: Endpoint | null) => (endpoint?.type === "place" ? endpoint.place : null);
  const saved = field === "home" ? local.home : field === "work" ? local.work : null;
  const own = field === "from" ? place(draft.from) : field === "to" ? place(draft.to) : null;
  const other = field === "from" ? place(draft.to) : place(draft.from);
  const start = own ?? saved ?? other ?? local.recents[0] ?? null;
  return start ? { center: [start.longitude, start.latitude], zoom: 15 } : { center: DEFAULT_CENTER, zoom: 14 };
}

function MyLocationRow({ onChoose }: { onChoose: () => void }) {
  const { t } = useI18n();
  const location = useLocationAvailability();
  if (location.availability === "unavailable") {
    // Shown, not offered: a one-line reason instead of a choice bound to fail.
    return (
      <li className="row-static" aria-disabled="true">
        <span className="row-icon" aria-hidden="true">
          ◎
        </span>
        <span className="row-text">
          <span className="row-title">{t("place.myLocation")}</span>
          <span className="row-sub">{t(`search.myLocation.${location.reason ?? "unsupported"}`)}</span>
        </span>
      </li>
    );
  }
  return (
    <li>
      <button type="button" className="row-button" onClick={onChoose}>
        <span className="row-icon" aria-hidden="true">
          ◎
        </span>
        <span className="row-text row-title">{t("place.myLocation")}</span>
      </button>
    </li>
  );
}

export function SearchScreen({ field }: { field: SearchField }) {
  const { t, lang } = useI18n();
  const { draft, setFrom, setTo } = usePlan();
  const local = useLocalState();
  const { setSnap } = useSheet();
  const near = useNearIfGranted();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"search" | "pick">("search");
  const [naming, setNaming] = useState<PlaceChoice | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);

  const typed = q.trim();
  const debounced = useDebounced(typed, SEARCH_DEBOUNCE_MS);
  const query = usePlaceSearch(debounced, lang, near);

  // The pick-on-map start is fixed when picking begins, so the map is not moved under the pin.
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const scene = useMemo(() => ({ ...emptyScene, pick: mode === "pick", camera: mode === "pick" ? ("fit" as const) : ("keep" as const), focus }), [mode, focus]);
  usePublishScene(scene);

  const searching = typed.length >= PLACES_MIN_CHARS;
  const loading = searching && (debounced !== typed || query.isPending || (query.isFetching && query.isError));
  const failure = query.error instanceof ApiFailure ? query.error : null;
  const answer = searching && !loading && query.data ? query.data : null;
  // While the next answer loads, the previous one stays (dimmed) instead of a skeleton:
  // no rows jump on every keystroke. Skeleton rows only when there is nothing to show.
  const [kept, setKept] = useState<Places | null>(null);
  if (answer && answer !== kept) setKept(answer);
  if (!searching && kept !== null) setKept(null);
  const shown = answer ?? (loading ? kept : null);
  const stale = shown !== null && shown !== answer;
  const skeleton = loading && shown === null;

  const choose = (choice: PlaceChoice | "myLocation") => {
    setSaveFailed(false);
    if (field === "from" || field === "to") {
      const endpoint: Endpoint = choice === "myLocation" ? { type: "myLocation" } : { type: "place", place: choice };
      // "my location" is never a recent (CU11); a chosen start is remembered as the last one.
      if (choice !== "myLocation") {
        if (field === "from") rememberOrigin(choice);
        else addRecent(choice);
      }
      if (field === "from") setFrom(endpoint);
      else setTo(endpoint);
      // Return to whatever opened Search (Compare stays one entry: Back from it is Home).
      // From Home with both ends known, Search's own entry becomes Compare; a destination
      // without a start asks for the start next, in the same entry.
      if (openerRoute()?.name === "compare") back();
      else if (field === "to" && draft.from === null) go({ name: "search", field: "from" }, { replace: true });
      else if (field === "to" || draft.to !== null) go({ name: "compare" }, { replace: true });
      else back();
      return;
    }
    if (choice === "myLocation") return;
    if (field === "favourite") {
      setMode("search");
      setNaming(choice);
      return;
    }
    if (saveSlot(field, choice)) back({ name: "home" });
    else setSaveFailed(true);
  };

  const title = t(`search.title.${field}`);

  if (naming) {
    return (
      <div className="search">
        <h1>{title}</h1>
        <NameFavourite
          choice={naming}
          onSave={(label) => {
            if (addFavourite(naming, label)) back({ name: "home" });
            else setSaveFailed(true);
          }}
          onCancel={() => setNaming(null)}
        />
        {saveFailed && (
          <p className="state state-error" role="alert">
            {t("search.pick.outside")}
          </p>
        )}
      </div>
    );
  }

  if (mode === "pick") {
    return (
      <div className="search">
        <h1>{t("search.pickOnMap")}</h1>
        <PickOnMap
          onConfirm={choose}
          onCancel={() => {
            setMode("search");
            setSnap("full");
            window.setTimeout(() => inputRef.current?.focus(), 0);
          }}
        />
      </div>
    );
  }

  const retryAfter = failure?.error.kind === "problem" ? failure.error.retryAfterSeconds : null;

  let live = "";
  if (loading) live = t("search.searching");
  else if (answer && answer.data.length > 0) live = t("search.results", { count: answer.data.length });

  return (
    <div className="search">
      <h1>{title}</h1>
      <div className="search-field">
        <label htmlFor={inputId} className="visually-hidden">
          {t("search.input")}
        </label>
        <input
          ref={inputRef}
          id={inputId}
          className="text-input"
          type="search"
          inputMode="search"
          enterKeyHint="search"
          autoComplete="off"
          spellCheck={false}
          placeholder={t("search.placeholder")}
          value={q}
          onChange={(event) => setQ(event.target.value)}
          data-autofocus=""
        />
        {q !== "" && (
          <button
            type="button"
            className="icon-button quiet search-clear"
            aria-label={t("search.clear")}
            onClick={() => {
              setQ("");
              inputRef.current?.focus();
            }}
          >
            <span aria-hidden="true">✕</span>
          </button>
        )}
      </div>

      <p className="visually-hidden" role="status" aria-live="polite">
        {live}
      </p>

      {saveFailed && (
        <p className="state state-error" role="alert">
          {t("search.pick.outside")}
        </p>
      )}

      {typed.length > 0 && !searching && <p className="muted small search-hint">{t("search.minChars")}</p>}

      {!searching && (
        <ul className="rows">
          <li>
            <button
              type="button"
              className="row-button"
              onClick={() => {
                setFocus(pickFocus(field, draft, local));
                setMode("pick");
                setSnap("peek");
              }}
            >
              <span className="row-icon" aria-hidden="true">
                🗺️
              </span>
              <span className="row-text row-title">{t("search.pickOnMap")}</span>
            </button>
          </li>
          {field === "from" && <MyLocationRow onChoose={() => choose("myLocation")} />}
          {local.home && field !== "home" && <SavedRow icon="⌂" title={t("place.home")} place={local.home} onChoose={choose} />}
          {local.work && field !== "work" && <SavedRow icon="▣" title={t("place.work")} place={local.work} onChoose={choose} />}
          {local.favourites.map((favourite) => (
            <SavedRow key={favourite.id} icon="★" title={favourite.label} place={favourite} onChoose={choose} />
          ))}
          {local.recents.map((recent) => (
            <SavedRow key={recent.id} icon="🕘" title={recent.label} place={recent} onChoose={choose} />
          ))}
        </ul>
      )}

      {skeleton && (
        <ul className="rows" aria-hidden="true" data-testid="search-skeleton">
          {Array.from({ length: SKELETON_ROWS }, (_, index) => (
            <li key={index} className="row-skeleton">
              <span className="skeleton-icon" />
              <span className="skeleton-lines">
                <span className="skeleton-line" />
                <span className="skeleton-line short" />
              </span>
            </li>
          ))}
        </ul>
      )}

      {searching && !loading && failure && (
        <>
          <ErrorState state={failure.state} retryAfterSeconds={retryAfter} onRetry={() => void query.refetch()} />
          {failure.state === "category_unavailable" && (
            <button type="button" className="button" onClick={() => void query.refetch()}>
              {t("state.retry")}
            </button>
          )}
        </>
      )}

      {shown && (
        <>
          {!stale && shown.data.length === 0 && shown.unavailableTypes.length === 0 && <Empty kind="noMatches" />}
          <ul
            className={stale ? "rows rows-stale" : "rows"}
            data-testid={stale ? "search-results-previous" : "search-results"}
            aria-busy={stale || undefined}
          >
            {shown.data.map((candidate, index) => (
              <ResultRow key={candidateKey(candidate, index)} candidate={candidate} meta={shown.meta} onChoose={choose} />
            ))}
            {shown.unavailableTypes.map((type) => (
              <li key={type} className="row-note" role="note">
                <span className="row-icon" aria-hidden="true">
                  ⓘ
                </span>
                <span>{t("search.categoryUnavailable", { category: t(`place.${type}`) })}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
