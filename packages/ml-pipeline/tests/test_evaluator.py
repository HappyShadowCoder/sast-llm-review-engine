import json
from src.evaluate_reviewer import ReviewerEvaluator, compute_line_iou


def test_line_iou_calculation():
    # Exact match
    assert compute_line_iou((10, 20), (10, 20)) == 1.0

    # Partial overlap: [10, 15] vs [12, 18]
    # intersection: [12, 15] -> 4 lines (12, 13, 14, 15)
    # union: [10, 18] -> 9 lines (10..18)
    # IoU: 4 / 9
    assert round(compute_line_iou((10, 15), (12, 18)), 4) == round(4 / 9, 4)

    # Disjoint ranges -> 0.0
    assert compute_line_iou((1, 5), (10, 15)) == 0.0


def test_reviewer_evaluator_benchmark():
    evaluator = ReviewerEvaluator(iou_threshold=0.3)

    # Ground truth: 2 defects
    ground_truth = [
        {
            "findings": [
                {
                    "file_path": "src/auth.py",
                    "start_line": 15,
                    "end_line": 18,
                    "category": "security",
                    "severity": "critical",
                },
                {
                    "file_path": "src/routes.py",
                    "start_line": 40,
                    "end_line": 45,
                    "category": "architecture",
                    "severity": "high",
                },
            ]
        }
    ]

    # Predictions: 1 true positive matching defect 1, 1 false positive, defect 2 missed (false negative)
    pred_response = json.dumps({
        "summary": "Review summary",
        "findings": [
            {
                "file_path": "src/auth.py",
                "start_line": 16,
                "end_line": 18,
                "category": "security",
                "severity": "critical",
                "confidence": 0.95,
                "explanation": "SQLi in query",
                "suggested_code": "cursor.execute(%s)",
            },
            {
                "file_path": "src/unused.py",
                "start_line": 1,
                "end_line": 5,
                "category": "performance",
                "severity": "medium",
                "confidence": 0.85,
                "explanation": "False positive finding",
                "suggested_code": "pass",
            },
        ],
    })

    results = evaluator.evaluate([pred_response], ground_truth)

    assert results.total_samples == 1
    assert results.json_validity_rate == 1.0
    assert results.schema_validity_rate == 1.0
    assert results.details["true_positives"] == 1
    assert results.details["false_positives"] == 1
    assert results.details["false_negatives"] == 1
    # Precision = 1 / (1 + 1) = 0.5
    assert results.precision == 0.5
    # Recall = 1 / (1 + 1) = 0.5
    assert results.recall == 0.5
    # F1 = 0.5
    assert results.f1_score == 0.5
    assert results.category_accuracy == 1.0
    assert results.severity_accuracy == 1.0
    assert results.mean_line_iou > 0.0
