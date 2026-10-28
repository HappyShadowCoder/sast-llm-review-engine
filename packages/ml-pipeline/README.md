# ML Pipeline (`packages/ml-pipeline`)

Responsible for:
- Dataset generation from historical PR diffs, AST bundles, and review comments.
- Preference pair generation from accepted vs. dismissed review feedback.
- QLoRA SFT fine-tuning of Qwen2.5-Coder-7B-Instruct with Unsloth.
- DPO preference alignment with TRL DPOTrainer.
