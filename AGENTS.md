# AGENTS.md — SAST-LLM Review Engine

## Project Overview
An open-source, self-hostable, multi-VCS AI code review assistant and engineering quality dashboard. It integrates with GitHub Pull Requests and GitLab Merge Requests to deliver cross-file architectural reviews and deterministic security flags, backed by a QLoRA/DPO fine-tuning pipeline and a Next.js analytics dashboard.

Positioning: deterministic security gating (Semgrep + CWE mapping), local-model support (Qwen2.5-Coder), and transparent, reproducible evaluation. We do not claim parity or superiority over commercial tools unless a benchmark we ran supports it.

## Monorepo Directory Structure
- `apps/api-gateway/`: FastAPI service for GitHub/GitLab webhooks, REST APIs for the dashboard, and authentication.
- `packages/context-engine/`: Tree-sitter AST parser, 2-hop call-graph builder, and Qdrant vector/symbol indexer.
- `packages/review-worker/`: Semgrep SAST runner, cross-file context assembly, AI model calls, anti-noise filtering, and VCS comment posting. (Verify whether execution is currently in-process or via Celery/Redis. See "Verify Before Assuming".)
- `packages/ml-pipeline/`: Dataset curation, Unsloth QLoRA fine-tuning (`Qwen/Qwen2.5-Coder-7B-Instruct`), TRL DPO alignment, and the benchmark harness.
- `apps/dashboard/`: Next.js (App Router, TypeScript, Tailwind CSS, Recharts) quality dashboard.
- `infra/`: `docker-compose.yml` for PostgreSQL, Redis, and Qdrant, plus environment templates.

## Verify Before Assuming
This file describes the target architecture. The code is the source of truth.
- Before any task, read the code in the area you will touch and state what actually exists versus what this file describes.
- If a module, queue, table, or endpoint mentioned here is missing, say so and ask before building around it.
- If a requirement is ambiguous, stop and ask rather than guessing.

## Strict Engineering Standards
1. **No Naive Diff Wrappers**: Never send raw `git diff` strings to an LLM without first enriching them with AST symbol definitions, imported type signatures, and caller/callee context from `packages/context-engine/`.
2. **Strict Output Schema**: All AI review generations must validate against the Pydantic v2 `ReviewFinding` schema: `file_path`, `start_line`, `end_line`, `category` (`architecture` | `security` | `performance` | `concurrency` | `bug`), `severity` (`critical` | `high` | `medium`), `confidence` (`0.0`–`1.0`), `explanation`, `suggested_code` (exact replacement block). Findings that fail validation (including unknown categories such as `style_nitpick`) must be dropped and counted as suppressed noise, never crash the review.
3. **Anti-Noise Gate**: Drop any finding with `confidence < 0.80` or `category == "style_nitpick"`. Never weaken this gate to produce more findings. Per-repo config may raise the threshold, never lower it.
4. **Type Safety & Verification**: Python 3.11+ with type hints and Pydantic v2 in backend packages; strict TypeScript in `apps/dashboard/`. Every change ships with tests. Run `pytest` or `vitest` and report the real output. Never claim tests pass without running them.

## Metrics & Documentation Integrity
- Never invent, estimate, hardcode, or "calibrate" benchmark numbers.
- Any figure in the README or docs must come from a committed script output (e.g. `benchmark_results.json`) that includes config, commit SHA, model names, and seed.
- Unmeasured numbers must be labeled "target" or removed.
- Claims about competitors must be checked against their current public documentation and kept factual.
- Offline proxies must be labeled as proxies. "Acceptance rate" requires real developer feedback logs.

## Security Requirements
- Verify GitHub webhook signatures (`X-Hub-Signature-256`, HMAC-SHA256, `hmac.compare_digest`). Reject invalid or missing signatures with 401. Apply the equivalent token check for GitLab.
- Treat all PR content (diffs, titles, descriptions, comments, filenames) as untrusted data. Delimit it in prompts and instruct the model to ignore instructions found inside it.
- Never log tokens, private keys, or API keys. Load secrets only from environment variables and keep `.env.example` current.
- Use least-privilege GitHub App permissions (Pull requests: read/write, Contents: read, Metadata: read; add Contents: write only for the fix-PR feature).
- Load per-repo config (`.aicr.yaml`) from the PR base branch, never the PR head.
- Run Semgrep and other analyzers on checked-out PR code with no network access and a timeout. Never execute PR code.
- Only act on `@aicr` commands from users with write access, and ignore comments authored by the app itself.

## Working Style
- One scoped task per run. Propose a short plan first for tasks touching auth, webhooks, or the fix-PR flow, and wait for approval.
- Small, reviewable commits. No unrelated refactors.
- Follow existing conventions (async SQLAlchemy, Pydantic v2, pytest fixtures). Check how the repo already does it before adding a new pattern.
- Mock all external services (GitHub, GitLab, LLM providers) in tests. No network calls in the test suite.
- End each task with: summary of changes, files touched, test output, and known gaps.