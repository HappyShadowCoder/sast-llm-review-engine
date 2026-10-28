import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["system", "user", "assistant"]
    content: str


class SFTExample(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    messages: List[ChatMessage] = Field(..., min_length=2)


class DPOTriplet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt: str = Field(..., description="User prompt with diff, AST context, and SAST findings")
    chosen: str = Field(..., description="Accepted high-confidence review response JSON")
    rejected: str = Field(..., description="Dismissed or generic/noisy review response JSON")
    metadata: Optional[Dict[str, Any]] = None


def export_sft_dataset(records: List[SFTExample], output_path: Union[str, Path]) -> int:
    """
    Exports SFT training records into Hugging Face ChatML JSONL format.
    Returns the number of records written.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out_file.open("w", encoding="utf-8") as f:
        for record in records:
            line = json.dumps(record.model_dump(), ensure_ascii=False)
            f.write(line + "\n")
            count += 1

    logger.info(f"Exported {count} SFT records to {out_file}")
    return count


def export_dpo_dataset(triplets: List[DPOTriplet], output_path: Union[str, Path]) -> int:
    """
    Exports DPO preference triplets into Hugging Face TRL JSONL format.
    Returns the number of triplets written.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out_file.open("w", encoding="utf-8") as f:
        for triplet in triplets:
            line = json.dumps(triplet.model_dump(), ensure_ascii=False)
            f.write(line + "\n")
            count += 1

    logger.info(f"Exported {count} DPO triplets to {out_file}")
    return count


def generate_sample_datasets(data_dir: Union[str, Path]) -> Tuple[Path, Path]:
    """
    Generates realistic sample SFT and DPO training JSONL datasets for local validation and dry-run training.
    """
    dir_path = Path(data_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    sft_path = dir_path / "sft_train.jsonl"
    dpo_path = dir_path / "dpo_train.jsonl"

    system_prompt = (
        "You are an enterprise-grade Principal Software Engineer and Application Security Architect. "
        "Review the PR with AST call-graph context and Semgrep SAST findings. "
        "Enforce strict ReviewResponse JSON output with committable suggested_code blocks. "
        "Drop low-confidence noise (< 0.80) and style nitpicks."
    )

    # 1. Sample SFT Examples
    sft_records = [
        SFTExample(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(
                    role="user",
                    content=(
                        "# PULL REQUEST: Fix user login query\n"
                        "## DIFF:\n"
                        "- cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
                        "+ cursor.execute(f'SELECT * FROM users WHERE email = {email}')\n"
                        "## SAST FINDINGS:\n"
                        "- [security.sqli] src/auth.py:15 (CRITICAL): Potential SQL Injection in execute call.\n"
                    ),
                ),
                ChatMessage(
                    role="assistant",
                    content=json.dumps(
                        {
                            "summary": "Critical SQL injection vulnerability detected in authentication query.",
                            "findings": [
                                {
                                    "file_path": "src/auth.py",
                                    "start_line": 15,
                                    "end_line": 15,
                                    "category": "security",
                                    "severity": "critical",
                                    "confidence": 0.98,
                                    "explanation": "Dynamic formatted string interpolation allows SQL injection.",
                                    "suggested_code": "cursor.execute('SELECT * FROM users WHERE email = %s', (email,))",
                                }
                            ],
                        },
                        indent=2,
                    ),
                ),
            ]
        ),
        SFTExample(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(
                    role="user",
                    content=(
                        "# PULL REQUEST: Update token verification signature\n"
                        "## DIFF:\n"
                        "- def verify_token(token: str) -> bool:\n"
                        "+ def verify_token(token: str, algorithm: str = 'ES256') -> bool:\n"
                        "## UPSTREAM CALL SITES:\n"
                        "- Caller: `login_handler` in `src/routes.py:42` calls `verify_token(token)`\n"
                    ),
                ),
                ChatMessage(
                    role="assistant",
                    content=json.dumps(
                        {
                            "summary": "Architectural review: Signature change is backward compatible via default argument.",
                            "findings": [],
                        },
                        indent=2,
                    ),
                ),
            ]
        ),
    ]

    # 2. Sample DPO Triplet Examples
    dpo_records = [
        DPOTriplet(
            prompt=(
                "# PULL REQUEST: Add user query API\n"
                "## DIFF:\n"
                "- res = db.query(raw_sql)\n"
                "+ res = db.execute(f'SELECT * FROM users WHERE id = {uid}')\n"
            ),
            chosen=json.dumps(
                {
                    "summary": "Critical security defect: SQL injection detected.",
                    "findings": [
                        {
                            "file_path": "src/api.py",
                            "start_line": 20,
                            "end_line": 20,
                            "category": "security",
                            "severity": "critical",
                            "confidence": 0.96,
                            "explanation": "Untrusted parameter interpolated into SQL query.",
                            "suggested_code": "res = db.execute('SELECT * FROM users WHERE id = :uid', {'uid': uid})",
                        }
                    ],
                }
            ),
            rejected=json.dumps(
                {
                    "summary": "Code style review.",
                    "findings": [
                        {
                            "file_path": "src/api.py",
                            "start_line": 20,
                            "end_line": 20,
                            "category": "style_nitpick",
                            "severity": "low",
                            "confidence": 0.50,
                            "explanation": "Variable `uid` could be named `user_identifier` for clarity.",
                            "suggested_code": "res = db.execute(f'SELECT * FROM users WHERE id = {user_identifier}')",
                        }
                    ],
                }
            ),
            metadata={"repo_id": "org/core", "pr_number": 42},
        )
    ]

    export_sft_dataset(sft_records, sft_path)
    export_dpo_dataset(dpo_records, dpo_path)

    return sft_path, dpo_path
