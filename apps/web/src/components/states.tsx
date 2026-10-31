import { useEffect, useState, type ReactNode } from "react";
import { isRetryable, type UiState } from "../api/classify";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { formatDate } from "../lib/time";

// Shared loading, empty, unavailable and error states (design: Cross-cutting rules,
// States). Empty results are successes and look calm; unavailable is not empty.

/** Isolates numbers, times, line numbers and mixed-language names inside RTL text. */
export function Bdi({ children }: { children: ReactNode }) {
  return <bdi className="tabular">{children}</bdi>;
}

export function Loading({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="state state-loading" role="status" aria-live="polite" aria-busy="true">
      <span className="spinner" aria-hidden="true" />
      <span>{label ?? t("state.loading")}</span>
    </div>
  );
}

const emptyKeys = {
  noRoute: "state.empty.noRoute",
  noDepartures: "state.empty.noDepartures",
  noMatches: "state.empty.noMatches",
} as const satisfies Record<string, MessageKey>;

export function Empty({ kind }: { kind: keyof typeof emptyKeys }) {
  const { t } = useI18n();
  return (
    <p className="state state-empty" role="status">
      {t(emptyKeys[kind])}
    </p>
  );
}

type PlaceType = "stop" | "station" | "poi" | "address";

export function Unavailable(props: { kind: "live" } | { kind: "category"; categories: readonly PlaceType[] }) {
  const { t } = useI18n();
  const text =
    props.kind === "live"
      ? t("state.unavailable.live")
      : t("state.unavailable.category", { categories: props.categories.map((c) => t(`place.${c}`)).join(", ") });
  return (
    <p className="state state-unavailable" role="note">
      <span className="state-icon" aria-hidden="true">
        ⓘ
      </span>
      {text}
    </p>
  );
}

function useCountdown(seconds: number | null): number {
  const [left, setLeft] = useState(seconds ?? 0);
  useEffect(() => {
    if (!seconds) return;
    const started = Date.now();
    const timer = setInterval(() => {
      const remaining = Math.max(0, seconds - Math.floor((Date.now() - started) / 1000));
      setLeft(remaining);
      if (remaining === 0) clearInterval(timer);
    }, 250);
    return () => clearInterval(timer);
  }, [seconds]);
  return left;
}

export interface ErrorStateProps {
  state: UiState;
  /** Coverage from response metadata, for OUTSIDE_SERVICE_WINDOW. */
  coverage?: { from: string; until: string } | null;
  retryAfterSeconds?: number | null;
  onRetry?: () => void;
}

export function ErrorState({ state, coverage, retryAfterSeconds = null, onRetry }: ErrorStateProps) {
  const { t, lang } = useI18n();
  const wait = useCountdown(state === "rate_limited" ? retryAfterSeconds : null);
  const message =
    state === "outside_window" && coverage
      ? t("error.outside_window", { from: formatDate(coverage.from, lang), until: formatDate(coverage.until, lang) })
      : state === "outside_window"
        ? t("error.outside_window.noDates")
        : t(`error.${state}`);
  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      {onRetry && isRetryable(state) && (
        <button type="button" className="button" onClick={onRetry} disabled={wait > 0}>
          {wait > 0 ? t("state.retryIn", { seconds: wait }) : t("state.retry")}
        </button>
      )}
    </div>
  );
}

export function TestDataBanner() {
  const { t } = useI18n();
  return (
    <div className="banner banner-test" role="note">
      {t("banner.testData")}
    </div>
  );
}

export function StaleDataBanner() {
  const { t } = useI18n();
  return (
    <div className="banner banner-stale" role="note">
      {t("banner.staleData")}
    </div>
  );
}
