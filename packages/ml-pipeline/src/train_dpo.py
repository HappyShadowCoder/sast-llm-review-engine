#!/usr/bin/env python3
"""
Direct Preference Optimization (DPO) Alignment Script.
Aligns SFT checkpoint using developer feedback triplets (prompt, chosen, rejected)
via Hugging Face TRL DPOTrainer to suppress dismissed comment patterns.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

from .dataset_builder import DPOTriplet

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("train_dpo")


def validate_dpo_dataset(dataset_path: Path, max_length: int = 16384, max_prompt_length: int = 12288) -> Dict[str, Any]:
    """
    Validates (prompt, chosen, rejected) triplets and verifies length constraints.
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"DPO dataset not found: {dataset_path}")

    total_triplets = 0
    valid_triplets = 0
    max_prompt_chars = 0
    max_response_chars = 0

    with dataset_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            total_triplets += 1
            try:
                data = json.loads(line)
                triplet = DPOTriplet.model_validate(data)

                # Ensure chosen and rejected are distinct
                if triplet.chosen.strip() == triplet.rejected.strip():
                    raise ValueError(f"Line {idx}: chosen and rejected outputs cannot be identical.")

                prompt_len = len(triplet.prompt)
                resp_len = max(len(triplet.chosen), len(triplet.rejected))

                if prompt_len > max_prompt_chars:
                    max_prompt_chars = prompt_len
                if resp_len > max_response_chars:
                    max_response_chars = resp_len

                valid_triplets += 1
            except Exception as e:
                logger.error(f"DPO validation error at line {idx}: {e}")
                raise

    est_prompt_tokens = int(max_prompt_chars / 3.5)
    est_total_tokens = int((max_prompt_chars + max_response_chars) / 3.5)

    if est_prompt_tokens > max_prompt_length:
        logger.warning(f"Max prompt token length (~{est_prompt_tokens}) exceeds max_prompt_length ({max_prompt_length}).")
    if est_total_tokens > max_length:
        logger.warning(f"Max total token length (~{est_total_tokens}) exceeds max_length ({max_length}).")

    return {
        "dataset_path": str(dataset_path),
        "total_triplets": total_triplets,
        "valid_triplets": valid_triplets,
        "estimated_max_prompt_tokens": est_prompt_tokens,
        "estimated_max_total_tokens": est_total_tokens,
        "max_length": max_length,
        "max_prompt_length": max_prompt_length,
    }


def run_dpo_training(args: argparse.Namespace) -> Dict[str, Any]:
    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Validating DPO dataset from {dataset_path}...")
    dataset_stats = validate_dpo_dataset(
        dataset_path,
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
    )
    logger.info(f"DPO dataset valid: {dataset_stats['valid_triplets']} triplets verified.")

    hyperparameters = {
        "sft_model_path": args.sft_model_path,
        "beta": args.beta,
        "max_length": args.max_length,
        "max_prompt_length": args.max_prompt_length,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "epochs": args.epochs,
    }

    manifest = {
        "status": "ready",
        "mode": "dry_run" if args.dry_run else "cuda_train",
        "dataset_stats": dataset_stats,
        "hyperparameters": hyperparameters,
        "output_dir": str(output_dir),
    }

    cuda_available = False
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        pass

    if args.dry_run or not cuda_available:
        manifest["status"] = "validated_dry_run"
        reason = "CLI flag --dry-run specified" if args.dry_run else "Non-CUDA environment detected (macOS / local CPU)"
        manifest["note"] = f"DPO pipeline validated successfully ({reason})."
        logger.info(f"DPO check successful. {manifest['note']}")

        manifest_path = output_dir / "dpo_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Saved DPO alignment manifest to {manifest_path}")
        return manifest

    # Full GPU Training (CUDA only)
    logger.info("Initializing TRL DPOTrainer on CUDA device...")
    import importlib
    try:
        datasets_mod = importlib.import_module("datasets")
        trl_mod = importlib.import_module("trl")
        transformers_mod = importlib.import_module("transformers")
    except ImportError as e:
        raise RuntimeError(
            f"GPU training dependencies (trl, datasets, transformers) not found: {e}. "
            "Run on a CUDA-enabled machine with: pip install trl datasets transformers torch"
        )

    load_dataset = datasets_mod.load_dataset
    DPOConfig = trl_mod.DPOConfig
    DPOTrainer = trl_mod.DPOTrainer
    AutoModelForCausalLM = transformers_mod.AutoModelForCausalLM
    AutoTokenizer = transformers_mod.AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(args.sft_model_path, load_in_4bit=True, device_map="auto")
    ref_model = AutoModelForCausalLM.from_pretrained(args.sft_model_path, load_in_4bit=True, device_map="auto")
    tokenizer = AutoTokenizer.from_pretrained(args.sft_model_path)

    train_dataset = load_dataset("json", data_files=str(dataset_path), split="train")

    dpo_config = DPOConfig(
        beta=args.beta,
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        num_train_epochs=args.epochs,
        output_dir=str(output_dir),
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        args=dpo_config,
        train_dataset=train_dataset,
        tokenizer=tokenizer,
    )

    trainer.train()
    trainer.save_model(str(output_dir / "dpo_aligned_model"))
    manifest["status"] = "dpo_alignment_completed"
    return manifest


def parse_args(args=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TRL DPO Alignment for AI Code Reviewer")
    parser.add_argument("--dataset-path", default="packages/ml-pipeline/data/dpo_train.jsonl")
    parser.add_argument("--output-dir", default="packages/ml-pipeline/checkpoints/dpo-aligned")
    parser.add_argument("--sft-model-path", default="packages/ml-pipeline/checkpoints/qlora-sft")
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--max-prompt-length", type=int, default=12288)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=5e-6)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="Validate DPO configuration and triplet dataset")
    return parser.parse_args(args)


if __name__ == "__main__":
    cli_args = parse_args()
    res = run_dpo_training(cli_args)
    print(json.dumps(res, indent=2))
