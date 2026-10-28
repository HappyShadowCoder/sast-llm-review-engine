#!/usr/bin/env python3
"""
Webhook replay simulation script for testing the API Gateway locally without live VCS credentials.

Usage:
    python scripts/simulate_webhook.py --provider github --type pr_open --url http://localhost:8000
    python scripts/simulate_webhook.py --provider github --type feedback_thread --url http://localhost:8000
    python scripts/simulate_webhook.py --provider gitlab --type mr_open --url http://localhost:8000
    python scripts/simulate_webhook.py --provider gitlab --type feedback_note --url http://localhost:8000
"""

import argparse
import hashlib
import hmac
import json
import sys
import urllib.request
import urllib.error


def compute_github_sig(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def send_request(url: str, headers: dict, data: bytes):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"[{resp.status}] Response: {resp.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] HTTP Error: {e.read().decode('utf-8')}", file=sys.stderr)
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Simulate VCS webhook events.")
    parser.add_argument(
        "--provider",
        choices=["github", "gitlab"],
        default="github",
        help="VCS provider to simulate",
    )
    parser.add_argument(
        "--type",
        choices=["pr_open", "pr_sync", "feedback_thread", "feedback_reaction", "mr_open", "feedback_note"],
        default="pr_open",
        help="Type of event payload to simulate",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API gateway",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="Webhook secret (defaults to test secrets)",
    )
    parser.add_argument(
        "--comment-id",
        default="mock_comment_123",
        help="External comment ID for feedback simulation",
    )
    args = parser.parse_args()

    if args.provider == "github":
        secret = args.secret or "test_github_secret"
        endpoint = f"{args.url.rstrip('/')}/webhooks/github"

        if args.type == "pr_open":
            payload = {
                "action": "opened",
                "number": 42,
                "pull_request": {
                    "number": 42,
                    "title": "Fix SQL injection in authentication query",
                    "user": {"login": "senior_dev"},
                    "head": {"sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e", "ref": "fix/sql-injection"},
                    "base": {"sha": "a1b2c3d4e5f67890123456789abcdef012345678", "ref": "main"},
                    "created_at": "2026-10-20T10:00:00Z",
                },
                "repository": {
                    "id": 1296269,
                    "full_name": "acme-corp/payment-service",
                    "default_branch": "main",
                    "clone_url": "https://github.com/acme-corp/payment-service.git",
                },
                "installation": {"id": 1001},
            }
            event_name = "pull_request"

        elif args.type == "pr_sync":
            payload = {
                "action": "synchronize",
                "number": 42,
                "pull_request": {
                    "number": 42,
                    "title": "Fix SQL injection in authentication query",
                    "user": {"login": "senior_dev"},
                    "head": {"sha": "888809b5b57875f334f61aebed695e2e41938888", "ref": "fix/sql-injection"},
                    "base": {"sha": "a1b2c3d4e5f67890123456789abcdef012345678", "ref": "main"},
                },
                "repository": {
                    "id": 1296269,
                    "full_name": "acme-corp/payment-service",
                    "default_branch": "main",
                },
            }
            event_name = "pull_request"

        elif args.type == "feedback_thread":
            payload = {
                "action": "resolved",
                "thread": {"comments": [{"id": args.comment_id}]},
                "repository": {"id": 1296269},
            }
            event_name = "pull_request_review_thread"

        elif args.type == "feedback_reaction":
            payload = {
                "action": "created",
                "reaction": {"content": "+1"},
                "comment": {"id": args.comment_id},
            }
            event_name = "reaction"

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-GitHub-Event": event_name,
            "X-Hub-Signature-256": compute_github_sig(body, secret),
        }
        print(f"Sending GitHub {event_name} event to {endpoint}...")
        send_request(endpoint, headers, body)

    elif args.provider == "gitlab":
        secret = args.secret or "test_gitlab_secret"
        endpoint = f"{args.url.rstrip('/')}/webhooks/gitlab"

        if args.type == "mr_open":
            payload = {
                "object_kind": "merge_request",
                "user": {"username": "gl_dev"},
                "project": {
                    "id": 7890,
                    "name": "identity-service",
                    "path_with_namespace": "gitlab-org/identity-service",
                    "default_branch": "main",
                    "git_http_url": "https://gitlab.com/gitlab-org/identity-service.git",
                },
                "object_attributes": {
                    "id": 202,
                    "iid": 15,
                    "title": "Migrate auth tokens to Argon2id",
                    "action": "open",
                    "state": "opened",
                    "last_commit": {"id": "da1560886d4f094c3e6c9ef4034937d2b4e0e264"},
                    "source_branch": "auth/argon2",
                    "target_branch": "main",
                    "source_branch_sha": "da1560886d4f094c3e6c9ef4034937d2b4e0e264",
                    "target_branch_sha": "target_branch_sha_11",
                    "created_at": "2026-10-20 12:00:00 UTC",
                },
            }
            event_name = "Merge Request Hook"

        elif args.type == "feedback_note":
            payload = {
                "object_kind": "note",
                "object_attributes": {
                    "id": args.comment_id,
                    "noteable_type": "MergeRequest",
                    "resolved": True,
                    "note": "Resolved and applied suggestion",
                },
            }
            event_name = "Note Hook"

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Gitlab-Event": event_name,
            "X-Gitlab-Token": secret,
        }
        print(f"Sending GitLab {event_name} event to {endpoint}...")
        send_request(endpoint, headers, body)


if __name__ == "__main__":
    main()
