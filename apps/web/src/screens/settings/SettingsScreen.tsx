import { useId, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useStatus } from "../../api/queries";
import { ApiFailure } from "../../api/result";
import { Bdi, ErrorState, Loading } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { LANGS } from "../../i18n/messages";
import { formatDate } from "../../lib/time";
import { emptyScene, usePublishScene } from "../../map/scene";
import { endActiveTrip } from "../../nav/activeTrip";
import { initialDraft } from "../../plan/draft";
import { usePlan } from "../../plan/PlanProvider";
import { go } from "../../router";
import { generationMeta } from "../../shell/Banners";
import { deleteSaved, reloadLocalState, renameSaved, useLocalState } from "../../shell/localStore";
import { clearAllLocalData, type SavedPlace } from "../../storage/local";
import { version } from "../../../package.json";

// Settings — C07 (design: Screens 7): a plain list. The one destructive action confirms
// inline with a second tap; there are no modals.

function SavedItem({
  title,
  place,
  onSet,
}: {
  title: string;
  place: SavedPlace | null;
  /** Home and Work can be set or replaced through Search; favourites cannot. */
  onSet?: () => void;
}) {
  const { t } = useI18n();
  const inputId = useId();
  const [renaming, setRenaming] = useState(false);
  const [label, setLabel] = useState(place?.label ?? "");
  const name = place?.label ?? title;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (place && renameSaved(place.id, label)) setRenaming(false);
  };

  return (
    <li className="saved-item">
      <div className="saved-item-text">
        <span className="row-title">{title}</span>
        <span className="row-sub">{place ? <bdi>{place.label}</bdi> : t("settings.notSet")}</span>
      </div>
      {renaming && place ? (
        <form className="name-form" onSubmit={submit}>
          <label htmlFor={inputId}>{t("settings.renameField", { place: name })}</label>
          <input
            id={inputId}
            className="text-input"
            value={label}
            maxLength={200}
            autoFocus
            onChange={(event) => setLabel(event.target.value)}
          />
          <div className="actions">
            <button type="submit" className="button button-primary">
              {t("settings.renameSave")}
            </button>
            <button type="button" className="button" onClick={() => setRenaming(false)}>
              {t("settings.cancel")}
            </button>
          </div>
        </form>
      ) : (
        <div className="actions">
          {onSet && (
            <button type="button" className="button" onClick={onSet}>
              {place ? t("settings.change") : t("settings.set")}
            </button>
          )}
          {place && (
            <>
              <button
                type="button"
                className="button"
                aria-label={t("settings.renameNamed", { place: name })}
                onClick={() => {
                  setLabel(place.label);
                  setRenaming(true);
                }}
              >
                {t("settings.rename")}
              </button>
              <button
                type="button"
                className="button"
                aria-label={t("settings.deleteNamed", { place: name })}
                onClick={() => deleteSaved(place.id)}
              >
                {t("settings.delete")}
              </button>
            </>
          )}
        </div>
      )}
    </li>
  );
}

function DataStatus() {
  const { t, lang } = useI18n();
  const status = useStatus();
  if (status.isPending) return <Loading label={t("status.checking")} />;
  if (status.isError) {
    const failure = status.error instanceof ApiFailure ? status.error : null;
    return (
      <ErrorState
        state={failure?.state ?? "unexpected"}
        retryAfterSeconds={failure?.error.kind === "problem" ? failure.error.retryAfterSeconds : null}
        onRetry={() => void status.refetch()}
      />
    );
  }
  const meta = generationMeta(status.data);
  const freshness = meta?.freshness;
  const freshnessKey =
    freshness === "current" || freshness === "aging" || freshness === "expired" ? freshness : "other";
  return (
    <ul className="plain-list">
      <li>{status.data.data.ready ? t("status.ready") : t("status.notReady")}</li>
      {meta && (
        <>
          <li>
            <Bdi>{t("settings.dataBuilt", { date: formatDate(meta.dataBuiltAt, lang) })}</Bdi>
          </li>
          <li>
            <Bdi>
              {t("status.coverage", { from: formatDate(meta.coverage.from, lang), until: formatDate(meta.coverage.until, lang) })}
            </Bdi>
          </li>
          <li>{t("settings.freshness", { value: t(`settings.freshness.${freshnessKey}`) })}</li>
          <li>
            <Bdi>{t("settings.generation", { id: meta.generationId.slice(0, 12) })}</Bdi>
          </li>
          {meta.mode === "fixture" && <li>{t("settings.testData")}</li>}
        </>
      )}
      <li>{t("settings.realtime")}</li>
      <li>{t("settings.alerts")}</li>
    </ul>
  );
}

function ClearAll() {
  const { t, setLang } = useI18n();
  const queryClient = useQueryClient();
  const { setFrom, setTo, setWhen } = usePlan();
  const [armed, setArmed] = useState(false);
  const [cleared, setCleared] = useState(false);

  const clear = () => {
    setLang("he");
    setFrom(initialDraft.from);
    setTo(initialDraft.to);
    setWhen(initialDraft.when);
    endActiveTrip();
    queryClient.clear();
    clearAllLocalData();
    reloadLocalState();
    setArmed(false);
    setCleared(true);
  };

  return (
    <>
      <p className="muted small">{t("settings.clearData.hint")}</p>
      <div className="actions">
        <button
          type="button"
          className={armed ? "button button-danger" : "button"}
          onClick={() => {
            setCleared(false);
            if (armed) clear();
            else setArmed(true);
          }}
        >
          {armed ? t("settings.clearData.again") : t("settings.clearData")}
        </button>
        {armed && (
          <button type="button" className="button" onClick={() => setArmed(false)}>
            {t("settings.cancel")}
          </button>
        )}
      </div>
      <p role="status" aria-live="polite">
        {cleared ? t("settings.clearData.done") : ""}
      </p>
    </>
  );
}

export function SettingsScreen() {
  const { t, lang, setLang } = useI18n();
  const local = useLocalState();
  const groupId = useId();
  usePublishScene(emptyScene);

  return (
    <div className="settings">
      <h1>{t("screen.settings")}</h1>

      <fieldset className="segmented" aria-labelledby={groupId}>
        <legend id={groupId} className="section-title">
          {t("settings.language")}
        </legend>
        {LANGS.map((option) => (
          <label key={option} lang={option}>
            <input type="radio" name="lang" value={option} checked={lang === option} onChange={() => setLang(option)} />
            {t(`settings.language.${option}`)}
          </label>
        ))}
      </fieldset>

      <section aria-labelledby="settings-saved">
        <h2 id="settings-saved" className="section-title">
          {t("settings.saved")}
        </h2>
        <ul className="saved-list">
          <SavedItem title={t("place.home")} place={local.home} onSet={() => go({ name: "search", field: "home" })} />
          <SavedItem title={t("place.work")} place={local.work} onSet={() => go({ name: "search", field: "work" })} />
          {local.favourites.map((favourite) => (
            <SavedItem key={favourite.id} title={t("place.saved")} place={favourite} />
          ))}
        </ul>
        {local.favourites.length === 0 && <p className="muted small">{t("settings.noFavourites")}</p>}
        <button type="button" className="button" onClick={() => go({ name: "search", field: "favourite" })}>
          + {t("settings.addFavourite")}
        </button>
      </section>

      <section aria-labelledby="settings-clear">
        <h2 id="settings-clear" className="section-title">
          {t("settings.clearData")}
        </h2>
        <ClearAll />
      </section>

      <section aria-labelledby="settings-status">
        <h2 id="settings-status" className="section-title">
          {t("settings.dataStatus")}
        </h2>
        <DataStatus />
      </section>

      <section aria-labelledby="settings-credits">
        <h2 id="settings-credits" className="section-title">
          {t("settings.attribution")}
        </h2>
        <ul className="plain-list">
          <li>{t("settings.attribution.mot")}</li>
          <li>{t("settings.attribution.osm")}</li>
          <li>{t("settings.attribution.tiles")}</li>
        </ul>
        <h2 className="section-title">{t("settings.licences")}</h2>
        <p className="small">{t("settings.licences.code")}</p>
        <p className="small muted">
          <Bdi>
            {t("settings.version", {
              version: import.meta.env.MODE === "production" ? version : `${version} (${import.meta.env.MODE})`,
            })}
          </Bdi>
        </p>
      </section>
    </div>
  );
}
