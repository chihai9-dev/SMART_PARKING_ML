import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from train_plate_color import (
    compare_metrics,
    evaluate_models_runtime,
    split_color_dataset,
    summarize_repeated_evaluation,
)
from src.evaluation.metrics import evaluate_classification


class TestPlateColorEvaluationSplit(unittest.TestCase):
    def _dataset(self, real_per_class):
        rows, labels, sources = [], [], []
        for label_index, label in enumerate(("White", "Yellow")):
            for value in range(5):
                rows.append([0.0, label_index, value])
                labels.append(label)
                sources.append("synthetic")
            for value in range(real_per_class):
                rows.append([1.0, label_index, value])
                labels.append(label)
                sources.append("real")
        return pd.DataFrame(rows), np.asarray(labels), np.asarray(sources)

    def test_repeated_summary_reports_quality_and_stability_without_overclaiming(self):
        runs = [
            {
                "run": 1,
                "algorithms": {
                    "RandomForestClassifier": {
                        "accuracy": 0.8,
                        "precision_macro": 0.8,
                        "recall_macro": 0.8,
                        "f1_macro": 0.7,
                        "median_ms_per_image": 1.0,
                    },
                    "KNeighborsClassifier": {
                        "accuracy": 0.94,
                        "precision_macro": 0.94,
                        "recall_macro": 0.94,
                        "f1_macro": 0.84,
                        "median_ms_per_image": 0.5,
                    },
                },
            },
            {
                "run": 2,
                "algorithms": {
                    "RandomForestClassifier": {
                        "accuracy": 1.0,
                        "precision_macro": 1.0,
                        "recall_macro": 1.0,
                        "f1_macro": 0.9,
                        "median_ms_per_image": 1.2,
                    },
                    "KNeighborsClassifier": {
                        "accuracy": 0.96,
                        "precision_macro": 0.96,
                        "recall_macro": 0.96,
                        "f1_macro": 0.86,
                        "median_ms_per_image": 0.6,
                    },
                },
            },
        ]

        report = summarize_repeated_evaluation(runs, "real")

        self.assertEqual(report["run_count"], 2)
        self.assertIn("GroupShuffleSplit", report["method"])
        self.assertEqual(report["quality_leader"], "KNeighborsClassifier")
        self.assertEqual(report["stability_leader"], "KNeighborsClassifier")
        self.assertAlmostEqual(
            report["summary"]["KNeighborsClassifier"]["f1_macro_mean"], 0.85
        )
        self.assertIn("không phải các mẫu độc lập", report["caveat"])

        synthetic_report = summarize_repeated_evaluation(runs, "synthetic_only")
        self.assertIn("synthetic", synthetic_report["method"])
        self.assertIn("không đại diện", synthetic_report["caveat"])

    def test_real_images_are_the_only_evaluation_samples(self):
        X, y, sources = self._dataset(real_per_class=2)
        X_train, X_test, _, _, evaluation_source = split_color_dataset(
            X, y, sources, test_size=0.25, random_state=42
        )

        self.assertEqual(evaluation_source, "real")
        self.assertTrue((X_test.iloc[:, 0] == 1.0).all())
        self.assertTrue((X_train.iloc[:, 0] == 0.0).any())

    def test_real_capture_groups_do_not_leak_between_train_and_test(self):
        X, y, sources = self._dataset(real_per_class=2)
        groups = np.asarray([
            (f"capture-{i % 2}" if source == "real" else "")
            for i, source in enumerate(sources)
        ])
        X_train, X_test, _, _, evaluation_source = split_color_dataset(
            X, y, sources, groups, test_size=0.5, random_state=42
        )

        real_train_groups = set(groups[X_train.index.to_numpy()])
        real_test_groups = set(groups[X_test.index.to_numpy()])
        real_train_groups.discard("")
        real_test_groups.discard("")
        self.assertEqual(evaluation_source, "real")
        self.assertTrue(real_train_groups.isdisjoint(real_test_groups))

    def test_synthetic_only_evaluation_is_labeled(self):
        X, y, sources = self._dataset(real_per_class=0)
        _, X_test, _, _, evaluation_source = split_color_dataset(
            X, y, sources, test_size=0.2, random_state=42
        )

        self.assertEqual(evaluation_source, "synthetic_only")
        self.assertGreater(len(X_test), 0)

    def test_comparison_uses_macro_f1_and_marks_synthetic_limit(self):
        comparison = compare_metrics(
            {
                "RandomForestClassifier": {
                    "f1_macro": 0.8,
                    "accuracy": 0.9,
                    "precision_macro": 0.82,
                    "recall_macro": 0.78,
                },
                "KNeighborsClassifier": {
                    "f1_macro": 0.85,
                    "accuracy": 0.86,
                    "precision_macro": 0.84,
                    "recall_macro": 0.86,
                },
            },
            "synthetic_only",
        )

        self.assertEqual(comparison["winner"], "KNeighborsClassifier")
        self.assertIn("tổng hợp", comparison["caveat"])

    def test_comparison_does_not_claim_winner_when_metrics_tie(self):
        metrics = {
            "f1_macro": 0.8,
            "accuracy": 0.9,
            "precision_macro": 0.88,
            "recall_macro": 0.79,
        }
        comparison = compare_metrics(
            {
                "RandomForestClassifier": metrics,
                "KNeighborsClassifier": metrics,
            },
            "real",
        )

        self.assertIsNone(comparison["winner"])
        self.assertTrue(comparison["outcome"].startswith("Hòa"))

    def test_comparison_uses_speed_only_when_quality_metrics_tie(self):
        metrics = {
            "f1_macro": 0.8,
            "accuracy": 0.9,
            "precision_macro": 0.88,
            "recall_macro": 0.79,
        }
        comparison = compare_metrics(
            {
                "RandomForestClassifier": metrics,
                "KNeighborsClassifier": metrics,
            },
            "real",
            {
                "RandomForestClassifier": {"median_ms_per_image": 1.0},
                "KNeighborsClassifier": {"median_ms_per_image": 1.2},
            },
        )

        self.assertEqual(comparison["winner"], "RandomForestClassifier")
        self.assertEqual(comparison["decision_basis"], "inference_speed_tiebreak")
        self.assertIn("nhanh hơn", comparison["outcome"])

    def test_small_speed_difference_does_not_select_a_winner(self):
        metrics = {
            "f1_macro": 0.8,
            "accuracy": 0.9,
            "precision_macro": 0.88,
            "recall_macro": 0.79,
        }
        comparison = compare_metrics(
            {
                "RandomForestClassifier": metrics,
                "KNeighborsClassifier": metrics,
            },
            "real",
            {
                "RandomForestClassifier": {"median_ms_per_image": 1.0},
                "KNeighborsClassifier": {"median_ms_per_image": 1.02},
            },
        )

        self.assertIsNone(comparison["winner"])
        self.assertIn("5%", comparison["outcome"])

    def test_quality_metrics_take_priority_over_speed(self):
        comparison = compare_metrics(
            {
                "RandomForestClassifier": {
                    "f1_macro": 0.81,
                    "accuracy": 0.9,
                    "precision_macro": 0.8,
                    "recall_macro": 0.82,
                },
                "KNeighborsClassifier": {
                    "f1_macro": 0.85,
                    "accuracy": 0.88,
                    "precision_macro": 0.84,
                    "recall_macro": 0.86,
                },
            },
            "real",
            {
                "RandomForestClassifier": {"median_ms_per_image": 0.5},
                "KNeighborsClassifier": {"median_ms_per_image": 1.5},
            },
        )

        self.assertEqual(comparison["winner"], "KNeighborsClassifier")
        self.assertEqual(comparison["decision_basis"], "quality_metrics")

    def test_runtime_evaluation_reports_confidence_and_latency(self):
        from sklearn.ensemble import RandomForestClassifier
        from src.models.classification import train_knn_model

        X_train = np.asarray([
            [0], [0.1], [0.2], [0.3],
            [1], [1.1], [1.2], [1.3],
        ])
        y_train = np.asarray(["White"] * 4 + ["Yellow"] * 4)
        X_train_scaled_shape = np.repeat(X_train, 3, axis=1)
        forest = RandomForestClassifier(n_estimators=5, random_state=42).fit(
            X_train_scaled_shape, y_train
        )
        knn = train_knn_model(
            X_train_scaled_shape,
            y_train,
        )
        X_test = np.asarray([[0.05, 0.05, 0.05], [1.05, 1.05, 1.05]])
        evaluation = evaluate_models_runtime(
            {"RandomForestClassifier": forest, "KNeighborsClassifier": knn},
            X_test,
            np.asarray(["White", "Yellow"]),
            repeats=2,
        )

        for model_evaluation in evaluation.values():
            self.assertGreaterEqual(model_evaluation["mean_confidence"], 0)
            self.assertLessEqual(model_evaluation["mean_confidence"], 1)
            self.assertGreater(model_evaluation["median_ms_per_image"], 0)
            self.assertGreaterEqual(
                model_evaluation["p95_ms_per_image"],
                model_evaluation["median_ms_per_image"],
            )

    def test_confusion_matrix_and_per_class_metrics_keep_all_color_labels(self):
        metrics = evaluate_classification(
            ["White", "Yellow", "White"],
            ["White", "White", "White"],
            labels=["Blue", "Red", "White", "Yellow"],
        )

        self.assertEqual(metrics["labels"], ["Blue", "Red", "White", "Yellow"])
        self.assertEqual(len(metrics["confusion_matrix"]), 4)
        self.assertEqual(metrics["per_class"]["Blue"]["support"], 0)
        self.assertEqual(metrics["per_class"]["Yellow"]["recall"], 0.0)

    def test_comparison_uses_precision_then_recall_to_break_ties(self):
        comparison = compare_metrics(
            {
                "RandomForestClassifier": {
                    "f1_macro": 0.8,
                    "accuracy": 0.9,
                    "precision_macro": 0.8,
                    "recall_macro": 0.8,
                },
                "KNeighborsClassifier": {
                    "f1_macro": 0.8,
                    "accuracy": 0.9,
                    "precision_macro": 0.85,
                    "recall_macro": 0.75,
                },
            },
            "real",
        )

        self.assertEqual(comparison["winner"], "KNeighborsClassifier")


if __name__ == "__main__":
    unittest.main()
