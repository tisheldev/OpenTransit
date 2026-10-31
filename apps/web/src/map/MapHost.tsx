// CONTRACT STUB (replaced in S3 by the map agent): the shell renders <MapHost/> as the
// full-bleed layer behind the sheet. S3 makes it lazy-load MapLibre after the first
// frame, draw the scene from ./scene.ts and keep the attribution visible.

export function MapHost() {
  return <div className="map-host" aria-hidden="true" data-testid="map-host" />;
}
