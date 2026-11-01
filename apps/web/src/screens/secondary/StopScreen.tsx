import { useI18n } from "../../i18n/I18nProvider";

// CONTRACT STUB, replaced by slice S7. Renders inside the sheet; publishes its map scene.
export function StopScreen(_props: { stopId: string }) {
  const { t } = useI18n();
  return <h1>{t("screen.stop")}</h1>;
}
