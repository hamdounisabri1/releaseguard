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
Open <https://smee.io/new> and copy the channel URL (`https://smee.io/<random>`). The client that forwards it to your machine is in [Run the webhook tunnel](#run-the-webhook-tunnel). smee.io **does not store** events: anything delivered while no client is connected is lost, although GitHub records it as delivered. Use **Redeliver** to get it again.

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
3. **Nothing leaked into the repo:** `git status` is clean apart from intended changes, `git ls-files '*.pem'` prints nothing, and the pre-commit gitleaks hook passes on every commit. For a full-history scan on demand, use a gitleaks binary: `gitleaks git --redact .`.
4. **Webhook reaches your machine:** follow [Run the webhook tunnel → Verify](#verify-a-real-delivery). Note that **Recent deliveries** shows a green tick (smee.io answered 200) whether or not anything on your machine received the event; only the receiver's log proves it arrived.

## Run the webhook tunnel

**Tool: smee.io** (SCRUM-9). The development App's webhook URL is a smee channel, so it never changes between sessions. A client on your machine holds an open connection to the channel and replays each event as a POST to the local endpoint. cloudflared is the fallback for one case (see [Signatures through smee](#signatures-through-smee)).

| | smee.io (default) | cloudflared quick tunnel (fallback) |
|---|---|---|
| Public URL | Stable channel URL, set once in the App | New random `*.trycloudflare.com` URL on every start; update the App's webhook URL each time |
| Body bytes | Re-serialized JSON (see below) | Byte-exact |
| Tunnel down | smee.io still answers 200; the event is **lost** (Redeliver it) | GitHub records a failed delivery; Redeliver it |
| Install | Node only (`npx`) | `winget install Cloudflare.cloudflared` |

### Start
Two terminals. Before the backend's webhook endpoint exists (SCRUM-45), the stand-in receiver [`infra/scripts/webhook_echo.py`](../infra/scripts/webhook_echo.py) listens on the same path. It logs only event, delivery id, action, size and the HMAC result, never the body or the secret.

```powershell
# Terminal 1: the receiver on http://127.0.0.1:8000/api/v1/github/webhooks
#   now:   the stand-in (paste the webhook secret only into this terminal's environment)
$env:GITHUB_WEBHOOK_SECRET = "<value from your .env>"; py -3 infra/scripts/webhook_echo.py
#   later: the real backend instead (SCRUM-45+), which reads the secret from .env
#   cd backend; uv run uvicorn app.main:app --reload

# Terminal 2: the tunnel (pinned client version; Node is enough, no global install)
npx -y smee-client@5.0.0 --url https://smee.io/<your-channel> --target http://127.0.0.1:8000/api/v1/github/webhooks
```

The client prints `Connected to https://smee.io/<your-channel>`, then one `POST … - <status>` line per forwarded event.

### Stop
`Ctrl+C` in both terminals. Stop the stand-in before starting the backend, since both use port 8000.

### Verify a real delivery
1. Start both terminals as above.
2. App settings → **Advanced → Recent deliveries**. Open any delivery (the installation event, or a `workflow_run` from a `taskflow` run; push a commit to `taskflow` if the list is empty) and click **Redeliver**.
3. The smee client prints `POST http://127.0.0.1:8000/api/v1/github/webhooks - 202`, and the receiver prints `event=… delivery=<the GUID shown in GitHub> … signature=valid`.

`signature=INVALID` means the secret in terminal 1 doesn't match the App's (fix it), or the payload hit the smee limitation below.

### Tunnel down (failure path)
- **Client stopped:** smee.io still returns 200 to GitHub, so the delivery shows as delivered, but it reached nothing. **Receiver stopped, client running:** the client logs `TypeError: fetch failed … ECONNREFUSED 127.0.0.1:8000` and the event is dropped.
- Either way: restart what was down, then **Redeliver** the affected deliveries from **Recent deliveries** (GitHub keeps them for 3 days). The same delivery GUID comes back, so the real endpoint's `X-GitHub-Delivery` de-duplication handles a redelivery of something it already processed.
- In the product, lost `workflow_run` events are also recovered by the reconcile sweep ([guide §10.3](DEVELOPMENT_LIFECYCLE.md#103-dispatch-inputs-correlation-and-callbacks)), so the tunnel is never the only path. In local dev, Redeliver is quicker.

### Signatures through smee
smee forwards `JSON.stringify(JSON.parse(body))`, not the original bytes. Tested 24 Nov 2026 with smee-client 5.0.0: compact JSON with raw UTF-8 and emoji keeps a valid `X-Hub-Signature-256`. `\uXXXX` and `\/` escapes, integers above 2^53, and floats such as `1.0` are rewritten, so the HMAC fails. GitHub sends compact JSON, so normal deliveries verify. If one delivery fails with `signature=INVALID` while others pass, replay it through cloudflared before debugging the endpoint:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
# set the App's webhook URL to https://<printed-host>.trycloudflare.com/api/v1/github/webhooks, Redeliver,
# then set it back to the smee channel URL
```

Never weaken the endpoint's HMAC check to make a tunnel work.

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
