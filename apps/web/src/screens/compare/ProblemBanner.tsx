import { useEffect, useState, type ReactNode } from "react";
import { isRetryable, type UiState } from "../../api/classify";
import { Icon } from "../../components/ds";
import { useI18n } from "../../i18n/I18nProvider";
import { formatDate } from "../../lib/time";
import { splitFirstSentence } from "./labels";

// Compare's notes as the design's banners (design: Banner): an icon and a bold first
// phrase that stands on its own, then the rest. The failure banner says what the shared
// ErrorState says (same messages, retry only where retrying helps, Retry-After counted
// down), drawn with `ot-banner--error` and its action.

/** A banner whose message opens with its first sentence in bold. */
export function Banner({
  tone = "info",
  icon,
  title,
  text,
  role,
  action,
}: {
  tone?: "info" | "warning" | "error";
  icon: "info" | "alert" | "pin";
  /** The bold opening phrase. */
  title: string;
  text?: string | null;
  role?: "status" | "alert";
  action?: ReactNode;
}) {
  return (
    <div className={`ot-banner${tone === "info" ? "" : ` ot-banner--${tone}`} compare-banner`} role={role}>
      <Icon name={icon} />
      <p className="ot-banner__body">
        <b>{title}</b>
        {text && <> {text}</>}
      </p>
      {action}
    </div>
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

export function ProblemBanner({
  state,
  coverage,
  retryAfterSeconds = null,
  onRetry,
}: {
  state: UiState;
  /** Coverage from /v1/status, for OUTSIDE_SERVICE_WINDOW. */
  coverage?: { from: string; until: string } | null;
  retryAfterSeconds?: number | null;
  onRetry?: () => void;
}) {
  const { t, lang } = useI18n();
  const wait = useCountdown(state === "rate_limited" ? retryAfterSeconds : null);
  const message =
    state === "outside_window" && coverage
      ? t("error.outside_window", { from: formatDate(coverage.from, lang), until: formatDate(coverage.until, lang) })
      : state === "outside_window"
        ? t("error.outside_window.noDates")
        : t(`error.${state}`);
  const { first, rest } = splitFirstSentence(message);
  return (
    <Banner
      tone="error"
      icon="alert"
      title={first}
      text={rest}
      role="alert"
      action={
        onRetry &&
        isRetryable(state) && (
          <button type="button" className="ot-banner__action" onClick={onRetry} disabled={wait > 0}>
            {wait > 0 ? t("state.retryIn", { seconds: wait }) : t("state.retry")}
          </button>
        )
      }
    />
  );
}
