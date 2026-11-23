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
- Fetch data with TanStack Query. Poll in-progress deployments (Deploying, Verifying) until they reach a terminal state.
- Forms: React Hook Form + Zod. The backend validates again, and its 422 errors are shown next to the matching field.
- Sessions use an `HttpOnly` cookie. Never read or store tokens in JS. Send requests `credentials: "include"`.
- The only environment variable available in the browser is `NEXT_PUBLIC_API_BASE_URL`.

## UI rules
- Every major screen has **empty, loading, error and permission-denied** states, using shared components.
- Hiding controls by role is a UX nicety only. The backend enforces permissions. Handle 403 and 404 gracefully.
- Always show **environment and version** next to a deployment status.
- Keep **deployment status** and **environment health** visually distinct. A deployment can succeed while the app is unhealthy.
- One status vocabulary and color map, defined in one place: Succeeded = green, Unhealthy = amber, Failed = red, Awaiting approval = blue (others neutral).
- Production deploys and rollbacks need a confirmation dialog that shows **current vs. target version**. Rollback needs a reason.
- Show approver identity and timestamp wherever an approval appears. Label AI probable causes **"AI-generated hypothesis"**.
- Store timestamps in UTC and render them in the user's local time.

## Quality
- `pnpm eslint .`, `pnpm tsc --noEmit` and `pnpm build` must pass. No `any` in API-facing code.
