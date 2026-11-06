import { useEffect, useState, type AriaRole, type ReactNode } from "react";
import { isRetryable, type UiState } from "../api/classify";
import { useI18n } from "../i18n/I18nProvider";
import type { MessageKey } from "../i18n/messages";
import { formatDate } from "../lib/time";
import { Icon, type IconName } from "./ds";

// Shared loading, empty, unavailable and error states (design: Cross-cutting rules,
// States; component Banner). Empty results are successes and look calm; unavailable is
// not empty. Every banner has an icon and a bold first phrase that stands on its own.

/** Isolates numbers, times, line numbers and mixed-language names inside RTL text. */
export function Bdi({ children }: { children: ReactNode }) {
  return <bdi className="tabular">{children}</bdi>;
}

/**
 * A message's first phrase (up to its first full stop, or before a " — ") and the rest,
 * so a banner can set the first phrase in bold. The two parts join back to the message.
 */
export function leadPhrase(message: string): [lead: string, rest: string] {
  const match = /\.\s|\s—\s/.exec(message);
  if (!match) return [message, ""];
  const end = match[0].startsWith(".") ? match.index + 1 : match.index;
  return [message.slice(0, end), message.slice(end)];
}

export type BannerTone = "info" | "warning" | "error";

/**
 * An honest note about the data (design: Banner): info is permanent context, warning a
 * degraded answer, error a failure. A string message gets its first phrase in bold.
 * `compact` where space is tight (the shell's top band).
 */
export function Banner({
  tone = "info",
  compact = false,
  role,
  icon,
  action,
  className,
  children,
}: {
  tone?: BannerTone;
  compact?: boolean;
  role?: AriaRole;
  icon?: IconName;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const classes = ["ot-banner", tone === "info" ? "" : `ot-banner--${tone}`, compact ? "ot-banner--compact" : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  let body = children;
  if (typeof children === "string") {
    const [lead, rest] = leadPhrase(children);
    body = (
      <>
        <b>{lead}</b>
        {rest}
      </>
    );
  }
  return (
    <div className={classes} role={role}>
      <Icon name={icon ?? (tone === "info" ? "info" : "alert")} size={compact ? "sm" : undefined} />
      <div className="ot-banner__body">{body}</div>
      {action}
    </div>
  );
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
    <Banner className="state state-empty" role="status">
      {t(emptyKeys[kind])}
    </Banner>
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
    <Banner tone={props.kind === "live" ? "info" : "warning"} className="state state-unavailable" role="note">
      {text}
    </Banner>
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
    <Banner
      tone="error"
      className="state"
      role="alert"
      action={
        onRetry &&
        isRetryable(state) && (
          <button type="button" className="ot-banner__action banner-action" onClick={onRetry} disabled={wait > 0}>
            {wait > 0 ? t("state.retryIn", { seconds: wait }) : t("state.retry")}
          </button>
        )
      }
    >
      {message}
    </Banner>
  );
}

/** Fixture or test data is always labelled, wherever it shows (design: Honest data). */
export function TestDataBanner({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <Banner tone="warning" compact={compact} className="banner-test" role="note">
      {t("banner.testData")}
    </Banner>
  );
}

export function StaleDataBanner({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <Banner tone="warning" compact={compact} role="note">
      {t("banner.staleData")}
    </Banner>
  );
}
