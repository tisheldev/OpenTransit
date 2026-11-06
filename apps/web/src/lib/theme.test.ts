import { afterEach, describe, expect, it } from "vitest";
import { loadLocalState } from "../storage/local";
import { THEME_COLORS } from "../styles/tokens";
import { applyTheme, getTheme, resetTheme, setTheme } from "./theme";

function meta(): HTMLMetaElement {
  let element = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (!element) {
    element = document.createElement("meta");
    element.name = "theme-color";
    document.head.append(element);
  }
  return element;
}

afterEach(() => {
  localStorage.clear();
  resetTheme();
});

describe("theme", () => {
  it("is dark by default, whatever is stored for language", () => {
    meta();
    resetTheme();
    expect(getTheme()).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(meta().content).toBe(THEME_COLORS.dark.bg);
  });

  it("light is a stored choice, applied at once with its theme-color", () => {
    meta();
    setTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(meta().content).toBe(THEME_COLORS.light.bg);
    expect(loadLocalState().state.settings.theme).toBe("light");
    resetTheme(); // a reload reads it back
    expect(getTheme()).toBe("light");
  });

  it("applyTheme sets only the attribute and the meta", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
