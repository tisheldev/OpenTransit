import type { Journey } from "../api/types";

// Rank labels are captions over returned numbers (design: Domain model, SE02). The order
// is the API's: this never re-sorts, drops or merges journeys; it returns one label (or
// none) per journey, index for index.
//
// - The first journey is "recommended" (the engine's first choice).
// - Among the others, one whose number is strictly the best of every option shown (the
//   first included, so a caption never contradicts what is drawn) gets, in this order of
//   preference: "fastest" (durationSeconds), "noTransfers" (transfers 0) or
//   "fewerTransfers" (transfers), "lessWalking" (walkingSeconds).
// - One label per option at most, and each label once at most. A tie gets none.
// - A walk-only option is captioned "walkOnly" in its row (rankLabels does not give it a
//   transfer label: it has no ride to transfer between).

export type RankLabel = "recommended" | "fastest" | "noTransfers" | "fewerTransfers" | "lessWalking";

export function isWalkOnly(journey: Journey): boolean {
  return journey.legs.length > 0 && journey.legs.every((leg) => leg.kind === "walk");
}

/** Index of the journey with the strictly lowest value, or null on a tie or with < 2 options. */
function strictMinimum(values: (number | null)[]): number | null {
  let best: number | null = null;
  let bestValue = Infinity;
  let tied = false;
  values.forEach((value, index) => {
    if (value === null) return;
    if (value < bestValue) {
      best = index;
      bestValue = value;
      tied = false;
    } else if (value === bestValue) {
      tied = true;
    }
  });
  return tied ? null : best;
}

export function rankLabels(journeys: readonly Journey[]): (RankLabel | null)[] {
  const labels: (RankLabel | null)[] = journeys.map((_, index) => (index === 0 ? "recommended" : null));
  if (journeys.length < 2) return labels;

  const give = (index: number | null, label: RankLabel) => {
    if (index === null || index === 0 || labels[index] !== null) return;
    labels[index] = label;
  };

  give(strictMinimum(journeys.map((j) => j.durationSeconds)), "fastest");
  const transfers = journeys.map((j) => (isWalkOnly(j) ? null : j.transfers));
  const fewest = strictMinimum(transfers);
  if (fewest !== null) give(fewest, transfers[fewest] === 0 ? "noTransfers" : "fewerTransfers");
  give(strictMinimum(journeys.map((j) => j.walkingSeconds)), "lessWalking");
  return labels;
}
