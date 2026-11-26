#!/usr/bin/env bash
# Apply ReleaseGuard's GitHub repository hygiene to one repository.
# Idempotent: safe to re-run. Needs `gh` logged in as a repo admin.
#
#   infra/github/setup-repo.sh hamdounisabri1/releaseguard
#   infra/github/setup-repo.sh hamdounisabri1/taskflow
#
# 1. Merge settings: rebase-merge only (main keeps every commit), delete branch on merge.
# 2. Labels: the set from docs/PROJECT_PLAN.md §5; GitHub's default labels are removed.
# 3. Ruleset `protect-main` (ruleset-main.json): PR required, rebase-merge only, no force-push,
#    no deletion, linear history, no bypass actors.
# 4. Ruleset `ci-required` (ruleset-ci-<repo-name>.json, if present): required CI status checks.
set -euo pipefail

repo="${1:?usage: setup-repo.sh <owner/repo>}"
here="$(cd "$(dirname "$0")" && pwd)"
ruleset_file="$here/ruleset-main.json"
ruleset_name="protect-main"

echo "== $repo: merge settings"
gh api -X PATCH "repos/$repo" --silent \
  -F allow_squash_merge=false \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=true \
  -F delete_branch_on_merge=true

echo "== $repo: labels"
# name|color|description (keep in sync with docs/PROJECT_PLAN.md §5 "Labels")
labels=(
  "area:api|1d76db|Backend API (FastAPI routes, services)"
  "area:web|1d76db|Frontend (Next.js)"
  "area:worker|1d76db|Worker: job loop and sweeps"
  "area:db|1d76db|Models, migrations, constraints"
  "area:github|1d76db|GitHub App, webhooks, workflows"
  "area:ai|1d76db|AIService and AI worker jobs"
  "area:infra|1d76db|Docker, Compose, Caddy, VPS, repo settings"
  "area:docs|1d76db|Documentation"
  "type:feature|0e8a16|New functionality"
  "type:bug|d73a4a|Something is broken"
  "type:chore|c5def5|Tooling, setup, maintenance"
  "type:test|bfd4f2|Tests only"
  "type:spike|d4c5f9|Time-boxed investigation"
  "sprint:0|ededed|Sprint 0: Setup"
  "sprint:1|ededed|Sprint 1"
  "sprint:2|ededed|Sprint 2"
  "sprint:3|ededed|Sprint 3"
  "sprint:4|ededed|Sprint 4"
  "sprint:5|ededed|Sprint 5"
  "sprint:6|ededed|Sprint 6"
  "p0|b60205|MVP-critical"
  "p1|fbca04|MVP"
  "p2|c2e0c6|Stretch, cut first"
)
for entry in "${labels[@]}"; do
  IFS='|' read -r name color description <<<"$entry"
  gh label create "$name" -R "$repo" --color "$color" --description "$description" --force >/dev/null
done
echo "   ${#labels[@]} labels created or updated"

defaults=(bug documentation duplicate enhancement "good first issue" "help wanted" invalid question wontfix accessibility)
existing="$(gh label list -R "$repo" --limit 200 --json name --jq '.[].name')"
for name in "${defaults[@]}"; do
  if grep -qxF "$name" <<<"$existing"; then
    gh label delete "$name" -R "$repo" --yes >/dev/null
    echo "   removed default label: $name"
  fi
done

echo "== $repo: ruleset $ruleset_name"
ruleset_id="$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$ruleset_name\") | .id")"
if [[ -n "$ruleset_id" ]]; then
  gh api -X PUT "repos/$repo/rulesets/$ruleset_id" --input "$ruleset_file" --silent
  echo "   updated ruleset $ruleset_id"
else
  ruleset_id="$(gh api -X POST "repos/$repo/rulesets" --input "$ruleset_file" --jq '.id')"
  echo "   created ruleset $ruleset_id"
fi

# Optional per-repo ruleset `ci-required` (ruleset-ci-<repo-name>.json): CI jobs that must pass
# before a PR can merge. A separate ruleset, so each repo lists its own job names and the shared
# protect-main file stays the same for both repos.
ci_ruleset_file="$here/ruleset-ci-${repo#*/}.json"
ci_ruleset_name="ci-required"
if [[ -f "$ci_ruleset_file" ]]; then
  echo "== $repo: ruleset $ci_ruleset_name"
  ci_ruleset_id="$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$ci_ruleset_name\") | .id")"
  if [[ -n "$ci_ruleset_id" ]]; then
    gh api -X PUT "repos/$repo/rulesets/$ci_ruleset_id" --input "$ci_ruleset_file" --silent
    echo "   updated ruleset $ci_ruleset_id"
  else
    ci_ruleset_id="$(gh api -X POST "repos/$repo/rulesets" --input "$ci_ruleset_file" --jq '.id')"
    echo "   created ruleset $ci_ruleset_id"
  fi
fi

echo "== $repo: done"
