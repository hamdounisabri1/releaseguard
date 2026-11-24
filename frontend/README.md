# frontend/

Next.js web UI (App Router, TypeScript, Tailwind, shadcn/ui, TanStack Query).

> **Placeholder.** No code yet. Sprint 1 fills this in, starting with SCRUM-26 (app shell).
>
> **Note for SCRUM-26:** `create-next-app` refuses to scaffold into a folder that already contains this README. Scaffold into a temporary folder and move the files in, or delete this README first.

Planned layout ([guide §5.6](../docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout)):

```text
app/          login, dashboard, applications/[appId], deployments/[deploymentId],
              approvals, environments, settings
components/   feature folders + ui/ (shadcn primitives)
hooks/
services/     every API call lives here
types/        generated from the backend OpenAPI (openapi-typescript)
lib/
```

Rules: [frontend.md](../.claude/rules/frontend.md) · [testing.md](../.claude/rules/testing.md) · [security.md](../.claude/rules/security.md)
