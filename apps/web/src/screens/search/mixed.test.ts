import { describe, expect, it } from "vitest";
import { fixture } from "../../api/fixtures";
import type { LineItem, Places } from "../../api/schemas";
import { derivedLineSearch } from "../../mocks/lineFixtures";
import { isLineQuery, LINES_SHOWN, matchRank, mixResults, withMoreRow, type MixedItem } from "./mixed";

const lines = (q: string, near = true): LineItem[] => {
  const url = new URL(`http://test/v1/lines?q=${encodeURIComponent(q)}&limit=50${near ? "&lat=32.0753&lon=34.7749" : ""}`);
  return (derivedLineSearch(url).body as { data: LineItem[] }).data;
};
const places = () => (fixture("recorded-places-stop-he").body as Places).data;
const label = (item: MixedItem) => (item.kind === "line" ? `line ${item.line.shortName} ${item.line.operatorName}` : `${item.candidate.kind} ${item.candidate.displayName}`);

describe("matchRank()", () => {
  it("ranks the whole name, then its start, a word's start, anywhere, then no literal match", () => {
    expect(["8", "82", "אבן גבירול 8", "דיזנגוף8", "סנטר"].map((name) => matchRank(name, "8"))).toEqual([0, 1, 2, 3, 4]);
    expect(matchRank("דיזנגוף סנטר/דיזנגוף", "סנטר")).toBe(2);
    expect(matchRank("Dizengoff Center", "dizengoff")).toBe(1);
  });

  it("a query naming a line starts with a digit", () => {
    expect([isLineQuery("8"), isLineQuery(" 82"), isLineQuery("1א"), isLineQuery("דיזנגוף 8")]).toEqual([true, true, true, false]);
  });
});

describe("mixResults()", () => {
  it("a number: exact lines first (operators sharing it apart), then longer numbers, then places", () => {
    const mixed = mixResults({ typed: "8", lines: lines("8"), places: places(), near: null });
    expect(mixed.slice(0, 3).map(label)).toEqual(["line 8 דן", "line 8 אגד", expect.stringMatching(/^line 8\d /)]);
    const firstPlace = mixed.findIndex((item) => item.kind === "place");
    expect(mixed.slice(0, firstPlace).every((item) => item.kind === "line")).toBe(true);
    // Among the prefix matches, the line with a stop nearer the passenger leads.
    expect(mixed[2]!.kind === "line" && mixed[2]!.line.shortName).toBe("82");
  });

  it("a name: places and stops by how well the name matches, then distance; the API's order breaks ties", () => {
    const mixed = mixResults({ typed: "דיזנגוף סנטר", lines: [], places: places(), near: null });
    // The exact name leads; the rest start with the text, and the stops carry the API's
    // distance (the request had `near`) while the other place does not, so it comes last.
    expect(mixed.map(label)).toEqual([
      "poi דיזנגוף סנטר",
      "stop דיזנגוף סנטר/דיזנגוף",
      "stop דיזנגוף סנטר/דיזנגוף",
      "stop דיזנגוף סנטר/טשרניחובסקי",
      "poi דיזנגוף סנטרל",
    ]);
    const near = { latitude: 32.0753, longitude: 34.7749 };
    const byDistance = mixResults({ typed: "דיזנגוף", lines: [], places: places(), near });
    const tied = byDistance.filter((item) => item.rank === byDistance[0]!.rank);
    const distances = tied.map((item) => item.distance!);
    expect([...distances].sort((a, b) => a - b)).toEqual(distances);
  });

  it("shows four lines, then one 'N more lines' row right after them, until opened", () => {
    const mixed = mixResults({ typed: "8", lines: lines("8"), places: places(), near: null });
    const count = mixed.filter((item) => item.kind === "line").length;
    expect(count).toBeGreaterThan(LINES_SHOWN);
    const shown = withMoreRow(mixed, false, false);
    expect(shown.filter((item) => item.kind === "line")).toHaveLength(LINES_SHOWN);
    expect(shown[LINES_SHOWN]).toEqual({ kind: "more", key: "more", count: count - LINES_SHOWN, atLeast: false });
    expect(withMoreRow(mixed, true, false)).toHaveLength(mixed.length);
    expect(withMoreRow(mixed.slice(0, 3), false, false)).toHaveLength(3);
  });
});
