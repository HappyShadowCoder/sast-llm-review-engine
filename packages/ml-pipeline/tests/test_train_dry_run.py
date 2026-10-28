from pathlib import Path
from src.train_qlora import parse_args as parse_qlora_args, run_training, validate_sft_dataset
from src.train_dpo import parse_args as parse_dpo_args, run_dpo_training, validate_dpo_dataset


def test_qlora_dry_run_pipeline(sample_data_dir, tmp_path: Path):
    sft_file = sample_data_dir["sft_file"]

    # 1. Dataset stats validation
    stats = validate_sft_dataset(sft_file, max_seq_len=16384)
    assert stats["valid_records"] >= 2
    assert stats["estimated_max_tokens"] <= 16384

    # 2. Dry-run training execution
    out_dir = tmp_path / "qlora_test_out"
    args = parse_qlora_args([
        "--dataset-path", str(sft_file),
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    manifest = run_training(args)

    assert manifest["status"] == "validated_dry_run"
    assert manifest["hyperparameters"]["base_model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert manifest["hyperparameters"]["lora_rank"] == 16
    assert (out_dir / "training_manifest.json").exists()


def test_dpo_dry_run_pipeline(sample_data_dir, tmp_path: Path):
    dpo_file = sample_data_dir["dpo_file"]

    # 1. DPO stats validation
    stats = validate_dpo_dataset(dpo_file, max_length=16384, max_prompt_length=12288)
    assert stats["valid_triplets"] >= 1

    # 2. Dry-run DPO execution
    out_dir = tmp_path / "dpo_test_out"
    args = parse_dpo_args([
        "--dataset-path", str(dpo_file),
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    manifest = run_dpo_training(args)

    assert manifest["status"] == "validated_dry_run"
    assert manifest["hyperparameters"]["beta"] == 0.1
    assert (out_dir / "dpo_manifest.json").exists()
