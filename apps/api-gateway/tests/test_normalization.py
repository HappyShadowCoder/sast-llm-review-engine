from src.services.payload_normalizer import PayloadNormalizer


def test_normalize_github_pr_opened():
    payload = {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "number": 42,
            "title": "Add async processing queue",
            "user": {"login": "dev_expert"},
            "head": {"sha": "headsha12345", "ref": "feature/async-queue"},
            "base": {"sha": "basesha67890", "ref": "main"},
            "created_at": "2026-10-20T10:00:00Z",
            "merged_at": None,
        },
        "repository": {
            "id": 987654,
            "full_name": "acme/backend-service",
            "default_branch": "main",
            "clone_url": "https://github.com/acme/backend-service.git",
        },
        "installation": {"id": 112233},
    }

    event = PayloadNormalizer.normalize_github_pr(payload, "pull_request")
    assert event is not None
    assert event.vcs_provider == "github"
    assert event.event_type == "pull_request.opened"
    assert event.action == "opened"
    assert event.external_repo_id == "987654"
    assert event.repo_name == "acme/backend-service"
    assert event.pr_number == 42
    assert event.title == "Add async processing queue"
    assert event.author == "dev_expert"
    assert event.head_sha == "headsha12345"
    assert event.base_sha == "basesha67890"
    assert event.head_branch == "feature/async-queue"
    assert event.base_branch == "main"
    assert event.installation_id == "112233"


def test_normalize_github_pr_synchronize():
    payload = {
        "action": "synchronize",
        "number": 42,
        "pull_request": {
            "number": 42,
            "title": "Add async processing queue",
            "user": {"login": "dev_expert"},
            "head": {"sha": "newheadsha999", "ref": "feature/async-queue"},
            "base": {"sha": "basesha67890", "ref": "main"},
            "created_at": "2026-10-20T10:00:00Z",
        },
        "repository": {
            "id": 987654,
            "full_name": "acme/backend-service",
            "default_branch": "main",
        },
    }

    event = PayloadNormalizer.normalize_github_pr(payload, "pull_request")
    assert event is not None
    assert event.action == "synchronize"
    assert event.head_sha == "newheadsha999"


def test_normalize_github_pr_ignored_action():
    payload = {
        "action": "labeled",
        "number": 42,
        "pull_request": {"number": 42},
        "repository": {"id": 987654},
    }
    event = PayloadNormalizer.normalize_github_pr(payload, "pull_request")
    assert event is None


def test_normalize_gitlab_mr_open():
    payload = {
        "object_kind": "merge_request",
        "user": {"username": "gitlab_engineer"},
        "project": {
            "id": 555,
            "name": "data-pipeline",
            "path_with_namespace": "gitlab-org/data-pipeline",
            "default_branch": "main",
            "git_http_url": "https://gitlab.com/gitlab-org/data-pipeline.git",
        },
        "object_attributes": {
            "id": 101,
            "iid": 12,
            "title": "Refactor SQL queries",
            "action": "open",
            "state": "opened",
            "last_commit": {"id": "gitlab_commit_sha_123"},
            "source_branch": "refactor/sql",
            "target_branch": "main",
            "source_branch_sha": "gitlab_commit_sha_123",
            "target_branch_sha": "target_main_sha",
            "created_at": "2026-10-20 12:00:00 UTC",
        },
    }

    event = PayloadNormalizer.normalize_gitlab_mr(payload)
    assert event is not None
    assert event.vcs_provider == "gitlab"
    assert event.action == "opened"
    assert event.external_repo_id == "555"
    assert event.repo_name == "gitlab-org/data-pipeline"
    assert event.pr_number == 12
    assert event.title == "Refactor SQL queries"
    assert event.author == "gitlab_engineer"
    assert event.head_sha == "gitlab_commit_sha_123"
    assert event.base_sha == "target_main_sha"
    assert event.head_branch == "refactor/sql"
    assert event.base_branch == "main"


def test_normalize_gitlab_mr_update():
    payload = {
        "object_kind": "merge_request",
        "user": {"username": "gitlab_engineer"},
        "project": {"id": 555, "path_with_namespace": "gitlab-org/data-pipeline"},
        "object_attributes": {
            "iid": 12,
            "title": "Refactor SQL queries",
            "action": "update",
            "last_commit": {"id": "updated_sha_456"},
            "source_branch": "refactor/sql",
            "target_branch": "main",
        },
    }

    event = PayloadNormalizer.normalize_gitlab_mr(payload)
    assert event is not None
    assert event.action == "synchronize"
    assert event.head_sha == "updated_sha_456"


def test_normalize_github_feedback_thread_resolved():
    payload = {
        "action": "resolved",
        "thread": {
            "comments": [
                {"id": 888123, "body": "Potential SQL injection vulnerability"}
            ]
        },
        "repository": {"id": 987654},
        "pull_request": {"number": 42},
    }
    feedback = PayloadNormalizer.normalize_github_feedback(payload, "pull_request_review_thread")
    assert feedback is not None
    assert feedback.status == "accepted"
    assert feedback.external_comment_id == "888123"


def test_normalize_github_feedback_thread_unresolved():
    payload = {
        "action": "unresolved",
        "thread": {
            "comments": [{"id": 888123}]
        },
        "repository": {"id": 987654},
    }
    feedback = PayloadNormalizer.normalize_github_feedback(payload, "pull_request_review_thread")
    assert feedback is not None
    assert feedback.status == "dismissed"
    assert feedback.external_comment_id == "888123"


def test_normalize_github_feedback_reaction_positive():
    payload = {
        "action": "created",
        "reaction": {"content": "+1"},
        "comment": {"id": 999321},
    }
    feedback = PayloadNormalizer.normalize_github_feedback(payload, "reaction")
    assert feedback is not None
    assert feedback.status == "accepted"
    assert feedback.external_comment_id == "999321"


def test_normalize_github_feedback_reaction_negative():
    payload = {
        "action": "created",
        "reaction": {"content": "-1"},
        "comment": {"id": 999321},
    }
    feedback = PayloadNormalizer.normalize_github_feedback(payload, "reaction")
    assert feedback is not None
    assert feedback.status == "dismissed"
    assert feedback.external_comment_id == "999321"


def test_normalize_gitlab_feedback_note_resolved():
    payload = {
        "object_kind": "note",
        "object_attributes": {
            "id": 777654,
            "noteable_type": "MergeRequest",
            "resolved": True,
            "note": "Resolved by applying suggestion",
        },
    }
    feedback = PayloadNormalizer.normalize_gitlab_feedback(payload)
    assert feedback is not None
    assert feedback.status == "accepted"
    assert feedback.external_comment_id == "777654"
