# Review Worker (`packages/review-worker`)

Responsible for:
- Celery worker handling review generation tasks.
- Semgrep SAST deterministic security scans.
- Structured AI review with prompt engineering and Pydantic validation.
- Confidence gating (`>= 0.80`) and anti-noise filtering.
- Publishing inline suggestions back to GitHub PRs and GitLab MRs.
