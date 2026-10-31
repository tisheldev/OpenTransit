import { useId, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../../i18n/I18nProvider";
import { LANGS } from "../../i18n/messages";
import { clearAllLocalData } from "../../storage/local";

// CONTRACT STUB, replaced by slice S4 (S0 behaviour kept so the existing e2e stays green).
function SettingsBody() {
  const { t, lang, setLang } = useI18n();
  const queryClient = useQueryClient();
  const [cleared, setCleared] = useState(false);
  const groupId = useId();
  return (
    <>
      <fieldset className="segmented" aria-labelledby={groupId}>
        <legend id={groupId}>{t("settings.language")}</legend>
        {LANGS.map((option) => (
          <label key={option} lang={option}>
            <input type="radio" name="lang" value={option} checked={lang === option} onChange={() => setLang(option)} />
            {t(`settings.language.${option}`)}
          </label>
        ))}
      </fieldset>
      <p>
        <button
          type="button"
          className="button"
          onClick={() => {
            if (!window.confirm(t("settings.clearData.confirm"))) return;
            clearAllLocalData();
            queryClient.clear();
            setLang("he");
            setCleared(true);
          }}
        >
          {t("settings.clearData")}
        </button>
      </p>
      <p role="status" aria-live="polite">
        {cleared ? t("settings.clearData.done") : ""}
      </p>
    </>
  );
}

export function SettingsScreen() {
  const { t } = useI18n();
  return (
    <>
      <h1>{t("screen.settings")}</h1>
      <SettingsBody />
    </>
  );
}
