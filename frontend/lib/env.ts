/**
 * Browser-visible configuration. `NEXT_PUBLIC_API_BASE_URL` is the ONLY public
 * variable (security.md); every secret stays on the backend. In production the API
 * is same-origin behind Caddy, so the default is the relative `/api/v1`.
 */
export const apiBaseUrl: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
