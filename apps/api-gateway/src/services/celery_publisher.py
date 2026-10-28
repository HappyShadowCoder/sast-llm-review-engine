import importlib.util
import logging
from pathlib import Path
import socket
import sys
import threading
from typing import Any, Dict
from urllib.parse import urlparse
from celery import Celery
from ..config import settings

logger = logging.getLogger(__name__)

celery_client = Celery(
    "aicr_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Protect against blocking retries when Redis is down
celery_client.conf.update(
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=0,
    broker_transport_options={
        "max_retries": 0,
        "interval_start": 0,
        "interval_step": 0,
        "interval_max": 0,
    },
)


def is_redis_available(broker_url: str = settings.CELERY_BROKER_URL) -> bool:
    """Fast non-blocking check whether Redis is reachable."""
    try:
        parsed = urlparse(broker_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except Exception:
        return False


def _execute_review_in_process(task_payload: Dict[str, Any]) -> None:
    """Executes the review_pr workflow in-process without requiring Redis/Celery worker."""
    try:
        if "review_worker" not in sys.modules:
            root = Path(__file__).resolve().parents[4]  # repo root
            rw_dir = root / "packages" / "review-worker" / "src"
            init_file = rw_dir / "__init__.py"
            if init_file.exists():
                spec = importlib.util.spec_from_file_location(
                    "review_worker",
                    str(init_file),
                    submodule_search_locations=[str(rw_dir)],
                )
                mod = importlib.util.module_from_spec(spec)
                sys.modules["review_worker"] = mod
                spec.loader.exec_module(mod)

        from review_worker.celery_app import review_pr

        review_pr(
            review_run_id=task_payload["review_run_id"],
            repo_id=task_payload["repo_id"],
            pr_number=task_payload["pr_number"],
            head_sha=task_payload["head_sha"],
            base_sha=task_payload["base_sha"],
            clone_url=task_payload.get("clone_url", ""),
            meta=task_payload.get("meta", {}),
        )
        logger.info(
            f"Completed in-process review for run {task_payload['review_run_id']}"
        )
    except Exception as e:
        logger.warning(
            f"In-process review execution encountered non-fatal error: {e}"
        )


class CeleryPublisher:
    @staticmethod
    def enqueue_review_job(
        review_run_id: str,
        repo_id: str,
        pr_number: int,
        head_sha: str,
        base_sha: str,
        clone_url: str = "",
        extra_meta: Dict[str, Any] = None,
    ) -> str:
        """
        Enqueues an asynchronous review job.
        If Redis is running, dispatches to Celery.
        If Redis is not running, executes immediately in-process on a background thread.
        Returns task_id string without blocking.
        """
        task_payload = {
            "review_run_id": review_run_id,
            "repo_id": repo_id,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "clone_url": clone_url,
            "meta": extra_meta or {},
        }

        # Try Celery if Redis is reachable
        if is_redis_available():
            try:
                async_result = celery_client.send_task(
                    "review_pr",
                    kwargs=task_payload,
                )
                logger.info(
                    f"Dispatched Celery task review_pr with ID: {async_result.id} for ReviewRun: {review_run_id}"
                )
                return str(async_result.id)
            except Exception as e:
                logger.warning(
                    f"Celery dispatch failed ({e}), falling back to in-process execution"
                )

        # Fallback to immediate in-process execution on daemon thread
        thread = threading.Thread(
            target=_execute_review_in_process,
            args=(task_payload,),
            daemon=True,
        )
        thread.start()
        task_id = f"in-process-{review_run_id}"
        logger.info(
            f"Running review in-process (task_id: {task_id}) for ReviewRun: {review_run_id}"
        )
        return task_id
