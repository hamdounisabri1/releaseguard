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
```

The browser talks to the API at `NEXT_PUBLIC_API_BASE_URL`, the **only** public variable (see `lib/env.ts`). For local development, put it in `frontend/.env.local` (value in the repo's `.env.example`). Unset, it defaults to the same-origin `/api/v1` that Caddy serves in production.

## Layout

```text
app/
  layout.tsx              root layout: fonts, metadata, TooltipProvider (no shell, so /login can render bare)
  (app)/layout.tsx        app shell: sidebar + top bar
  (app)/dashboard/        dashboard (placeholder until SCRUM-28)
  (app)/[...slug]/        catch-all → notFound(), so unknown URLs get a 404 inside the shell
  (app)/not-found.tsx     the 404 page
components/
  layout/                 app-sidebar.tsx, top-bar.tsx
  ui/                     shadcn primitives (add with `pnpm dlx shadcn@latest add <name>`)
hooks/                    use-mobile.ts
lib/                      navigation.ts (sidebar items), env.ts, utils.ts
services/                 every API call lives here (SCRUM-27)
types/                    generated from the backend OpenAPI (openapi-typescript, SCRUM-27)
```

Routes to come ([guide §5.6](../docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout)): login, applications/[appId], deployments/[deploymentId], approvals, environments, settings. Pages that need the shell go under `app/(app)/`.

Rules: [frontend.md](../.claude/rules/frontend.md) · [testing.md](../.claude/rules/testing.md) · [security.md](../.claude/rules/security.md). Next.js API docs for this exact version ship in `node_modules/next/dist/docs/` (see `AGENTS.md`).
