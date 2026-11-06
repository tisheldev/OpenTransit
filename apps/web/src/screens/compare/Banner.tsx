import type { ReactNode } from "react";
import { Icon } from "../../components/ds";

// Compare's prompts and notes as the design's banners (design: Banner): an icon and a bold
// title on its own line, then the rest. Failures use the shared ErrorState.

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
