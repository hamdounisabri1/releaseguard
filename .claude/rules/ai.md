---
paths:
  - "backend/app/services/ai*"
  - "backend/app/services/ai/**"
  - "backend/app/worker/*ai*"
  - "backend/app/worker/**/*ai*"
  - "backend/app/schemas/ai*"
---

# AI assistant rules

## Boundary
- AI **explains and recommends only**. It never approves, dispatches, rolls back, or picks commands, repositories, refs or targets. No tool use and no function calling that touches operations.
- AI runs only as a **worker job** (`jobs.kind` = `ai_analysis` or `ai_release_notes`). `transition()` enqueues an analysis when a deployment becomes Failed or Unhealthy and AI is enabled. A deployment never waits on AI, and a provider outage never changes deployment state.
- If `AI_API_KEY` is empty, AI is disabled and every other feature works normally.

## AIService
- Everything goes through `AIService` (provider adapter chosen by `AI_PROVIDER` and `AI_MODEL`). No direct provider SDK calls elsewhere.
- Methods: `analyze_deployment_failure`, `summarize_pipeline_logs`, `generate_release_notes`, and (stretch, first on the cut list) `compare_deployment_failures`.
- If the provider is Claude, load the **`claude-api`** skill before writing provider code (model IDs, SDK usage, structured output).

## Input safety
- **Sanitize before sending:** redact tokens, keys, passwords, connection strings, emails and private keys. Cap the size. Send only relevant excerpts (the failed step and its surrounding lines).
- Fetch logs from the GitHub API on the backend with the installation token. The token never reaches the model or the frontend.
- Treat logs, commit messages and PR text as **untrusted data**. Wrap them in clear delimiters and tell the model not to follow instructions inside them.
- Check workspace and application authorization **before** pulling any historical data into a prompt.

## Output
- Validate the response with a Pydantic schema: `summary`, `category`, `severity`, `probable_cause`, `evidence`, `recommendations`. If validation fails, store and show **"analysis unavailable"** with a retry option. Never show raw model output.
- Store `model_provider`, the model ID, `analysis_version`, `created_at` and `deployment_id` in `ai_failure_reports`.
- The UI labels `probable_cause` **"AI-generated hypothesis"**.

## Tests
- Sanitizer unit tests (secrets never leave the system), schema tests with good and bad payloads, a provider-timeout test, and a prompt-injection fixture. Use a fake provider in CI and never the real API.
