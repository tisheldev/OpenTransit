import { createElement, lazy, Suspense, type ComponentType } from "react";
import { Loading } from "../components/states";
import { useI18n } from "../i18n/I18nProvider";
import type { Route } from "../router";
import { HomeScreen } from "./home/HomeScreen";
import { SearchScreen } from "./search/SearchScreen";
import { LinesScreen } from "./secondary/LinesScreen";
import { NearbyScreen } from "./secondary/NearbyScreen";
import { StopScreen } from "./secondary/StopScreen";
import { TripScreen } from "./secondary/TripScreen";
import { SettingsScreen } from "./settings/SettingsScreen";

// Compare and Navigate are their own chunks: Home and Search paint without them, and the
// initial script stays under its 150 KB budget (design: Performance). Both are prefetched
// once the first screen has painted; a chunk already loaded renders at once (no fallback).
function preloadable<P extends object>(load: () => Promise<ComponentType<P>>) {
  let loaded: ComponentType<P> | null = null;
  let pending: Promise<ComponentType<P>> | null = null;
  const preload = () =>
    (pending ??= load().then((component) => {
      loaded = component;
      return component;
    }));
  const Lazy = lazy(() => preload().then((component) => ({ default: component })));
  function Preloadable(props: P) {
    return loaded ? createElement(loaded, props) : createElement(Lazy, props);
  }
  return { Component: Preloadable, preload };
}

const compare = preloadable(() => import("./compare/CompareScreen").then((m) => m.CompareScreen));
const navigate = preloadable(() => import("./navigate/NavigateScreen").then((m) => m.NavigateScreen));
const CompareScreen = compare.Component;
const NavigateScreen = navigate.Component;

/** Warm the Compare and Navigate chunks (after first paint; in tests before rendering). */
export function prefetchScreens(): Promise<unknown> {
  return Promise.all([compare.preload(), navigate.preload()]);
}

// The sheet's content for each route (design: Surface). Each screen owns its folder,
// renders its own <h1> and publishes its map scene; the shell (src/shell/Shell.tsx)
// places it in the bottom sheet and moves focus to it on navigation.

export function Screen({ route }: { route: Route }) {
  const { t } = useI18n();
  switch (route.name) {
    case "home":
      return <HomeScreen />;
    case "search":
      return <SearchScreen key={route.field} field={route.field} />;
    case "compare":
      return (
        <Suspense fallback={<Loading />}>
          <CompareScreen />
        </Suspense>
      );
    case "navigate":
      return (
        <Suspense fallback={<Loading />}>
          <NavigateScreen />
        </Suspense>
      );
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
