# frontend/

Next.js web UI: **Next.js 16.4** (App Router, Cache Components), TypeScript, Tailwind CSS 4 and shadcn/ui (Radix). TanStack Query arrives with SCRUM-27.

## Run it

Needs Node 22 LTS and pnpm 10 (pinned in `package.json`; install it once with `corepack install -g pnpm@10.34.9`).

```bash
pnpm install
pnpm dev                 # http://localhost:3000  (/ redirects to /dashboard)
pnpm lint                # ESLint, zero warnings
pnpm typecheck           # next typegen + tsc --noEmit
pnpm build               # production build
pnpm format              # Prettier (format:check in CI and pre-commit)
pnpm test                # Vitest unit tests (*.test.ts/tsx)
pnpm api:types           # regenerate types/api.ts from the running backend
```

The browser talks to the API at `NEXT_PUBLIC_API_BASE_URL`, the **only** public variable (see `lib/env.ts`). For local development, put it in `frontend/.env.local` (value in the repo's `.env.example`). Unset, it defaults to the same-origin `/api/v1` that Caddy serves in production. It must end in `/api/v1`: the generated paths already carry that prefix, so the client uses only the part before it.

## Layout

```text
app/
  layout.tsx              root layout: fonts, metadata, TooltipProvider (no shell, so /login can render bare)
  (app)/layout.tsx        app shell: sidebar + top bar
  (app)/dashboard/        dashboard (placeholder until SCRUM-28)
  (app)/[...slug]/        catch-all → notFound(), so unknown URLs get a 404 inside the shell
  (app)/not-found.tsx     the 404 page (EmptyState)
  (app)/loading.tsx       skeleton while a page loads (LoadingState)
  (app)/error.tsx         error boundary for every shell page (ApiErrorState, retry)
components/
  layout/                 app-sidebar.tsx, top-bar.tsx
  ui/                     shadcn primitives (add with `pnpm dlx shadcn@latest add <name>`)
hooks/                    use-mobile.ts
  providers/              query-provider.tsx (TanStack Query, in the root layout)
  states/                 empty, loading, error, permission-denied + ApiErrorState (picks one from an error)
lib/                      navigation.ts (sidebar items), env.ts, query-client.ts (retry rules), utils.ts
services/                 every API call: api.ts (typed client, ApiError, 401 → /login), one file per area
types/api.ts              generated from the backend OpenAPI; never edit by hand
scripts/api-types.mjs     regenerates types/api.ts
```

## Calling the API

```ts
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/services/api";

const me = useQuery({
  queryKey: ["auth", "me"],
  queryFn: () => unwrap(api.GET("/api/v1/auth/me")),
});
```

`api` is an [openapi-fetch](https://openapi-ts.dev/openapi-fetch/) client typed by `types/api.ts`, so paths, params, bodies and responses are checked by `tsc`. It sends the session cookie (`credentials: "include"`). `unwrap` returns the data or throws an `ApiError` (`status`, `code`, `message`, `details` from the backend's `{"error": {…}}` shape). Any 401 sends the browser to `/login?next=<current path>`. Queries retry network errors, 5xx and 429 twice, never another 4xx (`isRetryable` in `lib/query-client.ts`, also used by the error state's "Try again").

After a backend API change, regenerate the types with the backend running (`uv run uvicorn app.main:app` in `backend/`):

```bash
pnpm api:types                   # from http://localhost:8000/openapi.json (override with OPENAPI_URL)
pnpm api:types ../openapi.json   # or from a file: uv run python -m app.scripts.export_openapi ../openapi.json
```

CI regenerates them from the backend and fails if `types/api.ts` differs.

Routes to come ([guide §5.6](../docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout)): login, applications/[appId], deployments/[deploymentId], approvals, environments, settings. Pages that need the shell go under `app/(app)/`.

Rules: [frontend.md](../.claude/rules/frontend.md) · [testing.md](../.claude/rules/testing.md) · [security.md](../.claude/rules/security.md). Next.js API docs for this exact version ship in `node_modules/next/dist/docs/` (see `AGENTS.md`).
