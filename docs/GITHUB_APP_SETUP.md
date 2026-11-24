# GitHub App setup

ReleaseGuard talks to GitHub only through a **GitHub App**. The worker uses it to dispatch TaskFlow's `deploy.yml` and read run status. GitHub sends `workflow_run` webhooks back to it. There are two Apps, and they never share keys or secrets:

| App | Used by | Webhook URL | Ticket |
|---|---|---|---|
| **Development** | Local stack on your machine | A smee.io channel (or a cloudflared tunnel) forwarding to `http://localhost:8000/api/v1/github/webhooks` | SCRUM-8 (registration), SCRUM-9 (tunnel) |
| **Production** | The VPS demo | `https://<host>/api/v1/github/webhooks` | SCRUM-95 |

Design background: [guide §10.4](DEVELOPMENT_LIFECYCLE.md#104-github-app), [`security.md`](../.claude/rules/security.md#github-and-webhooks), [ADR-0005](adr/0005-single-deploy-workflow.md).

## The contract (both Apps)

| Setting | Value | Why |
|---|---|---|
| Repository permissions | **Actions: Read and write** · **Contents: Read-only** · **Metadata: Read-only** | Dispatch `deploy.yml`, read runs and job logs, read the workflow file. Metadata is mandatory |
| Organization and account permissions | **None** | |
| Subscribed events | **Workflow run** only | Status sync. No `push`, `deployment` or `check_run` |
| Where it can be installed | **Only on this account** | |
| Installed on | **`taskflow` only** (Only select repositories) | Least privilege. Never "All repositories" |
| User authorization (OAuth), device flow, callback URL | Off / empty | ReleaseGuard has its own login; the App never acts as a user |
| Webhook secret | 32 random bytes, hex | HMAC-SHA256 check of `X-Hub-Signature-256` |
| Private key | A `.pem` file **outside the repo** | Signs the App JWT that is exchanged for installation tokens |

Anything beyond this table is a defect. If a later feature seems to need another permission or event, write an ADR first.

## Register the development App

Takes about 15 minutes. Do it in a browser signed in as the account that owns `taskflow`.

### 1. Create a webhook channel
Open <https://smee.io/new> and copy the channel URL (`https://smee.io/<random>`). SCRUM-9 starts the client that forwards it to the local backend. Until then, deliveries simply queue up in the channel and in the App's **Advanced → Recent deliveries** list.

> The smee URL is not a secret, but anyone who has it can read the payloads. That is acceptable here because `taskflow` is public and every delivery is still HMAC-verified. Never point a smee channel at a private repository's App.

### 2. Generate the webhook secret
In a terminal, generate it and keep the window open (you paste it twice: into GitHub, then into `.env`):

```powershell
py -3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Fill in the form
Go to **Settings → Developer settings → GitHub Apps → New GitHub App** (<https://github.com/settings/apps/new>).

| Field | Value |
|---|---|
| GitHub App name | `releaseguard-dev-<your-login>` (names are global, max 34 characters) |
| Description | `ReleaseGuard development App (local stack). Dispatches deploy.yml and receives workflow_run events.` |
| Homepage URL | The `releaseguard` repository URL |
| Callback URL | *empty* |
| Expire user authorization tokens | leave the default (unused) |
| Request user authorization (OAuth) during installation | **unchecked** |
| Enable Device Flow | **unchecked** |
| Setup URL | *empty* for now. The install callback (`/api/v1/integrations/github/callback`) is built in Sprint 2/3 |
| Webhook: Active | **checked** |
| Webhook URL | the smee channel URL from step 1 |
| Webhook secret | the value from step 2 |
| SSL verification | **Enabled** |
| Repository permissions | Actions **Read and write**, Contents **Read-only**, Metadata **Read-only** (preselected). Everything else **No access** |
| Organization permissions | all **No access** |
| Account permissions | all **No access** |
| Subscribe to events | **Workflow run** only (the checkbox appears once Actions is selected) |
| Where can this GitHub App be installed? | **Only on this account** |

Click **Create GitHub App**.

### 4. Note the App ID and generate the private key
On the App's **General** page:
1. Copy the **App ID** (a number). It goes in `.env` as `GITHUB_APP_ID`. It is not secret.
2. Under **Private keys**, click **Generate a private key**. The browser downloads `<app-name>.<date>.private-key.pem`.
3. Move the file out of `Downloads` into a folder **outside any repository**, and make it readable only by you:

   ```powershell
   $dir = "$HOME\.releaseguard"
   New-Item -ItemType Directory -Force $dir | Out-Null
   Move-Item "$HOME\Downloads\releaseguard-dev-*.private-key.pem" "$dir\github-app-dev.pem"
   icacls "$dir\github-app-dev.pem" /inheritance:r /grant:r "$($env:USERNAME):(R)"
   ```

   On Linux or macOS: `~/.releaseguard/github-app-dev.pem` with `chmod 600`.

Never copy the key into the repository, a chat, a Jira comment or a screenshot. `.gitignore` ignores `*.pem` as a backstop, not as the plan.

### 5. Install it on `taskflow` only
In the App's sidebar, click **Install App** → **Install** next to your account → **Only select repositories** → pick **`taskflow`** → **Install**.

The browser lands on `https://github.com/settings/installations/<installation-id>`. The id doesn't go in `.env`: the backend stores it in `integrations.installation_id` once the install callback exists. Note it anyway, for testing before then.

### 6. Fill in your local `.env`
Copy `.env.example` to `.env` (git-ignored) if you haven't already, then set:

```dotenv
GITHUB_APP_ID=<App ID from step 4>
GITHUB_APP_PRIVATE_KEY_PATH=C:/Users/<you>/.releaseguard/github-app-dev.pem
GITHUB_WEBHOOK_SECRET=<value from step 2>
```

Use forward slashes in the path. Close the terminal from step 2.

## Verify

1. **Permissions and events** (read from the GitHub API, no secrets involved):

   ```bash
   gh api apps/<app-slug> --jq '{permissions, events}'
   ```

   (No leading slash: Git Bash on Windows rewrites `/apps/…` into a filesystem path.)

   Expected output, exactly:

   ```json
   {"events":["workflow_run"],"permissions":{"actions":"write","contents":"read","metadata":"read"}}
   ```

   Any extra key in `permissions` or `events` fails the check: edit the App (**Permissions & events**) and remove it.
2. **Installation scope:** <https://github.com/settings/installations> → **Configure** next to the App shows **Only select repositories: `taskflow`**.
3. **Nothing leaked into the repo:** `git status` is clean apart from intended changes, `git ls-files '*.pem'` prints nothing, and gitleaks finds nothing once it is installed (SCRUM-10).
4. **Webhook reaches GitHub's side:** after the next `taskflow` workflow run, **Advanced → Recent deliveries** on the App page lists a `workflow_run` delivery. It shows as failed until the tunnel and endpoint exist (SCRUM-9, SCRUM-45); that's expected.

## Rotation and incidents

| Event | Do this |
|---|---|
| Private key exposed (committed, pasted, sent) | Immediately: App page → **Private keys** → **Delete** the exposed key, then generate a new one and update the file. Deleting the key revokes it; rewriting git history does not |
| Routine key rotation | Generate a second key, switch `GITHUB_APP_PRIVATE_KEY_PATH` to it, restart backend and worker, then delete the old key in GitHub |
| Webhook secret exposed or rotated | Generate a new one, set it in the App (**General → Webhook secret**) and in `.env`, then restart the backend. Deliveries signed with the old secret are rejected with 401 |
| Machine lost or reinstalled | Delete all the dev App's private keys in GitHub and generate a new one |

## Production App (SCRUM-95)

Same contract and steps, with these differences:
- Name `releaseguard-<your-login>`, webhook URL `https://<host>/api/v1/github/webhooks` (no tunnel), Setup URL set to the install callback once it exists.
- New webhook secret and private key. **Never reuse the development values.**
- The key file lives on the VPS beside the env file (owned by the deploy user, `chmod 600`) and is mounted read-only into the backend and worker containers. `GITHUB_APP_PRIVATE_KEY_PATH` points at the path inside the container.
