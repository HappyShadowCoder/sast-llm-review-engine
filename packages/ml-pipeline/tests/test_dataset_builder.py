import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from src.dataset_builder import (
    ChatMessage,
    SFTExample,
    DPOTriplet,
    export_sft_dataset,
    export_dpo_dataset,
)


def test_sft_example_validation():
    # Valid SFT Example
    example = SFTExample(
        messages=[
            ChatMessage(role="system", content="System instruction"),
            ChatMessage(role="user", content="User prompt"),
            ChatMessage(role="assistant", content="Assistant output"),
        ]
    )
    assert len(example.messages) == 3
    assert example.messages[0].role == "system"

    # Invalid: fewer than 2 messages
    with pytest.raises(ValidationError):
        SFTExample(messages=[ChatMessage(role="user", content="Only one message")])


def test_dpo_triplet_validation():
    triplet = DPOTriplet(
        prompt="PR diff prompt",
        chosen="Accepted comment",
        rejected="Dismissed comment",
        metadata={"repo_id": "test"},
    )
    assert triplet.prompt == "PR diff prompt"
    assert triplet.chosen == "Accepted comment"
    assert triplet.rejected == "Dismissed comment"


def test_export_sft_dataset(tmp_path: Path):
    sft_file = tmp_path / "test_sft.jsonl"
    records = [
        SFTExample(
            messages=[
                ChatMessage(role="system", content="Sys"),
                ChatMessage(role="user", content="User 1"),
                ChatMessage(role="assistant", content="Assistant 1"),
            ]
        ),
        SFTExample(
            messages=[
                ChatMessage(role="system", content="Sys"),
                ChatMessage(role="user", content="User 2"),
                ChatMessage(role="assistant", content="Assistant 2"),
            ]
        ),
    ]

    count = export_sft_dataset(records, sft_file)
    assert count == 2
    assert sft_file.exists()

    with sft_file.open("r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 2
    assert lines[0]["messages"][1]["content"] == "User 1"


def test_export_dpo_dataset(tmp_path: Path):
    dpo_file = tmp_path / "test_dpo.jsonl"
    triplets = [
        DPOTriplet(
            prompt="Prompt 1",
            chosen="Accepted",
            rejected="Dismissed",
        )
    ]

    count = export_dpo_dataset(triplets, dpo_file)
    assert count == 1
    assert dpo_file.exists()

    with dpo_file.open("r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 1
    assert lines[0]["chosen"] == "Accepted"
