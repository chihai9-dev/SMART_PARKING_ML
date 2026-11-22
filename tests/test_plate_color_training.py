import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from train_plate_color import compare_metrics, split_color_dataset


class TestPlateColorEvaluationSplit(unittest.TestCase):
    def _dataset(self, real_per_class):
        rows, labels, sources = [], [], []
        for label_index, label in enumerate(("White", "Yellow", "Blue", "Red")):
            for value in range(5):
                rows.append([0.0, label_index, value])
                labels.append(label)
                sources.append("synthetic")
            for value in range(real_per_class):
                rows.append([1.0, label_index, value])
                labels.append(label)
                sources.append("real")
        return pd.DataFrame(rows), np.asarray(labels), np.asarray(sources)

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
