# GitHub App Setup & Webhook Integration Guide

This guide walks through creating and configuring a **GitHub App** for automated, multi-file architectural and security PR code reviews with **AICR (AI Code Reviewer)**.

---

## 1. Create the GitHub App

1. Navigate to your GitHub account or organization settings:
   - **Personal Account:** [GitHub Settings → Developer settings → GitHub Apps](https://github.com/settings/apps)
   - **Organization:** `https://github.com/organizations/<YOUR_ORG>/settings/apps`
2. Click **New GitHub App**.
3. Fill in the app basics:
   - **GitHub App name:** `AICR-Code-Reviewer` (or your preferred name)
   - **Homepage URL:** `https://github.com/your-org/ai-code-reviewer` (or your dashboard URL)
   - **Webhook URL:** `https://<YOUR_TUNNEL_DOMAIN>/webhooks/github` (see [Local Testing with a Tunnel](#4-local-testing-with-a-tunnel))
   - **Webhook secret:** Enter a strong secret string (e.g. generated with `openssl rand -hex 32`).

---

## 2. Configure Permissions & Subscribed Events

### Repository Permissions

Configure the exact least-privilege permissions required:

| Permission | Access | Purpose |
| :--- | :--- | :--- |
| **Pull requests** | **Read & write** | Read PR metadata, diffs, and post structured reviews with inline committable suggestions (`POST /repos/{owner}/{repo}/pulls/{n}/reviews`) |
| **Contents** | **Read-only** | Read repository file contents for Tree-sitter AST and Semgrep SAST cross-file analysis |
| **Metadata** | **Read-only** | Required default by GitHub for repo identification |

> [!NOTE]
> Do NOT grant write permissions to **Contents** unless you explicitly intend to enable the automated autofix commit feature on external branches.

### Subscribed Webhook Events

Check the box for the following event under **Subscribe to events**:
- [x] **Pull request** (triggers on `opened`, `synchronize`, `reopened`)

---

## 3. Generate and Download Private Key

1. Under the **Private keys** section of your GitHub App settings page, click **Generate a private key**.
2. A `.pem` file will download to your machine (e.g., `aicr-code-reviewer.2026-10-29.private-key.pem`).
3. Note your **App ID** displayed at the top of the **General** page (e.g. `123456`).
4. Install the app on your user account or target repositories via **Install App** in the sidebar. Note the **Installation ID** (visible in the URL after installing: `https://github.com/settings/installations/<INSTALLATION_ID>`).

---

## 4. Local Testing with a Tunnel

To test GitHub App webhooks locally against your running API Gateway on `http://127.0.0.1:8000`:

### Option A: Using Smee.io (Recommended for Webhooks)

1. Go to [https://smee.io](https://smee.io) and click **Start a new channel**. Copy the generated URL (e.g., `https://smee.io/abc123xyz`).
2. Set your GitHub App's **Webhook URL** to your Smee channel URL.
3. Install and run the Smee client locally:
   ```bash
   npm install --global smee-client
   smee -u https://smee.io/abc123xyz -t http://127.0.0.1:8000/webhooks/github
   ```

### Option B: Using Cloudflare Tunnel or ngrok

```bash
# Using Cloudflare Tunnel
cloudflared tunnel --url http://127.0.0.1:8000

# Or using ngrok
ngrok http 8000
```
Update your GitHub App's **Webhook URL** to:
`https://<your-subdomain>.ngrok-free.app/webhooks/github`

---

## 5. Configure Local Environment (.env)

Add the following environment variables to your `.env` file:

```env
# GitHub App Authentication
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="/path/to/aicr-code-reviewer.private-key.pem"
GITHUB_WEBHOOK_SECRET="your_webhook_secret_here"
```

> [!TIP]
> `GITHUB_APP_PRIVATE_KEY` can either be a path to the downloaded `.pem` file on disk or the raw PEM string itself (with `\n` linebreaks).

---

## 6. Verifying the Integration

1. Start your API Gateway:
   ```bash
   .venv/bin/uvicorn src.main:app --app-dir apps/api-gateway --host 127.0.0.1 --port 8000 --reload
   ```
2. Open or push a new commit (`synchronize`) to a Pull Request in a repository where the GitHub App is installed.
3. Check the API Gateway logs:
   ```text
   INFO: Webhook signature verified with HMAC-SHA256
   INFO: Review job dispatched for PR #12
   INFO: Successfully posted review on owner/repo PR #12
   ```
4. The PR will receive **ONE unified review** with:
   - Committable suggestion blocks on modified lines.
   - Out-of-diff findings rendered under the summary comment to avoid 422 errors.
   - Full telemetry recorded in the PostgreSQL dashboard database.

