import { Icon } from "../../components/ds";
import { Banner } from "../../components/states";
import { useI18n } from "../../i18n/I18nProvider";
import { hrefFor } from "../../router";

// A screen that is not built yet, or a route that does not exist: its title, an honest
// note, and the way back home. Renders inside the sheet like every screen.

export function Placeholder({ title, notBuilt = true }: { title: string; notBuilt?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="placeholder">
      <h1>{title}</h1>
      {notBuilt && <Banner role="note">{t("screen.placeholder")}</Banner>}
      <a className="button placeholder-home" href={hrefFor({ name: "home" })}>
        <Icon name="home" />
        {t("screen.backHome")}
      </a>
    </div>
  );
}
