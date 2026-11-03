import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { back, go, hrefFor, openerRoute, parseHash, useRoute, type Route } from "./router";

describe("history entries", () => {
  it("remember the screen that opened them; a deep link has no opener", async () => {
    window.history.replaceState({ otDepth: 0 }, "", "/#/");
    const { result } = renderHook(() => useRoute());
    act(() => {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(openerRoute()).toBeNull();
    act(() => go({ name: "compare" }));
    await waitFor(() => expect(result.current).toEqual({ name: "compare" }));
    expect(openerRoute()).toEqual({ name: "home" });
    act(() => go({ name: "search", field: "from" }));
    await waitFor(() => expect(result.current).toEqual({ name: "search", field: "from" }));
    expect(openerRoute()).toEqual({ name: "compare" });
    // Replacing an entry keeps who opened it.
    act(() => go({ name: "settings" }, { replace: true }));
    await waitFor(() => expect(result.current).toEqual({ name: "settings" }));
    expect(openerRoute()).toEqual({ name: "compare" });
    act(() => back());
    await waitFor(() => expect(result.current).toEqual({ name: "compare" }));
    expect(openerRoute()).toEqual({ name: "home" });
  });
});

describe("hash router", () => {
  it.each<[string, Route]>([
    ["", { name: "home" }],
    ["#/", { name: "home" }],
    ["#/search", { name: "search", field: "to" }],
    ["#/search/from", { name: "search", field: "from" }],
    ["#/search/bogus", { name: "notFound", path: "/search/bogus" }],
    ["#/settings", { name: "settings" }],
    ["#/stop/mot%3Astop%3A13583", { name: "stop", stopId: "mot:stop:13583" }],
    ["#/trip/20260930_23%3A50_mot60day_584668860_300926", { name: "trip", tripRef: "20260930_23:50_mot60day_584668860_300926" }],
    ["#/nope", { name: "notFound", path: "/nope" }],
    ["#/settings/extra", { name: "notFound", path: "/settings/extra" }],
    ["#/stop/%E0%A4%A", { name: "notFound", path: "/stop/%E0%A4%A" }],
  ])("parses %j", (hash, route) => {
    expect(parseHash(hash)).toEqual(route);
  });

  it("round-trips routes through hrefs", () => {
    const routes: Route[] = [
      { name: "home" },
      { name: "compare" },
      { name: "stop", stopId: "mot:stop:13583" },
      { name: "trip", tripRef: "20261025_00:00_mot60day_463093_081026" },
    ];
    for (const route of routes) expect(parseHash(hrefFor(route))).toEqual(route);
  });
});
