import * as React from "react";

const MOBILE_BREAKPOINT = 768;
const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`;

function subscribe(onChange: () => void): () => void {
  const mql = window.matchMedia(QUERY);
  mql.addEventListener("change", onChange);
  return () => mql.removeEventListener("change", onChange);
}

// Rewritten from the shadcn template with useSyncExternalStore: the template's
// setState-in-effect fails the React Compiler lint rule (react-hooks/set-state-in-effect).
export function useIsMobile(): boolean {
  return React.useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false, // server render: assume desktop, as the template did
  );
}
