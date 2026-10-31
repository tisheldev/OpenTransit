// Shared by the recorded-evidence extractor and the live recorder, so every fixture is
// sanitised the same way. Responses carry no personal data; what varies per request
// (request IDs) is replaced so fixtures are stable and cannot be mistaken for a trace.

export const SANITISED_REQUEST_ID = "0".repeat(32);

export function sanitise(value) {
  if (Array.isArray(value)) return value.map(sanitise);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        key === "requestId" && typeof item === "string" ? SANITISED_REQUEST_ID : sanitise(item),
      ]),
    );
  }
  return value;
}

export function stableJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}
