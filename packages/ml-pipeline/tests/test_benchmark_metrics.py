import pytest
from src.benchmark_proof import (
    compute_detection_metrics_per_cwe,
    compute_false_positive_rate_on_negatives,
    compute_hallucination_rate,
    compute_expected_calibration_error,
    compute_noise_suppression_ratio,
    compute_latency_percentiles,
)


def test_detection_metrics_per_cwe_hand_computed():
    """
    Hand-computed test:
    - Case 1 (CWE-89, positive): vulnerable [10, 15]
      Prediction matches [12, 14] -> TP=1, FP=0, FN=0
    - Case 2 (CWE-89, positive): vulnerable [20, 25]
      Prediction is off-target [40, 42] -> TP=0, FP=1, FN=1
    - Case 3 (CWE-89, negative): safe code
      Prediction emits false alarm on line 5 -> FP=1
    - Case 4 (CWE-78, positive): vulnerable [5, 10]
      No prediction emitted -> TP=0, FP=0, FN=1
    """
    cases = [
        {
            "id": "c1",
            "cwe_id": "CWE-89",
            "is_negative": False,
            "vulnerable_line_ranges": [[10, 15]],
        },
        {
            "id": "c2",
            "cwe_id": "CWE-89",
            "is_negative": False,
            "vulnerable_line_ranges": [[20, 25]],
        },
        {
            "id": "c3",
            "cwe_id": "CWE-89",
            "is_negative": True,
            "vulnerable_line_ranges": [],
        },
        {
            "id": "c4",
            "cwe_id": "CWE-78",
            "is_negative": False,
            "vulnerable_line_ranges": [[5, 10]],
        },
    ]

    predictions = {
        "c1": [
            {"category": "security", "start_line": 12, "end_line": 14}
        ],
        "c2": [
            {"category": "security", "start_line": 40, "end_line": 42}
        ],
        "c3": [
            {"category": "security", "start_line": 5, "end_line": 5}
        ],
        "c4": [],
    }

    metrics = compute_detection_metrics_per_cwe(cases, predictions)

    # For CWE-89:
    # TP = 1 (c1)
    # FP = 2 (1 from c2 off-target, 1 from c3 negative false alarm)
    # FN = 1 (c2 missed)
    # Precision = 1 / (1 + 2) = 0.3333
    # Recall = 1 / (1 + 1) = 0.5000
    assert metrics["CWE-89"]["tp"] == 1
    assert metrics["CWE-89"]["fp"] == 2
    assert metrics["CWE-89"]["fn"] == 1
    assert metrics["CWE-89"]["precision"] == 0.3333
    assert metrics["CWE-89"]["recall"] == 0.5

    # For CWE-78:
    # TP = 0, FP = 0, FN = 1
    # Recall = 0.0
    assert metrics["CWE-78"]["tp"] == 0
    assert metrics["CWE-78"]["fp"] == 0
    assert metrics["CWE-78"]["fn"] == 1
    assert metrics["CWE-78"]["recall"] == 0.0


def test_false_positive_rate_on_negatives_hand_computed():
    """
    Hand-computed test:
    Total negative cases = 4
    Flagged negatives with security findings = 1 (neg_2)
    Unflagged negatives = 3 (neg_1, neg_3, neg_4)
    Hand-computed FPR_neg = 1 / 4 = 0.25 (25.0%)
    """
    cases = [
        {"id": "neg_1", "is_negative": True},
        {"id": "neg_2", "is_negative": True},
        {"id": "neg_3", "is_negative": True},
        {"id": "neg_4", "is_negative": True},
        {"id": "pos_1", "is_negative": False},  # Positives must be excluded
    ]

    predictions = {
        "neg_1": [],
        "neg_2": [{"category": "security", "start_line": 5, "end_line": 5}],
        "neg_3": [{"category": "style_nitpick", "start_line": 1, "end_line": 1}],  # Not security!
        "neg_4": [],
        "pos_1": [{"category": "security", "start_line": 10, "end_line": 10}],
    }

    fpr = compute_false_positive_rate_on_negatives(cases, predictions)
    assert fpr == 0.25


def test_hallucination_rate_hand_computed():
    """
    Hand-computed test:
    Total emitted findings = 4
    - Finding 1: line 5 in a 10-line file, valid syntax -> NOT hallucination
    - Finding 2: line 999 in a 10-line file -> out-of-bounds -> HALLUCINATION
    - Finding 3: syntax error in Python code block -> HALLUCINATION
    - Finding 4: line 3 in a 10-line file, valid syntax -> NOT hallucination
    Hand-computed Hallucination Rate = 2 / 4 = 0.50 (50.0%)
    """
    cases = [
        {
            "id": "case_1",
            "language": "python",
            "files": {
                "app.py": "def test():\n    return 42\n" + ("# line\n" * 8)  # 10 lines
            },
        }
    ]

    predictions = {
        "case_1": [
            # 1. Valid
            {
                "file_path": "app.py",
                "start_line": 5,
                "end_line": 5,
                "suggested_code": "x = 10",
            },
            # 2. Out of bounds (line 999 > 10)
            {
                "file_path": "app.py",
                "start_line": 999,
                "end_line": 1005,
                "suggested_code": "x = 20",
            },
            # 3. Invalid Python syntax
            {
                "file_path": "app.py",
                "start_line": 2,
                "end_line": 3,
                "suggested_code": "def broken_syntax(x, :",
            },
            # 4. Valid with indentation stripped
            {
                "file_path": "app.py",
                "start_line": 3,
                "end_line": 4,
                "suggested_code": "    return x + 1",
            },
        ]
    }

    hr = compute_hallucination_rate(cases, predictions)
    assert hr == 0.5


def test_expected_calibration_error_hand_computed():
    """
    Hand-computed test:
    Total samples = 4, 2 equal bins [0.0, 0.5) and [0.5, 1.0]
    Bin 1:
      sample 1: conf = 0.2, acc = False
      sample 2: conf = 0.4, acc = False
      bin_acc = 0.0, bin_conf = 0.3
      diff = |0.0 - 0.3| = 0.3
    Bin 2:
      sample 3: conf = 0.8, acc = True
      sample 4: conf = 0.9, acc = True
      bin_acc = 1.0, bin_conf = 0.85
      diff = |1.0 - 0.85| = 0.15
    ECE = (2/4)*0.3 + (2/4)*0.15 = 0.15 + 0.075 = 0.225
    """
    confidences = [0.2, 0.4, 0.8, 0.9]
    accuracies = [False, False, True, True]

    ece = compute_expected_calibration_error(confidences, accuracies, num_bins=2)
    assert ece == 0.225


def test_noise_suppression_ratio_hand_computed():
    """
    Hand-computed test:
    Raw findings count = 50
    Suppressed findings count = 42
    NSR = 42 / 50 = 0.84 (84.0%)
    """
    nsr = compute_noise_suppression_ratio(raw_findings_count=50, suppressed_findings_count=42)
    assert nsr == 0.84

    # Edge case: 0 raw findings returns 0.0 without DivisionByZero
    assert compute_noise_suppression_ratio(0, 0) == 0.0


def test_latency_percentiles_hand_computed():
    """
    Hand-computed test:
    Latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
    Median (idx 2) = 300.0 ms
    p95 (max / idx 4) = 500.0 ms
    """
    latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
    stats = compute_latency_percentiles(latencies)
    assert stats["median_ms"] == 300.0
    assert stats["p95_ms"] == 500.0
