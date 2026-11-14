import { VEHICLE_ICONS } from "./ds";
import "./gsign.css";

// Stop marker "G" (user, 12 November 2026: "I like G and want to apply it to everything"):
// a small sign with the vehicle on a short pole that ends in a dot on the kerb, the dot on
// the stop's point. SELF-CONTAINED STAND-IN for the Stop, Line and Ride maps, written by the
// stop/line builder; builder M owns the map's stops layer and marker motion and the two are
// unified at merge. Sizes and colours copied from the canvas boards Stop, Line and Ride
// (`.sg`) and the marker table in docs/client-design.md. The pole always points down here
// (the boards); which side of the road it points to is M's.

export function GSign({ chosen = false, rail = false }: { chosen?: boolean; rail?: boolean }) {
  const icon = VEHICLE_ICONS[rail ? "train" : "bus"];
  const className = ["ot-gsign", chosen ? "ot-gsign--chosen" : "", rail ? "ot-gsign--rail" : ""].filter(Boolean).join(" ");
  return (
    <span className={className} aria-hidden="true">
      <svg viewBox={icon.viewBox} aria-hidden="true" focusable="false">
        <path fillRule="evenodd" d={icon.d} />
      </svg>
    </span>
  );
}
