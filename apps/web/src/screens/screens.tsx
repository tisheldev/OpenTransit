import { useI18n } from "../i18n/I18nProvider";
import type { Route } from "../router";
import { CompareScreen } from "./compare/CompareScreen";
import { HomeScreen } from "./home/HomeScreen";
import { NavigateScreen } from "./navigate/NavigateScreen";
import { SearchScreen } from "./search/SearchScreen";
import { LinesScreen } from "./secondary/LinesScreen";
import { NearbyScreen } from "./secondary/NearbyScreen";
import { StopScreen } from "./secondary/StopScreen";
import { TripScreen } from "./secondary/TripScreen";
import { SettingsScreen } from "./settings/SettingsScreen";

// The sheet's content for each route (design: Surface). Each screen owns its folder.

export function Screen({ route }: { route: Route }) {
  const { t } = useI18n();
  switch (route.name) {
    case "home":
      return <HomeScreen />;
    case "search":
      return <SearchScreen field={route.field} />;
    case "compare":
      return <CompareScreen />;
    case "navigate":
      return <NavigateScreen />;
    case "settings":
      return <SettingsScreen />;
    case "stop":
      return <StopScreen stopId={route.stopId} />;
    case "trip":
      return <TripScreen tripRef={route.tripRef} />;
    case "nearby":
      return <NearbyScreen />;
    case "lines":
      return <LinesScreen />;
    case "notFound":
      return <h1>{t("screen.notFound")}</h1>;
  }
}
