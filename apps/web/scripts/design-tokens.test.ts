// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
// @ts-expect-error plain ES module script without type declarations
import { generate, readTokens } from "./design-tokens.mjs";

// The client's tokens are generated from the design system's tokens.json; this fails when
// either side changed without `npm run tokens` (the two cannot drift).
describe("design tokens", () => {
  it("tokens.css, tokens.ts and theme.js match tokens.json", () => {
    const files = generate(readTokens()) as Record<string, string>;
    for (const [path, content] of Object.entries(files)) {
      expect(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"), path).toBe(content);
    }
  });

  it("dark is the default; light only under data-theme=light", () => {
    const css = (generate(readTokens()) as Record<string, string>)["src/styles/tokens.css"]!;
    expect(css).toMatch(/:root \{\n {2}color-scheme: dark;[\s\S]*--bg: #0d1618;/);
    expect(css).toMatch(/:root\[data-theme="light"\] \{\n {2}color-scheme: light;[\s\S]*--bg: #f4f7f7;/);
  });
});
