import type { he_nav } from "./nav.he";

// Mirrors nav.he.ts key for key.
export const en_nav: Record<keyof typeof he_nav, string> = {
  "nav.noTrip": "No active trip.",
  "nav.stepOf": "Step {n} of {total}",
  "nav.origin": "the starting point",
  "nav.destination": "your destination",

  "nav.step.walkToStop": "Walk to {stop}",
  "nav.step.transferWalk": "Transfer: walk to {stop}",
  "nav.step.walkToDestination": "Walk to {place}",
  "nav.step.arrive": "You have arrived at {place}",

  "nav.mode.bus": "Bus",
  "nav.mode.rail": "Train",
  "nav.mode.light_rail": "Light rail",
  "nav.mode.other": "Line",
  "nav.ride.train": "Train to {to}",
  "nav.ride.headsign": "towards {headsign}",

  "nav.distanceLeft": "{distance} to go",
  "nav.walkDistance": "{distance} walk",
  "nav.walkTimeOnly": "About {duration} walk · no street path available",
  "nav.departsAt": "Departs {time} (scheduled)",
  "nav.countdown": "in {duration}",
  "nav.countdownNow": "leaving now",
  "nav.countdownPast": "the scheduled departure has passed",
  "nav.platformUnknown": "Platform unknown",
  "nav.stopsLeft": "{count} stops left",
  "nav.stopsLeftOne": "1 stop left",
  "nav.stopCount": "{count} stops",
  "nav.stopsUnknown": "Number of stops unknown",
  "nav.exitAt": "Get off at {stop} · {time} (scheduled)",
  "nav.then": "Then: {next}",
  "nav.arriveAt": "Arrival {time} (scheduled)",

  "nav.cueTwo": "Get off in 2 stops",
  "nav.cueNext": "Get off at the next stop",

  "nav.next": "Next step",
  "nav.finish": "Finish",
  "nav.end": "End trip",
  "nav.manual": "Steps advance manually",
  "nav.lost": "No location right now",
  "nav.keepOpen": "Keep this page open: the browser does not follow your location while the screen is locked.",

  "nav.checklist": "All steps",
  "nav.row.done": "Done",
  "nav.row.current": "Current step",
  "nav.row.pending": "To come",
  "nav.summary.walkToStop": "Walk to {stop} · {duration}",
  "nav.summary.rideNoStops": "{ride} · get off at {stop}",
  "nav.summary.transfer": "Transfer · {duration}",
  "nav.summary.walkToDestination": "Walk to {place} · {duration}",
  "nav.summary.arrive": "Arrive {time}",
  "nav.announce.step": "Step {n} of {total}: {summary}",

  "nav.testing": "Testing tools",
  "nav.sim.toggle": "Simulated location (testing)",
  "nav.sim.speed": "Simulation speed",
  "nav.sim.speedValue": "×{n}",
  "nav.sim.on": "Simulated location — not your real position. Simulated clock {time}.",
};
