/**
 * Browser-visible configuration. `NEXT_PUBLIC_API_BASE_URL` is the ONLY public
 * variable (security.md); every secret stays on the backend. In production the API
 * is same-origin behind Caddy, so the default is the relative `/api/v1`. An empty
 * value (`NEXT_PUBLIC_API_BASE_URL=`) also falls back to it, hence `||` rather than `??`.
 * It must end in `/api/v1` (services/api.ts strips it: the generated paths carry the prefix).
 */
export const apiBaseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "/api/v1";
