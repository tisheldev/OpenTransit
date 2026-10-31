import { useI18n } from "../../i18n/I18nProvider";
import type { SearchField } from "../../router";

// CONTRACT STUB, replaced by slice S4. Renders inside the sheet; publishes its map scene.
export function SearchScreen(_props: { field: SearchField }) {
  const { t } = useI18n();
  return <h1>{t("screen.search")}</h1>;
}
