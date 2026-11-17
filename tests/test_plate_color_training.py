import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from train_plate_color import split_color_dataset


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

    def test_synthetic_only_evaluation_is_labeled(self):
        X, y, sources = self._dataset(real_per_class=0)
        _, X_test, _, _, evaluation_source = split_color_dataset(
            X, y, sources, test_size=0.2, random_state=42
        )

        self.assertEqual(evaluation_source, "synthetic_only")
        self.assertGreater(len(X_test), 0)


if __name__ == "__main__":
    unittest.main()
