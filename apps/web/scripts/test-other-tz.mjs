#!/usr/bin/env node
// Rerun the time tests under host zones other than UTC; results must not change.
import { spawnSync } from "node:child_process";

for (const zone of ["America/New_York", "Asia/Tokyo", "Asia/Jerusalem"]) {
  console.log(`\n# OT_TEST_TZ=${zone}`);
  const run = spawnSync("npx", ["vitest", "run", "src/lib"], {
    stdio: "inherit",
    shell: process.platform === "win32",
    env: { ...process.env, OT_TEST_TZ: zone },
  });
  if (run.status !== 0) process.exit(run.status ?? 1);
}
