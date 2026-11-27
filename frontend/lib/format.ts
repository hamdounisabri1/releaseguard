const DATE_TIME = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** A UTC timestamp from the API in the user's local time ("27 Nov 2026, 14:05"). */
export function formatDateTime(iso: string): string {
  return DATE_TIME.format(new Date(iso));
}
