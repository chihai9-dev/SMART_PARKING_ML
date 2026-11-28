"""Huấn luyện và so sánh HOG + SVM với Random Forest và KNN cho nhận diện ký tự biển số VN."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sklearn
from PIL import Image, ImageDraw, ImageFont
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from src.features.char_hog import CHAR_IMAGE_SIZE, extract_char_hog_features

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET_DIR = ROOT / "data" / "char_dataset"
SVM_MODEL_OUT = ROOT / "models" / "classification" / "char_svm_model.joblib"
META_OUT = ROOT / "models" / "classification" / "char_model_metadata.json"
COMPARISON_OUT = ROOT / "outputs" / "results" / "char_algorithm_comparison.json"
CM_FIG_OUT = ROOT / "outputs" / "figures" / "char_confusion_matrix.png"

VN_CHAR_CLASSES = list("0123456789ABCDEFGHKLMNPRSTUVXYZ")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def generate_synthetic_char(label: str, rng: random.Random) -> np.ndarray:
    """Sinh ảnh ký tự biển số giả lập (dùng để kiểm thử luồng hoặc bổ sung train)."""
    w, h = rng.randint(24, 34), rng.randint(38, 52)
    bg_val = rng.randint(175, 245)
    fg_val = rng.randint(5, 65)
    img = Image.new("L", (w, h), bg_val)
    draw = ImageDraw.Draw(img)
    font = _load_font(rng.randint(26, 36))
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) // 2 - bbox[0] + rng.randint(-2, 2)
    y = (h - th) // 2 - bbox[1] + rng.randint(-2, 2)
    draw.text((x, y), label, fill=fg_val, font=font)

    angle = rng.uniform(-7.0, 7.0)
    img = img.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=bg_val)
    arr = np.asarray(img, dtype=np.float32)
    if rng.random() < 0.35:
        arr = cv2.GaussianBlur(arr, (3, 3), 0)
    noise = np.random.default_rng(rng.randint(0, 999999)).normal(0, 6.0, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)


def _plate_group_from_path(path: Path) -> str:
    """Suy ra ID biển số từ tên file (VD: plate001_char3.jpg → plate001) để chống leakage."""
    stem = path.stem
    if "_char" in stem:
        return stem.split("_char")[0]
    parts = stem.rsplit("_", 1)
    return parts[0] if len(parts) == 2 else stem


def _load_split_folder(split_dir: Path) -> tuple[list[np.ndarray], list[str], list[str]]:
    X, y, groups = [], [], []
    if not split_dir.is_dir():
        return X, y, groups
    for class_dir in sorted(split_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        label = class_dir.name.strip().upper()
        for img_path in sorted(class_dir.iterdir()):
            if img_path.suffix.lower() not in IMAGE_EXTS:
                continue
            img = cv2.imread(str(img_path))
            if img is None or img.size == 0:
                continue
            X.append(extract_char_hog_features(img, size=CHAR_IMAGE_SIZE))
            y.append(label)
            groups.append(_plate_group_from_path(img_path))
    return X, y, groups


def load_character_dataset(
    dataset_dir: Path,
    synthetic_per_class: int = 40,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    """Tải tập train/test ký tự.

    Hỗ trợ 3 cấu trúc:
    1. `dataset_dir/train/<CLASS>/...` và `dataset_dir/test/<CLASS>/...` (hoặc `valid`)
    2. `dataset_dir/<CLASS>/...` (tự chia 80/20 theo nhóm biển số để chống leakage)
    3. Nếu chưa có ảnh thật → tự sinh tập synthetic để test toàn bộ luồng.
    """
    train_dir = dataset_dir / "train"
    test_dir = dataset_dir / "test" if (dataset_dir / "test").is_dir() else dataset_dir / "valid"

    if train_dir.is_dir() and test_dir.is_dir():
        X_tr, y_tr, _ = _load_split_folder(train_dir)
        X_te, y_te, _ = _load_split_folder(test_dir)
        if X_tr and X_te:
            return (
                np.asarray(X_tr, dtype=np.float32),
                np.asarray(X_te, dtype=np.float32),
                np.asarray(y_tr),
                np.asarray(y_te),
                "real_presplit",
            )

    if dataset_dir.is_dir():
        X_all, y_all, groups = _load_split_folder(dataset_dir)
        if X_all:
            X_arr = np.asarray(X_all, dtype=np.float32)
            y_arr = np.asarray(y_all)
            g_arr = np.asarray(groups)
            if len(np.unique(g_arr)) > 5:
                splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
                tr_idx, te_idx = next(splitter.split(X_arr, y_arr, groups=g_arr))
                return X_arr[tr_idx], X_arr[te_idx], y_arr[tr_idx], y_arr[te_idx], "real_grouped"
            X_tr, X_te, y_tr, y_te = train_test_split(
                X_arr, y_arr, test_size=0.2, random_state=seed, stratify=y_arr
            )
            return X_tr, X_te, y_tr, y_te, "real_stratified"

    # Fallback tổng hợp khi người dùng chưa tải dataset thật
    rng = random.Random(seed)
    X_syn, y_syn = [], []
    for label in VN_CHAR_CLASSES:
        for _ in range(synthetic_per_class):
            img = generate_synthetic_char(label, rng)
            X_syn.append(extract_char_hog_features(img, size=CHAR_IMAGE_SIZE))
            y_syn.append(label)
    X_arr = np.asarray(X_syn, dtype=np.float32)
    y_arr = np.asarray(y_syn)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_arr, y_arr, test_size=0.2, random_state=seed, stratify=y_arr
    )
    return X_tr, X_te, y_tr, y_te, "synthetic_only"


def build_candidate_models(seed: int = 42, svm_c: float = 10.0) -> dict[str, object]:
    """Khởi tạo 3 mô hình trên đặc trưng HOG để huấn luyện và so sánh."""
    return {
        "SVM_RBF": Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", SVC(
                kernel="rbf",
                C=svm_c,
                gamma="scale",
                probability=True,
                class_weight="balanced",
                random_state=seed,
            )),
        ]),
        "RandomForest": RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "KNN": Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", KNeighborsClassifier(n_neighbors=5, weights="distance")),
        ]),
    }


def evaluate_model(model, X_test: np.ndarray, y_test: np.ndarray) -> dict[str, float]:
    t0 = time.perf_counter()
    preds = model.predict(X_test)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "accuracy": round(float(accuracy_score(y_test, preds)), 6),
        "precision_macro": round(float(precision_score(y_test, preds, average="macro", zero_division=0)), 6),
        "recall_macro": round(float(recall_score(y_test, preds, average="macro", zero_division=0)), 6),
        "f1_macro": round(float(f1_score(y_test, preds, average="macro", zero_division=0)), 6),
        "ms_per_char": round(float(elapsed_ms / max(len(X_test), 1)), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train & so sánh HOG + SVM / RF / KNN cho ký tự biển số VN")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--svm-c", type=float, default=10.0)
    parser.add_argument("--synthetic-per-class", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"1. Tải dữ liệu ký tự từ: {args.data_dir}")
    X_train, X_test, y_train, y_test, eval_source = load_character_dataset(
        args.data_dir,
        synthetic_per_class=args.synthetic_per_class,
        seed=args.seed,
    )
    classes = sorted(set(y_train.tolist()) | set(y_test.tolist()))
    print(
        f"   Nguồn: {eval_source} | Số lớp: {len(classes)} | "
        f"Train: {len(X_train)} | Test: {len(X_test)} | Chiều HOG: {X_train.shape[1]}"
    )

    print("2. Huấn luyện và so sánh SVM (RBF), Random Forest, KNN trên đặc trưng HOG...")
    models = build_candidate_models(seed=args.seed, svm_c=args.svm_c)
    results: dict[str, dict[str, float]] = {}
    for name, clf in models.items():
        t0 = time.perf_counter()
        clf.fit(X_train, y_train)
        train_sec = round(time.perf_counter() - t0, 2)
        metrics = evaluate_model(clf, X_test, y_test)
        metrics["train_seconds"] = train_sec
        results[name] = metrics
        print(
            f"   {name:14s} | Acc={metrics['accuracy']:.4f} | "
            f"Macro-F1={metrics['f1_macro']:.4f} | "
            f"{metrics['ms_per_char']:.3f} ms/ký tự | train {train_sec}s"
        )

    for out_path in (SVM_MODEL_OUT, META_OUT, COMPARISON_OUT, CM_FIG_OUT):
        out_path.parent.mkdir(parents=True, exist_ok=True)

    svm_model = models["SVM_RBF"]
    joblib.dump(svm_model, SVM_MODEL_OUT)
    model_sha256 = hashlib.sha256(SVM_MODEL_OUT.read_bytes()).hexdigest()

    # Lưu Confusion Matrix của mô hình chính (HOG + SVM)
    svm_preds = svm_model.predict(X_test)
    cm = confusion_matrix(y_test, svm_preds, labels=classes)
    plt.figure(figsize=(12, 10))
    sns.heatmap(cm, annot=len(classes) <= 20, fmt="d", cmap="Blues", xticklabels=classes, yticklabels=classes)
    plt.title(f"Confusion Matrix - HOG + SVM ({eval_source})")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(CM_FIG_OUT, dpi=150)
    plt.close()

    winner = max(results.items(), key=lambda kv: (kv[1]["f1_macro"], kv[1]["accuracy"]))[0]
    comparison_payload = {
        "feature_extractor": "HOG (32x32, cell=8x8, block=16x16, nbins=9 -> 324 dims)",
        "evaluation_source": eval_source,
        "num_classes": len(classes),
        "classes": classes,
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "winner": winner,
        "algorithms": results,
    }
    COMPARISON_OUT.write_text(
        json.dumps(comparison_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata = {
        "task": "Phân loại ký tự biển số xe Việt Nam (HOG + SVM)",
        "algorithm": "SVC(kernel='rbf', probability=True)",
        "model_artifact": SVM_MODEL_OUT.name,
        "model_sha256": model_sha256,
        "feature_dim": int(X_train.shape[1]),
        "char_image_size": list(CHAR_IMAGE_SIZE),
        "classes": classes,
        "evaluation_source": eval_source,
        "test_metrics": results["SVM_RBF"],
        "comparison": comparison_payload,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
        },
    }
    META_OUT.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"3. Đã lưu mô hình chính HOG + SVM tại: {SVM_MODEL_OUT}")
    print(f"   Báo cáo so sánh: {COMPARISON_OUT}")
    print(f"   Confusion Matrix: {CM_FIG_OUT}")


if __name__ == "__main__":
    main()
