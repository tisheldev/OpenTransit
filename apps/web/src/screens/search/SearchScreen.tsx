import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import { usePlaceSearch, PLACES_MIN_CHARS } from "../../api/queries";
import { ApiFailure } from "../../api/result";
import type { Meta, PlaceCandidate } from "../../api/schemas";
import { Empty, ErrorState } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { emptyScene, useMapState, usePublishScene } from "../../map/scene";
import { choiceFromSaved, type Endpoint, type PlaceChoice } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { back, go, type SearchField } from "../../router";
import { addFavourite, addRecent, saveSlot, storable, useLocalState } from "../../shell/localStore";
import { useSheet } from "../../shell/sheet";
import type { SavedPlace } from "../../storage/local";
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

const KIND_ICON: Record<PlaceCandidate["kind"], string> = { stop: "🚏", station: "🚉", address: "⌖", poi: "★" };
const SKELETON_ROWS = 4;

function ResultRow({ candidate, meta, onChoose }: { candidate: PlaceCandidate; meta: Meta; onChoose: (choice: PlaceChoice) => void }) {
  const { t, lang } = useI18n();
  const locality = readableLocality(candidate.locality);
  const other = candidate.languageUsed !== lang && /^[a-z]{2}$/.test(candidate.languageUsed);
  const stopCode = candidate.kind === "stop" || candidate.kind === "station" ? candidate.stopCode : null;
  return (
    <li>
      <button type="button" className="row-button" onClick={() => onChoose(choiceFromCandidate(candidate, meta))}>
        <span className="row-icon" aria-hidden="true">
          {KIND_ICON[candidate.kind]}
        </span>
        <span className="row-text">
          <bdi className="row-title" lang={other ? candidate.languageUsed : undefined}>
            {candidate.displayName}
          </bdi>
          <span className="row-sub">
            <span className="kind-label">{t(`place.${candidate.kind}`)}</span>
            {isStreetLevel(candidate) && <span className="tag">{t("place.streetLevel")}</span>}
            {stopCode && (
              <bdi className="tabular">{t("place.stopCode", { code: stopCode })}</bdi>
            )}
            {locality && <bdi>{locality}</bdi>}
          </span>
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
          <span className="row-title">{title}</span>
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

  const scene = useMemo(() => ({ ...emptyScene, pick: mode === "pick" }), [mode]);
  usePublishScene(scene);

  const choose = (choice: PlaceChoice | "myLocation") => {
    setSaveFailed(false);
    if (field === "from" || field === "to") {
      const endpoint: Endpoint = choice === "myLocation" ? { type: "myLocation" } : { type: "place", place: choice };
      if (choice !== "myLocation") addRecent(choice); // "my location" is never a recent (CU11)
      if (field === "from") setFrom(endpoint);
      else setTo(endpoint);
      const otherKnown = field === "from" ? draft.to !== null : true;
      if (otherKnown) go({ name: "compare" }, { replace: true });
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

  const searching = typed.length >= PLACES_MIN_CHARS;
  const skeleton = searching && (debounced !== typed || query.isPending || (query.isFetching && query.isError));
  const failure = query.error instanceof ApiFailure ? query.error : null;
  const answer = searching && !skeleton && query.data ? query.data : null;
  const retryAfter = failure?.error.kind === "problem" ? failure.error.retryAfterSeconds : null;

  let live = "";
  if (skeleton) live = t("search.searching");
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
            className="icon-button"
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

      {!searching && (
        <ul className="rows">
          <li>
            <button
              type="button"
              className="row-button"
              onClick={() => {
                setMode("pick");
                setSnap("peek");
              }}
            >
              <span className="row-icon" aria-hidden="true">
                📍
              </span>
              <span className="row-text row-title">{t("search.pickOnMap")}</span>
            </button>
          </li>
          {field === "from" && (
            <li>
              <button type="button" className="row-button" onClick={() => choose("myLocation")}>
                <span className="row-icon" aria-hidden="true">
                  ◎
                </span>
                <span className="row-text row-title">{t("place.myLocation")}</span>
              </button>
            </li>
          )}
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

      {typed.length > 0 && !searching && <p className="muted">{t("search.minChars")}</p>}

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

      {searching && !skeleton && failure && (
        <>
          <ErrorState state={failure.state} retryAfterSeconds={retryAfter} onRetry={() => void query.refetch()} />
          {failure.state === "category_unavailable" && (
            <button type="button" className="button" onClick={() => void query.refetch()}>
              {t("state.retry")}
            </button>
          )}
        </>
      )}

      {answer && (
        <>
          {answer.data.length === 0 && answer.unavailableTypes.length === 0 && <Empty kind="noMatches" />}
          <ul className="rows" data-testid="search-results">
            {answer.data.map((candidate, index) => (
              <ResultRow key={candidateKey(candidate, index)} candidate={candidate} meta={answer.meta} onChoose={choose} />
            ))}
            {answer.unavailableTypes.map((type) => (
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
