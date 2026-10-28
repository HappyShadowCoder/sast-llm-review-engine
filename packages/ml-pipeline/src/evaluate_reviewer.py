import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


def compute_line_iou(pred_range: tuple[int, int], gt_range: tuple[int, int]) -> float:
    """
    Computes Intersection over Union (IoU) between predicted [start, end] and ground truth [start, end].
    """
    p_start, p_end = pred_range
    g_start, g_end = gt_range

    intersection = max(0, min(p_end, g_end) - max(p_start, g_start) + 1)
    union = max(p_end, g_end) - min(p_start, g_start) + 1

    return float(intersection / union) if union > 0 else 0.0


class BenchmarkEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_samples: int
    json_validity_rate: float = Field(..., description="Percentage of responses valid JSON")
    schema_validity_rate: float = Field(..., description="Percentage validating against ReviewResponse schema")
    mean_line_iou: float = Field(..., description="Mean IoU for matched defects")
    category_accuracy: float = Field(..., description="Accuracy on matching defect category")
    severity_accuracy: float = Field(..., description="Accuracy on matching defect severity")
    precision: float
    recall: float
    f1_score: float
    details: Dict[str, Any] = Field(default_factory=dict)


class ReviewerEvaluator:
    def __init__(self, iou_threshold: float = 0.3):
        self.iou_threshold = iou_threshold

    def evaluate(
        self,
        predictions: List[str],
        ground_truths: List[Dict[str, Any]],
    ) -> BenchmarkEvaluation:
        """
        Evaluates model predictions against ground truth review benchmarks.
        """
        total = len(predictions)
        if total == 0:
            return BenchmarkEvaluation(
                total_samples=0,
                json_validity_rate=0.0,
                schema_validity_rate=0.0,
                mean_line_iou=0.0,
                category_accuracy=0.0,
                severity_accuracy=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
            )

        json_valid_count = 0
        schema_valid_count = 0
        parsed_predictions: List[List[Dict[str, Any]]] = []

        # 1. Evaluate JSON & Schema Validity
        for raw in predictions:
            try:
                # Strip code blocks
                clean = raw.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1]
                    clean = clean.rsplit("```", 1)[0].strip()

                data = json.loads(clean)
                json_valid_count += 1

                # Validate expected schema structure
                if isinstance(data, dict) and "findings" in data and isinstance(data["findings"], list):
                    schema_valid_count += 1
                    parsed_predictions.append(data["findings"])
                else:
                    parsed_predictions.append([])
            except Exception:
                parsed_predictions.append([])

        json_validity_rate = round(json_valid_count / total, 4)
        schema_validity_rate = round(schema_valid_count / total, 4)

        # 2. Match findings with ground truth
        total_tp = 0
        total_fp = 0
        total_fn = 0
        matched_ious = []
        matched_categories = 0
        matched_severities = 0
        total_matches = 0

        for pred_findings, gt_item in zip(parsed_predictions, ground_truths):
            gt_findings = gt_item.get("findings", [])
            unmatched_gt = list(gt_findings)

            for pf in pred_findings:
                p_file = pf.get("file_path", "")
                p_range = (pf.get("start_line", 0), pf.get("end_line", 0))
                p_cat = pf.get("category", "").lower()
                p_sev = pf.get("severity", "").lower()

                best_match_idx = None
                best_iou = 0.0

                for idx, gf in enumerate(unmatched_gt):
                    g_file = gf.get("file_path", "")
                    if p_file == g_file:
                        g_range = (gf.get("start_line", 0), gf.get("end_line", 0))
                        iou = compute_line_iou(p_range, g_range)
                        if iou > best_iou:
                            best_iou = iou
                            best_match_idx = idx

                if best_match_idx is not None and best_iou >= self.iou_threshold:
                    total_tp += 1
                    matched_ious.append(best_iou)
                    total_matches += 1

                    matched_gt_finding = unmatched_gt.pop(best_match_idx)
                    if p_cat == matched_gt_finding.get("category", "").lower():
                        matched_categories += 1
                    if p_sev == matched_gt_finding.get("severity", "").lower():
                        matched_severities += 1
                else:
                    total_fp += 1

            total_fn += len(unmatched_gt)

        mean_iou = round(sum(matched_ious) / len(matched_ious), 4) if matched_ious else 0.0
        cat_acc = round(matched_categories / total_matches, 4) if total_matches else 0.0
        sev_acc = round(matched_severities / total_matches, 4) if total_matches else 0.0

        precision = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 0.0
        recall = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 0.0
        f1 = round((2 * precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        return BenchmarkEvaluation(
            total_samples=total,
            json_validity_rate=json_validity_rate,
            schema_validity_rate=schema_validity_rate,
            mean_line_iou=mean_iou,
            category_accuracy=cat_acc,
            severity_accuracy=sev_acc,
            precision=precision,
            recall=recall,
            f1_score=f1,
            details={
                "true_positives": total_tp,
                "false_positives": total_fp,
                "false_negatives": total_fn,
                "total_matches": total_matches,
                "iou_threshold": self.iou_threshold,
            },
        )
