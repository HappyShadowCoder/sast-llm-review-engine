from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union
from ..schemas.webhook import NormalizedFeedbackEvent, NormalizedPREvent


def parse_datetime(dt_str: Optional[str]) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        # ISO formats or Gitlab formatted string "YYYY-MM-DD HH:MM:SS UTC"
        clean_str = dt_str.replace(" UTC", "+00:00").replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return datetime.now(timezone.utc)


class PayloadNormalizer:
    @staticmethod
    def normalize_github_pr(payload: Dict[str, Any], event_name: str = "pull_request") -> Optional[NormalizedPREvent]:
        action = payload.get("action", "")
        # Only process relevant PR actions
        if action not in {"opened", "synchronize", "reopened"}:
            return None

        pr_data = payload.get("pull_request")
        repo_data = payload.get("repository")
        if not pr_data or not repo_data:
            return None

        installation = payload.get("installation") or {}
        installation_id = str(installation.get("id")) if installation.get("id") else None

        head = pr_data.get("head") or {}
        base = pr_data.get("base") or {}
        user = pr_data.get("user") or {}

        opened_at = parse_datetime(pr_data.get("created_at"))
        merged_at = parse_datetime(pr_data.get("merged_at")) if pr_data.get("merged_at") else None

        return NormalizedPREvent(
            vcs_provider="github",
            event_type=f"pull_request.{action}",
            action=action,
            external_repo_id=str(repo_data.get("id", "")),
            repo_name=repo_data.get("full_name") or repo_data.get("name", "unknown"),
            repo_default_branch=repo_data.get("default_branch", "main"),
            repo_clone_url=repo_data.get("clone_url"),
            installation_id=installation_id,
            pr_number=int(pr_data.get("number") or payload.get("number", 0)),
            title=pr_data.get("title", ""),
            author=user.get("login", "unknown"),
            head_sha=head.get("sha", ""),
            base_sha=base.get("sha", ""),
            head_branch=head.get("ref", ""),
            base_branch=base.get("ref", ""),
            opened_at=opened_at,
            merged_at=merged_at,
            raw_payload=payload,
        )

    @staticmethod
    def normalize_github_feedback(
        payload: Dict[str, Any],
        event_name: str,
    ) -> Optional[NormalizedFeedbackEvent]:
        """
        Extracts comment feedback from:
        - pull_request_review_thread (action=resolved -> accepted, unresolved -> dismissed)
        - reaction (content: +1, heart, rocket -> accepted; -1 -> dismissed)
        - pull_request_review_comment (applied suggestion or reaction)
        """
        action = payload.get("action", "")

        # 1. PR review thread resolution
        if event_name == "pull_request_review_thread":
            thread = payload.get("thread", {})
            comments = thread.get("comments", [])
            ext_id = str(comments[0].get("id")) if comments else None
            repo_data = payload.get("repository", {})

            if action == "resolved" and ext_id:
                return NormalizedFeedbackEvent(
                    vcs_provider="github",
                    event_type="pull_request_review_thread",
                    action=action,
                    external_comment_id=ext_id,
                    external_repo_id=str(repo_data.get("id", "")),
                    pr_number=payload.get("pull_request", {}).get("number"),
                    status="accepted",
                    reason="PR review thread was marked as resolved by engineer",
                    raw_payload=payload,
                )
            elif action == "unresolved" and ext_id:
                return NormalizedFeedbackEvent(
                    vcs_provider="github",
                    event_type="pull_request_review_thread",
                    action=action,
                    external_comment_id=ext_id,
                    external_repo_id=str(repo_data.get("id", "")),
                    pr_number=payload.get("pull_request", {}).get("number"),
                    status="dismissed",
                    reason="PR review thread was reopened or dismissed",
                    raw_payload=payload,
                )

        # 2. Reactions on review comments
        if event_name in {"reaction", "pull_request_review_comment"}:
            reaction_data = payload.get("reaction") or {}
            comment_data = payload.get("comment") or {}
            content = reaction_data.get("content", "")
            ext_id = str(comment_data.get("id")) if comment_data.get("id") else None

            if ext_id and content:
                if content in {"+1", "thumbs_up", "heart", "rocket"}:
                    return NormalizedFeedbackEvent(
                        vcs_provider="github",
                        event_type=event_name,
                        action=action,
                        external_comment_id=ext_id,
                        status="accepted",
                        reason=f"Positive developer reaction '{content}' received",
                        raw_payload=payload,
                    )
                elif content in {"-1", "thumbs_down", "confused"}:
                    return NormalizedFeedbackEvent(
                        vcs_provider="github",
                        event_type=event_name,
                        action=action,
                        external_comment_id=ext_id,
                        status="dismissed",
                        reason=f"Negative developer reaction '{content}' received",
                        raw_payload=payload,
                    )

            # Check if comment body explicitly notes suggestion applied or dismissed
            body = comment_data.get("body", "")
            if ext_id and ("Apply suggestion" in body or "Applied suggestion" in body):
                return NormalizedFeedbackEvent(
                    vcs_provider="github",
                    event_type="pull_request_review_comment",
                    action=action,
                    external_comment_id=ext_id,
                    status="accepted",
                    reason="Suggestion commit applied by developer",
                    raw_payload=payload,
                )

        return None

    @staticmethod
    def normalize_gitlab_mr(payload: Dict[str, Any]) -> Optional[NormalizedPREvent]:
        object_kind = payload.get("object_kind")
        if object_kind != "merge_request":
            return None

        attrs = payload.get("object_attributes", {})
        action = attrs.get("action", "")
        # GitLab actions: open, update, reopen, close, merge
        if action not in {"open", "update", "reopen"}:
            return None

        project = payload.get("project", {})
        user = payload.get("user", {})
        last_commit = attrs.get("last_commit", {})

        # Normalize action terminology to match PRs ('open' -> 'opened', 'update' -> 'synchronize')
        normalized_action = "opened" if action == "open" else ("synchronize" if action == "update" else action)

        opened_at = parse_datetime(attrs.get("created_at"))

        return NormalizedPREvent(
            vcs_provider="gitlab",
            event_type=f"merge_request.{normalized_action}",
            action=normalized_action,
            external_repo_id=str(project.get("id", "")),
            repo_name=project.get("path_with_namespace") or project.get("name", "unknown"),
            repo_default_branch=project.get("default_branch", "main"),
            repo_clone_url=project.get("git_http_url") or project.get("web_url"),
            installation_id=None,
            pr_number=int(attrs.get("iid") or attrs.get("id", 0)),
            title=attrs.get("title", ""),
            author=user.get("username", "unknown"),
            head_sha=last_commit.get("id") or attrs.get("source_branch_sha", ""),
            base_sha=attrs.get("target_branch_sha") or attrs.get("base_sha", "main"),
            head_branch=attrs.get("source_branch", ""),
            base_branch=attrs.get("target_branch", "main"),
            opened_at=opened_at,
            merged_at=None,
            raw_payload=payload,
        )

    @staticmethod
    def normalize_gitlab_feedback(payload: Dict[str, Any]) -> Optional[NormalizedFeedbackEvent]:
        """
        Extracts feedback from GitLab Note Hook or Merge Request discussions.
        """
        object_kind = payload.get("object_kind")
        if object_kind == "note":
            attrs = payload.get("object_attributes", {})
            noteable_type = attrs.get("noteable_type")
            ext_id = str(attrs.get("id", ""))
            discussion_id = attrs.get("discussion_id")

            # Check if discussion was resolved
            if attrs.get("resolved") is True or "resolved" in attrs.get("note", "").lower():
                return NormalizedFeedbackEvent(
                    vcs_provider="gitlab",
                    event_type="note",
                    action="resolved",
                    external_comment_id=ext_id or discussion_id,
                    status="accepted",
                    reason="GitLab discussion resolved by developer",
                    raw_payload=payload,
                )
            elif "dismissed" in attrs.get("note", "").lower() or "rejected" in attrs.get("note", "").lower():
                return NormalizedFeedbackEvent(
                    vcs_provider="gitlab",
                    event_type="note",
                    action="dismissed",
                    external_comment_id=ext_id or discussion_id,
                    status="dismissed",
                    reason="GitLab discussion marked as dismissed by developer",
                    raw_payload=payload,
                )

        return None
