import { act, fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";
import { go, type Route } from "../router";
import { useSheet, type SheetControl } from "./sheet";
import { renderApp } from "./testUtils";

// G1: a screen that sets a snap from an effect keyed on setSnap (as Compare and Navigate
// did) must not snap back after every drag or tap. The screen switch is replaced by a
// probe that does exactly that and records setSnap's identity on every render.

const seen = vi.hoisted(() => ({ setSnaps: [] as unknown[], snapOnMount: "full" as "peek" | "half" | "full" }));

vi.mock("../screens/screens", () => ({
  Screen: ({ route }: { route: Route }) => <Probe key={JSON.stringify(route)} route={route} />,
}));

function Probe({ route }: { route: Route }) {
  const { setSnap } = useSheet();
  seen.setSnaps.push(setSnap);
  useEffect(() => setSnap(seen.snapOnMount), [setSnap]);
  return <h1>{route.name}</h1>;
}

const sheet = () => document.querySelector(".sheet")!;
const handle = () => screen.getByRole("button", { name: /גודל הגיליון/ });

describe("setSnap from a screen's effect", () => {
  it("applies once; then the handle's tap and drag stick, and setSnap keeps its identity", async () => {
    seen.setSnaps.length = 0;
    renderApp("#/compare");
    expect(sheet()).toHaveAttribute("data-snap", "full");
    await userEvent.click(handle());
    expect(sheet()).toHaveAttribute("data-snap", "peek");
    await userEvent.click(handle());
    expect(sheet()).toHaveAttribute("data-snap", "half");
    // jsdom has no layout: a drag from 0 px up by 700 px in a 768 px viewport ends near full.
    fireEvent.pointerDown(handle(), { button: 0, clientY: 740, pointerId: 1 });
    fireEvent.pointerMove(handle(), { clientY: 40, pointerId: 1 });
    fireEvent.pointerUp(handle(), { clientY: 40, pointerId: 1 });
    expect(sheet()).toHaveAttribute("data-snap", "full");
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(sheet()).toHaveAttribute("data-snap", "full");
    const distinct = new Set(seen.setSnaps as SheetControl["setSnap"][]);
    expect(distinct.size).toBe(1);
  });

  it("a new route gets its own setSnap, and the new screen's request applies there", async () => {
    seen.setSnaps.length = 0;
    seen.snapOnMount = "peek";
    renderApp("#/");
    expect(sheet()).toHaveAttribute("data-snap", "peek");
    act(() => go({ name: "settings" }));
    await screen.findByRole("heading", { name: "settings" });
    expect(sheet()).toHaveAttribute("data-snap", "peek");
    expect(new Set(seen.setSnaps).size).toBe(2);
    seen.snapOnMount = "full";
  });
});
