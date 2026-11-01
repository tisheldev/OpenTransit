import { describe, expect, it } from "vitest";
import { UI_STATES } from "../api/classify";
import { en } from "./en";
import { he } from "./he";
import { directionOf, placeholdersOf, translate, type MessageKey } from "./messages";

const heKeys = Object.keys(he).sort();
const enKeys = Object.keys(en).sort();

describe("dictionaries", () => {
  it("have the same keys", () => {
    expect(enKeys).toEqual(heKeys);
  });

  it.each(heKeys)("%s has the same placeholders and no empty text", (key) => {
    const k = key as MessageKey;
    expect(placeholdersOf(en[k])).toEqual(placeholdersOf(he[k]));
    expect(he[k].trim()).not.toBe("");
    expect(en[k].trim()).not.toBe("");
  });

  it("write Hebrew strings in Hebrew", () => {
    const latinOnly = heKeys.filter((key) => !/[֐-׿]/.test(he[key as MessageKey]));
    // Brand names (the app, the compact map credits) and the English language label are
    // deliberately Latin.
    expect(latinOnly).toEqual(["app.name", "map.attribution.osm", "map.attribution.tiles", "settings.language.en"]);
  });

  it("have a message for every UI state", () => {
    for (const state of UI_STATES) expect(heKeys).toContain(`error.${state}`);
  });

  it("use the design's Hebrew units", () => {
    expect(he["state.retryIn"]).toContain("שנ׳");
  });
});

describe("translate()", () => {
  it("fills placeholders and keeps unknown ones visible", () => {
    expect(translate("en", "status.coverage", { from: "1 Oct", until: "31 Oct" })).toBe(
      "Scheduled timetable from 1 Oct to 31 Oct",
    );
    expect(translate("en", "status.coverage", { from: "1 Oct" })).toContain("{until}");
  });

  it("maps language to direction", () => {
    expect(directionOf("he")).toBe("rtl");
    expect(directionOf("en")).toBe("ltr");
  });
});
