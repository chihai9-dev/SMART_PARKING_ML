"""Evaluate full ALPR inference against a manifest of real labeled images."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from src.evaluation.metrics import evaluate_classification
from src.models.classification import load_color_model, predict_plate_color
from src.vision.plate_ocr import normalize_plate, recognize_plate

ROOT = Path(__file__).resolve().parents[2]
_REQUIRED_COLUMNS = {"image_path", "plate_true", "source"}
_BBOX_COLUMNS = ("bbox_x", "bbox_y", "bbox_width", "bbox_height")


def character_error_rate(expected: str, actual: str) -> float:
    """Return normalized Levenshtein distance for two plate strings."""
    expected = normalize_plate(expected)
    actual = normalize_plate(actual)
    if not expected:
        raise ValueError("Ground-truth plate must not be empty.")
    previous = list(range(len(actual) + 1))
    for row, expected_char in enumerate(expected, start=1):
        current = [row]
        for column, actual_char in enumerate(actual, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (expected_char != actual_char),
            ))
        previous = current
    return previous[-1] / len(expected)


def intersection_over_union(
    expected: list[float] | tuple[float, ...],
    actual: list[float] | tuple[float, ...] | None,
) -> float:
    """Calculate IoU for boxes represented as x, y, width, height."""
    if actual is None:
        return 0.0
    ex, ey, ew, eh = expected
    ax, ay, aw, ah = actual
    left = max(ex, ax)
    top = max(ey, ay)
    right = min(ex + ew, ax + aw)
    bottom = min(ey + eh, ay + ah)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = ew * eh + aw * ah - intersection
    return intersection / union if union > 0 else 0.0


def _bbox_from_row(row: pd.Series) -> list[float] | None:
    if not all(
        column in row.index and str(row[column]).strip() != ""
        for column in _BBOX_COLUMNS
    ):
        return None
    box = [float(row[column]) for column in _BBOX_COLUMNS]
    if box[2] <= 0 or box[3] <= 0:
        raise ValueError("Ground-truth bounding boxes must have positive dimensions.")
    return box


def _read_manifest(path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(path, keep_default_na=False)
    missing = _REQUIRED_COLUMNS - set(manifest.columns)
    if missing:
        raise ValueError("Manifest is missing columns: " + ", ".join(sorted(missing)))
    if manifest.empty:
        raise ValueError("Manifest has no labeled image rows.")
    sources = manifest["source"].astype(str).str.strip().str.lower()
    if not sources.eq("real").all():
        raise ValueError("Benchmark requires real images only; source must be 'real' for every row.")
    if manifest["plate_true"].astype(str).str.strip().eq("").any():
        raise ValueError("Every benchmark row must have a ground-truth plate_true.")
    return manifest


def _decode_crop(encoded: str | None) -> np.ndarray | None:
    if not encoded:
        return None
    raw = base64.b64decode(encoded, validate=True)
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    return image


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_benchmark(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run OCR, color classification and optional detector-IoU evaluation."""
    manifest_path = manifest_path.resolve()
    manifest = _read_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    color_model = load_color_model()
    rows: list[dict[str, Any]] = []

    for index, row in manifest.iterrows():
        image_path = Path(str(row["image_path"]))
        if not image_path.is_absolute():
            image_path = manifest_path.parent / image_path
        if not image_path.is_file():
            raise FileNotFoundError(f"Image for row {index + 2} does not exist: {image_path}")

        started = time.perf_counter()
        prediction = recognize_plate(str(image_path))
        predicted_plate = normalize_plate(prediction.get("plate") or "")
        color_prediction = None
        crop = _decode_crop(prediction.get("crop_jpeg_b64"))
        if color_model is not None and crop is not None and str(row.get("color_true", "")).strip():
            color_prediction = predict_plate_color(color_model, crop)
        elapsed_ms = (time.perf_counter() - started) * 1000

        expected_plate = normalize_plate(str(row["plate_true"]))
        expected_box = _bbox_from_row(row)
        predicted_box = prediction.get("bbox")
        rows.append({
            "image_path": str(row["image_path"]),
            "group_id": str(row.get("group_id", "")),
            "ocr_engine": prediction.get("engine", "none"),
            "plate_true": expected_plate,
            "plate_pred": predicted_plate,
            "plate_exact_match": expected_plate == predicted_plate,
            "character_error_rate": character_error_rate(expected_plate, predicted_plate),
            "color_true": str(row.get("color_true", "")).strip(),
            "color_pred": (color_prediction or {}).get("color_code", "Unknown"),
            "color_confidence": (color_prediction or {}).get("confidence"),
            "bbox_iou": (
                intersection_over_union(expected_box, predicted_box)
                if expected_box is not None
                else None
            ),
            "inference_time_ms": round(elapsed_ms, 2),
        })

    results = pd.DataFrame(rows)
    results.to_csv(output_dir / "per_image_results.csv", index=False)
    color_rows = results[results["color_true"].ne("")]
    color_metrics = None
    if not color_rows.empty:
        metrics = evaluate_classification(color_rows["color_true"], color_rows["color_pred"])
        color_metrics = {key: value for key, value in metrics.items() if key not in {"report", "labels"}}

    iou_values = results["bbox_iou"].dropna()
    groups = manifest["group_id"].astype(str).str.strip() if "group_id" in manifest else pd.Series(dtype=str)
    summary = {
        "evaluation_source": "real_labeled_images",
        "sample_count": int(len(results)),
        "capture_group_count": int(groups[groups.ne("")].nunique()) if not groups.empty else 0,
        "plate_exact_match_rate": round(float(results["plate_exact_match"].mean()), 4),
        "plate_character_error_rate": round(float(results["character_error_rate"].mean()), 4),
        "plate_detection_iou": (
            {"mean": round(float(iou_values.mean()), 4), "sample_count": int(len(iou_values))}
            if not iou_values.empty
            else None
        ),
        "plate_color_metrics": color_metrics,
        "mean_inference_time_ms": round(float(results["inference_time_ms"].mean()), 2),
        "ocr_engine_counts": {
            str(engine): int(count)
            for engine, count in results["ocr_engine"].value_counts().items()
        },
        "model_artifacts": {
            "plate_detector_onnx_sha256": _sha256_file(ROOT / "models" / "vision" / "best.onnx"),
            "plate_color_sha256": _sha256_file(ROOT / "models" / "classification" / "best_classification_model.pkl"),
        },
        "manifest": manifest_path.name,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="CSV labels manifest")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/alpr_benchmark"))
    args = parser.parse_args()
    summary = run_benchmark(args.manifest, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
