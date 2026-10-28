#!/bin/bash
set -e

echo "=== Running API Gateway Tests ==="
.venv/bin/pytest apps/api-gateway/tests/test_analytics.py apps/api-gateway/tests/test_feedback.py apps/api-gateway/tests/test_migrations.py apps/api-gateway/tests/test_normalization.py apps/api-gateway/tests/test_signatures.py apps/api-gateway/tests/test_webhooks.py "$@"
.venv/bin/pytest apps/api-gateway/tests/test_repo_analyzer.py apps/api-gateway/tests/test_live_scanner.py "$@"

echo ""
echo "=== Running Context Engine Tests ==="
.venv/bin/pytest packages/context-engine/tests "$@"

echo ""
echo "=== Running Review Worker Tests ==="
.venv/bin/pytest packages/review-worker/tests "$@"

echo ""
echo "=== Running ML Pipeline Tests ==="
.venv/bin/pytest packages/ml-pipeline/tests "$@"

echo ""
echo "All 4 test suites passed successfully!"
