# AGENTS.md — AI-Powered Code Review Assistant Architecture & Rules

## Project Overview
We are building an enterprise-grade, multi-VCS AI Code Review Assistant and Engineering Quality Dashboard. It integrates with GitHub Pull Requests and GitLab Merge Requests to deliver cross-file architectural reviews and deterministic security flags, backed by a QLoRA/DPO fine-tuning pipeline and a Next.js analytics dashboard.

## Monorepo Directory Structure
- `apps/api-gateway/`: FastAPI service for GitHub/GitLab webhooks, REST APIs for the dashboard, and authentication.
- `packages/context-engine/`: Tree-sitter AST parser, 2-hop call-graph builder, and Qdrant vector/symbol indexer.
- `packages/review-worker/`: Celery/Redis async worker running Semgrep SAST, assembling cross-file context, calling the AI model, filtering low-confidence noise, and posting inline VCS review comments.
- `packages/ml-pipeline/`: Dataset curation scripts, Unsloth QLoRA fine-tuning pipeline (`Qwen/Qwen2.5-Coder-7B-Instruct`), and TRL DPO alignment trainer using webhook feedback events.
- `apps/dashboard/`: Next.js (App Router, TypeScript, Tailwind CSS, Recharts) engineering quality dashboard.
- `infra/`: `docker-compose.yml` for PostgreSQL, Redis, and Qdrant, plus environment templates.

## Strict Engineering Standards for Agents
1. **No Naive Diff Wrappers**: Never send raw `git diff` strings to an LLM without first enriching them with AST symbol definitions, imported type signatures, and caller/callee context from `packages/context-engine/`.
2. **Strict Output Schema**: All AI review generations must validate against a Pydantic schema (`ReviewFinding`) containing `file_path`, `start_line`, `end_line`, `category` (`architecture` | `security` | `performance` | `concurrency` | `bug`), `severity` (`critical` | `high` | `medium`), `confidence` (`0.0` to `1.0`), `explanation`, and `suggested_code` (exact replacement block).
3. **Anti-Noise Gate**: Automatically drop any AI finding with `confidence < 0.80` or `category == "style_nitpick"`.
4. **Type Safety & Verification**: Use Python 3.11+ with strict Pydantic v2 models and type hints in backend packages, and strict TypeScript in `apps/dashboard/`. After implementing any module, write and run `pytest` or `vitest` unit tests before marking the task complete.
