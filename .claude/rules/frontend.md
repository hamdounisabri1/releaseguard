---
paths:
  - "frontend/**"
---

# Frontend rules (Next.js App Router, TypeScript, Tailwind, shadcn/ui)

## Before building UI
- Use the **`ui-ux-pro-max`** skill for layout, color, typography, accessibility and component decisions. Use `--stack nextjs` / `--stack shadcn` for stack-specific guidance.
- Check Next.js, TanStack Query and shadcn/ui APIs with **context7**. The App Router changes often.
- After a UI change, verify it in a real browser with the **`webapp-testing`** skill. On Windows, **don't use its `with_server.py`** (it leaves `node` running and can hang on full pipes): start the app as a background task (`pnpm dev` or `docker compose … up`), then run the Playwright script directly. The skill's script paths are relative to `.claude/skills/webapp-testing/`, not the repo root.

## Structure and data
- Routes in `app/` (login, dashboard, applications/[appId], deployments/[deploymentId], approvals, environments, settings). Feature components in `components/<feature>/`, primitives in `components/ui/`.
- Put all API calls in `services/`, using types **generated from the backend OpenAPI** (`openapi-typescript`) in `types/`. Don't hand-write API response types.
- Fetch data with TanStack Query. Poll active deployments (Queued, Deploying, Verifying) until they reach a terminal state.
- Forms: React Hook Form + Zod. The backend validates again, and its 422 errors are shown next to the matching field.
- Sessions use an `HttpOnly` cookie. Never read or store tokens in JS. In production the API is same-origin (`/api/v1` behind Caddy); send requests with `credentials: "include"` so local dev on separate ports works too.
- The only environment variable available in the browser is `NEXT_PUBLIC_API_BASE_URL`.

## UI rules
- Every major screen has **empty, loading, error and permission-denied** states, using shared components.
- Hiding controls by role is a UX nicety only. The backend enforces permissions. Handle 403 and 404 gracefully.
- Always show **environment and version** next to a deployment status.
- Keep **deployment status** and **environment health** visually distinct. A deployment can succeed while the app is unhealthy.
- One status vocabulary and color map, defined in one place, for the states in guide §8: Succeeded = green, Unhealthy = amber, Failed = red, Awaiting approval = blue, Queued/Deploying/Verifying = neutral with a progress indicator, Rejected/Expired/Cancelled = neutral. Environment health (Healthy/Unhealthy/Unknown) uses its own badge.
- A 409 `environment_busy` means another deployment is active in that environment: show which one and link to it.
- Production deploys and rollbacks need a confirmation dialog that shows **current vs. target version**. Rollback needs a reason.
- Show approver identity and timestamp wherever an approval appears. Label AI probable causes **"AI-generated hypothesis"**.
- Store timestamps in UTC and render them in the user's local time.

## Stack notes (Next.js 16.4, SCRUM-26)
- **Cache Components and Partial Prefetching are on** (`next.config.ts`). Read the matching guide in `frontend/node_modules/next/dist/docs/` before using a Next.js API (see `frontend/AGENTS.md`); this is also the fallback when context7 isn't available.
- Pages that need the app shell go under the `app/(app)/` route group. The root layout stays bare (for `/login`). Unknown URLs hit `app/(app)/[...slug]`, which calls `notFound()`, so a 404 renders inside the shell.
- shadcn/ui uses the Radix base with the Nova preset, a slate palette and `cn` from the `cn` package. Dark mode follows the OS (`prefers-color-scheme`). Add primitives with `pnpm dlx shadcn@latest add <name>`, then run `pnpm lint`: generated code must pass the React Compiler rules (`use-mobile.ts` had to be rewritten).
- Sidebar items come from `lib/navigation.ts`. The only public env var is read in `lib/env.ts`.

## Quality
- `pnpm lint`, `pnpm typecheck` (runs `next typegen`, then `tsc --noEmit`, so `LayoutProps` exists on a fresh clone) and `pnpm build` must pass. `pnpm format:check` must be clean. No `any` in API-facing code.

## Lessons learned
- **On Windows, run a Node tool's JS entry with `node`, never its `node_modules/.bin/*.cmd` shim, when the arguments include file paths.** Why: the shim goes through `cmd.exe`, which breaks on `(` and `)` in route-group paths such as `app/(app)/…`. (2026-11-25, SCRUM-26)
