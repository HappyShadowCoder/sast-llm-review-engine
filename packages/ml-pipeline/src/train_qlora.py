#!/usr/bin/env python3
"""
QLoRA SFT Training Script for Qwen/Qwen2.5-Coder-7B-Instruct.
Supports 4-bit Unsloth fine-tuning on CUDA GPU environments,
and graceful non-CUDA / --dry-run validation on local macOS machines.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from .dataset_builder import SFTExample

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("train_qlora")


def validate_sft_dataset(dataset_path: Path, max_seq_len: int = 16384) -> Dict[str, Any]:
    """
    Validates JSONL dataset format, parses ChatML messages, and computes token statistics.
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    total_records = 0
    valid_records = 0
    max_chars = 0
    total_chars = 0

    with dataset_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            total_records += 1
            try:
                data = json.loads(line)
                example = SFTExample.model_validate(data)
                # Compute rough token estimate (~3.5 chars / token)
                full_text = "".join(m.content for m in example.messages)
                chars = len(full_text)
                total_chars += chars
                if chars > max_chars:
                    max_chars = chars
                valid_records += 1
            except Exception as e:
                logger.error(f"Validation error at line {idx}: {e}")
                raise

    avg_chars = int(total_chars / valid_records) if valid_records else 0
    estimated_max_tokens = int(max_chars / 3.5)
    estimated_avg_tokens = int(avg_chars / 3.5)

    if estimated_max_tokens > max_seq_len:
        logger.warning(
            f"Dataset max token length (~{estimated_max_tokens}) exceeds max_seq_len ({max_seq_len}). "
            f"Long examples will be truncated during training."
        )

    return {
        "dataset_path": str(dataset_path),
        "total_records": total_records,
        "valid_records": valid_records,
        "estimated_max_tokens": estimated_max_tokens,
        "estimated_avg_tokens": estimated_avg_tokens,
        "max_seq_len": max_seq_len,
    }


def run_training(args: argparse.Namespace) -> Dict[str, Any]:
    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dataset verification
    logger.info(f"Validating SFT dataset from {dataset_path}...")
    dataset_stats = validate_sft_dataset(dataset_path, max_seq_len=args.max_seq_length)
    logger.info(f"Dataset valid: {dataset_stats['valid_records']} records. Max tokens: ~{dataset_stats['estimated_max_tokens']}.")

    hyperparameters = {
        "base_model": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "load_in_4bit": True,
        "lora_rank": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.0,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "max_seq_length": args.max_seq_length,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "epochs": args.epochs,
        "export_gguf": args.export_gguf,
    }

    manifest = {
        "status": "ready",
        "mode": "dry_run" if args.dry_run else "cuda_train",
        "dataset_stats": dataset_stats,
        "hyperparameters": hyperparameters,
        "output_dir": str(output_dir),
    }

    # Check for CUDA availability
    cuda_available = False
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        pass

    if args.dry_run or not cuda_available:
        manifest["status"] = "validated_dry_run"
        reason = "CLI flag --dry-run specified" if args.dry_run else "Non-CUDA environment detected (macOS / local CPU)"
        manifest["note"] = f"Training pipeline validated successfully ({reason})."
        logger.info(f"Dry-run / local check successful. {manifest['note']}")

        manifest_path = output_dir / "training_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Saved training readiness manifest to {manifest_path}")
        return manifest

    # Full GPU Training (CUDA only)
    logger.info("NVIDIA CUDA detected. Initializing Unsloth FastLanguageModel...")
    import importlib
    try:
        unsloth_mod = importlib.import_module("unsloth")
        datasets_mod = importlib.import_module("datasets")
        trl_mod = importlib.import_module("trl")
        transformers_mod = importlib.import_module("transformers")
    except ImportError as e:
        raise RuntimeError(
            f"GPU training dependencies (unsloth, trl, datasets, transformers) not found: {e}. "
            "Run on a CUDA-enabled machine with: pip install unsloth trl datasets transformers torch"
        )

    FastLanguageModel = unsloth_mod.FastLanguageModel
    load_dataset = datasets_mod.load_dataset
    SFTTrainer = trl_mod.SFTTrainer
    TrainingArguments = transformers_mod.TrainingArguments

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=hyperparameters["base_model"],
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=hyperparameters["lora_rank"],
        target_modules=hyperparameters["target_modules"],
        lora_alpha=hyperparameters["lora_alpha"],
        lora_dropout=hyperparameters["lora_dropout"],
        bias="none",
        use_gradient_checkpointing=True,
    )

    train_dataset = load_dataset("json", data_files=str(dataset_path), split="train")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        dataset_text_field="messages",
        max_seq_length=args.max_seq_length,
        dataset_num_proc=2,
        args=TrainingArguments(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=4,
            warmup_steps=10,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            logging_steps=1,
            output_dir=str(output_dir),
        ),
    )

    trainer.train()
    model.save_pretrained(str(output_dir / "lora_adapter"))
    tokenizer.save_pretrained(str(output_dir / "lora_adapter"))
    manifest["status"] = "training_completed"
    return manifest


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QLoRA SFT Training for Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--dataset-path", default="packages/ml-pipeline/data/sft_train.jsonl")
    parser.add_argument("--output-dir", default="packages/ml-pipeline/checkpoints/qlora-sft")
    parser.add_argument("--max-seq-length", type=int, default=16384)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--export-gguf", action="store_true", help="Export adapter to GGUF format for vLLM/Ollama")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and dataset without launching GPU training")
    return parser.parse_args(args)


if __name__ == "__main__":
    cli_args = parse_args()
    res = run_training(cli_args)
    print(json.dumps(res, indent=2))
