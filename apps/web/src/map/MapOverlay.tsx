import type { Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useReducer, type CSSProperties } from "react";
import { LineBadge } from "../components/ds";
import { edgePin, spreadPins, type EdgePin, type ScreenRect } from "./edgePin";
import { GMarker } from "./stops/markers";
import { poleSideOf } from "./stops/StopsLayer";
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

/** A direction's tag shows at most this many badges, then "+N". */
const MAX_BADGES = 4;

function Badge({ line }: { line: NonNullable<MapTag["line"]> }) {
  return (
    <LineBadge
      mode={lineMode(line.mode) === "rail" ? "rail" : "bus"}
      label={line.label}
      line={{ mode: line.mode, operatorId: line.operatorId, operatorName: line.operatorName }}
    />
  );
}

function TagBody({ tag }: { tag: MapTag }) {
  if (tag.lines && tag.lines.length > 0) {
    const shown = tag.lines.slice(0, MAX_BADGES);
    const more = tag.lines.length - shown.length;
    return (
      <>
        {tag.text && <span className="map-tag__text">{tag.text}</span>}
        {shown.map((line, index) => (
          <Badge key={`${line.label}-${index}`} line={line} />
        ))}
        {more > 0 && (
          <>
            {/* "+N" on screen; the lines it stands for, by number, to a screen reader. */}
            <span className="map-tag__more num" aria-hidden="true">
              +{more}
            </span>
            <span className="visually-hidden">{tag.lines.slice(MAX_BADGES).map((line) => line.label).join(" ")}</span>
          </>
        )}
      </>
    );
  }
  return (
    <>
      {tag.line && <Badge line={tag.line} />}
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

function Tag({ tag, dir, edge, anchor }: { tag: MapTag; dir: "rtl" | "ltr"; edge: "left" | "right" | null; anchor?: MapTag["anchor"] }) {
  const className = `map-tag map-tag--${tag.kind} map-tag--${anchor ?? tag.anchor ?? "above"}${edge ? ` map-tag--edge-${edge}` : ""}${
    tag.late ? " map-tag--late" : ""
  }${tag.along ? " map-tag--pinned" : ""}`;
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

/** The chosen line's direction (boards Stop and Line: a chevron on the line, path copied verbatim). */
function Chevron({ tag, bearing }: { tag: MapTag; bearing: number }) {
  // The canvas path points north-east (45°); turned to the line's bearing.
  return (
    <span className="map-chevron" role={tag.ariaLabel ? "img" : undefined} aria-label={tag.ariaLabel} style={{ transform: `rotate(${Math.round(bearing - 45)}deg)` }}>
      <svg viewBox="262 116 24 24" aria-hidden="true" focusable="false">
        <path d="m268 126 12-4-4 12" />
      </svg>
    </span>
  );
}

function StopPin({ pin, map }: { pin: MapStopPin; map: MapLibreMap }) {
  if (pin.look === "sign") {
    // Marker G, the same as the stops layer's (src/map/stops): its pole snapped away from
    // the road when the side is known, else centred with no pole.
    return (
      <GMarker
        side={pin.rail ? null : poleSideOf(pin.id, pin.bearingDegrees, map.getBearing())}
        chosen={pin.selected === true}
        station={pin.rail === true}
        label={pin.ariaLabel}
        onSelect={pin.onSelect}
      />
    );
  }
  const className = `map-stop${pin.selected ? " map-stop--selected" : ""}`;
  if (pin.onSelect) {
    return (
      <button type="button" className={className} aria-label={pin.ariaLabel} onClick={pin.onSelect}>
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

/** Pinned tags keep this far inside the visible map. */
const PIN_MARGIN_PX = 8;

/** How a tag hangs from the point where its path leaves the map: always inward. */
function pinnedPlacement(map: MapLibreMap, pin: EdgePin, fallback: MapTag["anchor"]): { anchor: MapTag["anchor"]; edge: "left" | "right" | null } {
  const at: [number, number] = map.unproject([pin.x, pin.y]).toArray() as [number, number];
  switch (pin.side) {
    case "top":
      return { anchor: "below", edge: edgeOf(map, at) };
    case "bottom":
      return { anchor: "above", edge: edgeOf(map, at) };
    case "left":
      return { anchor: "center", edge: "left" };
    case "right":
      return { anchor: "center", edge: "right" };
    default:
      return { anchor: fallback, edge: edgeOf(map, at) };
  }
}

export function MapOverlay({
  map,
  tags,
  stopPins,
  dir,
  visible,
}: {
  map: MapLibreMap;
  tags: readonly MapTag[];
  stopPins: readonly MapStopPin[];
  dir: "rtl" | "ltr";
  /** Insets of the map covered by the top band, the sheet and a side panel, in pixels. */
  visible?: { top: number; bottom: number; left: number; right: number };
}) {
  useMapFrame(map);
  if (tags.length === 0 && stopPins.length === 0) return null;
  const container = map.getContainer();
  const rect: ScreenRect = {
    left: (visible?.left ?? 0) + PIN_MARGIN_PX,
    top: (visible?.top ?? 0) + PIN_MARGIN_PX,
    right: container.clientWidth - (visible?.right ?? 0) - PIN_MARGIN_PX,
    bottom: container.clientHeight - (visible?.bottom ?? 0) - PIN_MARGIN_PX,
  };
  const pins = spreadPins(tags.map((tag) => (tag.along ? edgePin(tag.along.map((at) => map.project(at)), rect) : null)));
  return (
    <div className="map-overlay" data-testid="map-overlay">
      {stopPins.map((pin) => (
        <div key={`stop-${pin.id}`} className="map-overlay__item" style={position(map, pin.position)}>
          <StopPin pin={pin} map={map} />
        </div>
      ))}
      {tags.map((tag, index) => {
        if (tag.along) {
          // Pinned where its lines leave the map; hidden while the stop is out of view.
          const pin = pins[index];
          if (!pin) return null;
          const { anchor, edge } = pinnedPlacement(map, pin, tag.anchor);
          return (
            <div key={`tag-${tag.id}`} className="map-overlay__item" style={{ transform: `translate(${Math.round(pin.x)}px, ${Math.round(pin.y)}px)` }}>
              <Tag tag={tag} dir={dir} edge={edge} anchor={anchor} />
            </div>
          );
        }
        return (
          <div key={`tag-${tag.id}`} className="map-overlay__item" style={position(map, tag.position)}>
            {tag.glyph ? <Chevron tag={tag} bearing={tag.glyph.bearing} /> : <Tag tag={tag} dir={dir} edge={edgeOf(map, tag.position)} />}
          </div>
        );
      })}
    </div>
  );
}
