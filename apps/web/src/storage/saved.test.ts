import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { reloadLocalState } from "../shell/localStore";
import { loadLocalState, MAX_SAVED_ITEMS, saveLocalState, defaultLocalState, STORAGE_KEY } from "./local";
import {
  removeSavedLine,
  saveLine,
  saveStop,
  toggleSavedLine,
  toggleSavedStop,
  useIsLineSaved,
  useIsStopSaved,
  useSavedLines,
  useSavedStops,
  type SaveLineInput,
  type SaveStopInput,
} from "./saved";

const stop = (stopId = "mot:stop:13583"): SaveStopInput => ({
  stopId,
  name: "דיזנגוף סנטר/דיזנגוף",
  code: "25609",
  latitude: 32.075566,
  longitude: 34.77512,
  mode: "bus",
});

const line = (lineKey = "5:10008"): SaveLineInput => ({
  lineKey,
  shortName: "8",
  operatorId: "5",
  operatorName: "דן",
  mode: "bus",
  destinationName: "מסוף הטייסים",
  originName: "מסוף רידינג",
  stopId: "mot:stop:13561",
  stopName: "דיזנגוף סנטר/דיזנגוף",
});

const NOW = new Date("2026-11-14T10:00:00Z");

beforeEach(() => reloadLocalState());

describe("saved stops and lines (device only, storage version 2)", () => {
  it("toggle a stop on and off, persisted and seen by every hook at once", () => {
    const saved = renderHook(() => ({ stops: useSavedStops(), on: useIsStopSaved("mot:stop:13583") }));
    expect(saved.result.current).toEqual({ stops: [], on: false });
    act(() => void expect(toggleSavedStop(stop(), NOW)).toBe(true));
    expect(saved.result.current.on).toBe(true);
    expect(saved.result.current.stops).toEqual([{ ...stop(), savedAt: NOW.toISOString() }]);
    expect(loadLocalState().state.savedStops).toHaveLength(1);
    act(() => void expect(toggleSavedStop(stop())).toBe(false));
    expect(saved.result.current).toEqual({ stops: [], on: false });
    expect(loadLocalState().state.savedStops).toEqual([]);
  });

  it("a line is keyed by operator + line code: saving again refreshes its direction and stop, keeping its place", () => {
    const saved = renderHook(() => ({ lines: useSavedLines(), on: useIsLineSaved("5:10008") }));
    act(() => {
      saveLine(line(), NOW);
      saveLine({ ...line("3:20008"), operatorId: "3", operatorName: "אגד" }, NOW);
      saveLine({ ...line(), destinationName: "מסוף רידינג", originName: "מסוף הטייסים", stopId: "mot:stop:13583" });
    });
    expect(saved.result.current.on).toBe(true);
    expect(saved.result.current.lines.map((item) => [item.lineKey, item.destinationName, item.stopId, item.savedAt])).toEqual([
      ["5:10008", "מסוף רידינג", "mot:stop:13583", NOW.toISOString()],
      ["3:20008", "מסוף הטייסים", "mot:stop:13561", NOW.toISOString()],
    ]);
    act(() => void toggleSavedLine(line()));
    expect(saved.result.current.on).toBe(false);
    act(() => void removeSavedLine("3:20008"));
    expect(saved.result.current.lines).toEqual([]);
  });

  it("fills a saved line's optional fields, so a card can render offline", () => {
    act(() => void saveLine({ lineKey: "18:50087", shortName: "87" }, NOW));
    expect(loadLocalState().state.savedLines[0]).toEqual({
      lineKey: "18:50087",
      shortName: "87",
      operatorId: null,
      operatorName: null,
      mode: "bus",
      destinationName: null,
      originName: null,
      routeIdHint: null,
      area: null,
      stopId: null,
      stopName: null,
      savedAt: NOW.toISOString(),
    });
  });

  it("refuses what it cannot store: a stop outside Israel, an empty key, past the cap", () => {
    expect(saveStop({ ...stop(), latitude: 51.5 })).toBe(false);
    expect(saveLine({ ...line(), lineKey: "" })).toBe(false);
    saveLocalState({
      ...defaultLocalState(),
      savedStops: Array.from({ length: MAX_SAVED_ITEMS }, (_, index) => ({ ...stop(`s${index}`), code: null, mode: null, savedAt: NOW.toISOString() })),
    });
    reloadLocalState();
    expect(saveStop(stop("one-more"))).toBe(false);
    expect(loadLocalState().state.savedStops).toHaveLength(MAX_SAVED_ITEMS);
  });

  it("never writes over data a newer app version stored", () => {
    const newer = JSON.stringify({ version: 99, savedStops: "a newer shape" });
    localStorage.setItem(STORAGE_KEY, newer);
    reloadLocalState();
    toggleSavedStop(stop());
    expect(localStorage.getItem(STORAGE_KEY)).toBe(newer);
  });
});
