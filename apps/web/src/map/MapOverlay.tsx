import type { Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useReducer, type CSSProperties } from "react";
import { LineBadge } from "../components/ds";
import { lineMode } from "./layers";
import type { MapStopPin, MapTag } from "./scene";

// Tags and stop pins drawn over the map as HTML (boards, 11 November 2026): a stop's next
// departure, an option's arrival time, "יורדים כאן", the stops around the passenger. They
// follow the map as it moves (re-projected once per animation frame) and are real buttons
// when they do something. The map canvas itself stays decorative; every fact a tag shows is
// also in the panel as text.

function useMapFrame(map: MapLibreMap): void {
  const [, tick] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    let frame = 0;
    const schedule = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        tick();
      });
    };
    map.on("move", schedule);
    map.on("resize", schedule);
    map.on("styledata", schedule);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      map.off("move", schedule);
      map.off("resize", schedule);
      map.off("styledata", schedule);
    };
  }, [map]);
}

function position(map: MapLibreMap, at: [number, number]): CSSProperties {
  const point = map.project(at);
  return { transform: `translate(${Math.round(point.x)}px, ${Math.round(point.y)}px)` };
}

function TagBody({ tag }: { tag: MapTag }) {
  return (
    <>
      {tag.line && (
        <LineBadge
          mode={lineMode(tag.line.mode) === "rail" ? "rail" : "bus"}
          label={tag.line.label}
          line={{ mode: tag.line.mode, operatorId: tag.line.operatorId, operatorName: tag.line.operatorName }}
        />
      )}
      {tag.text && <span className="map-tag__text">{tag.text}</span>}
    </>
  );
}

/** Within this many pixels of a side, a tag opens inward from its point instead of centring on it, so it is not clipped. */
const EDGE_PX = 96;

function edgeOf(map: MapLibreMap, at: [number, number]): "left" | "right" | null {
  const x = map.project(at).x;
  const width = map.getContainer().clientWidth;
  if (x < EDGE_PX) return "left";
  if (width > 0 && x > width - EDGE_PX) return "right";
  return null;
}

function Tag({ tag, dir, edge }: { tag: MapTag; dir: "rtl" | "ltr"; edge: "left" | "right" | null }) {
  const className = `map-tag map-tag--${tag.kind} map-tag--${tag.anchor ?? "above"}${edge ? ` map-tag--edge-${edge}` : ""}`;
  const style = tag.accent ? ({ "--tag-accent": tag.accent } as CSSProperties) : undefined;
  if (tag.onSelect) {
    return (
      <button type="button" className={className} style={style} dir={dir} aria-label={tag.ariaLabel} onClick={tag.onSelect}>
        <TagBody tag={tag} />
      </button>
    );
  }
  return (
    <span className={className} style={style} dir={dir} aria-label={tag.ariaLabel} role={tag.ariaLabel ? "img" : undefined}>
      <TagBody tag={tag} />
    </span>
  );
}

/** The stop sign inside a large stop pin (boards: a sign on a post). */
function StopSign() {
  return (
    <svg viewBox="0 0 26 26" aria-hidden="true" focusable="false">
      <rect x="8" y="6" width="10" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M13 13 V20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function StopPin({ pin }: { pin: MapStopPin }) {
  const className = `map-stop${pin.selected ? " map-stop--selected" : ""}`;
  if (pin.onSelect) {
    return (
      <button type="button" className={className} aria-label={pin.ariaLabel} aria-pressed={pin.selected ?? false} onClick={pin.onSelect}>
        <StopSign />
      </button>
    );
  }
  return (
    <span className={className} role="img" aria-label={pin.ariaLabel}>
      <StopSign />
    </span>
  );
}

export function MapOverlay({
  map,
  tags,
  stopPins,
  dir,
}: {
  map: MapLibreMap;
  tags: readonly MapTag[];
  stopPins: readonly MapStopPin[];
  dir: "rtl" | "ltr";
}) {
  useMapFrame(map);
  if (tags.length === 0 && stopPins.length === 0) return null;
  return (
    <div className="map-overlay" data-testid="map-overlay">
      {stopPins.map((pin) => (
        <div key={`stop-${pin.id}`} className="map-overlay__item" style={position(map, pin.position)}>
          <StopPin pin={pin} />
        </div>
      ))}
      {tags.map((tag) => (
        <div key={`tag-${tag.id}`} className="map-overlay__item" style={position(map, tag.position)}>
          <Tag tag={tag} dir={dir} edge={edgeOf(map, tag.position)} />
        </div>
      ))}
    </div>
  );
}
