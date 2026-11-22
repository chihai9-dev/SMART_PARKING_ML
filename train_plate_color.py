"""Huấn luyện và so sánh Random Forest với KNN cho màu biển số Việt Nam."""
from __future__ import annotations
import json
import hashlib
import platform
import random
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
from src.data.split_data import split_train_test
from src.evaluation.metrics import evaluate_classification
from src.features.feature_engineering import FEATURE_NAMES, extract_plate_color_features
from src.models.classification import (
    COLOR_LABELS_VI,
    KNN_MODEL_PATH,
    MODEL_PATH,
    train_classification_model,
    train_knn_model,
)
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parent
META_OUT = MODEL_PATH.parent / "model_metadata.json"
CSV_OUT = ROOT / "outputs" / "results" / "classification_results.csv"
CM_FIG_OUT = ROOT / "outputs" / "figures" / "confusion_matrix.png"
FI_FIG_OUT = ROOT / "outputs" / "figures" / "feature_importance.png"
COMPARISON_OUT = ROOT / "outputs" / "results" / "algorithm_comparison.json"
THEMES = {
    "White": ((235,235,232),(20,20,20)),
    "Yellow": ((50,205,240),(20,20,20)),
    "Blue": ((175,75,20),(245,245,245)),
    "Red": ((35,35,195),(245,245,245)),
}

def load_font(size):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def generate_synthetic_plate(label, rng):
    bg, fg = THEMES[label]
    bg_rgb = tuple(int(np.clip(c + rng.randint(-25,25),0,255)) for c in (bg[2],bg[1],bg[0]))
    fg_rgb = (fg[2],fg[1],fg[0])
    two = rng.random() < 0.55
    w,h = (260,190) if two else (420,110)
    image = Image.new("RGB",(w,h),bg_rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle([4,4,w-5,h-5], outline=fg_rgb, width=4)
    font = load_font(rng.randint(36,46))
    prefix = "TM" if label == "Red" else rng.choice(["29","30","51","59","80","92"])
    series = rng.choice(["A","B1","C","F","H1","LD"])
    number = f"{rng.randint(100,999)}.{rng.randint(10,99)}"
    if two:
        draw.text((w*.22,h*.14),f"{prefix}-{series}",fill=fg_rgb,font=font)
        draw.text((w*.16,h*.54),number,fill=fg_rgb,font=font)
    else:
        draw.text((w*.10,h*.26),f"{prefix}{series}-{number}",fill=fg_rgb,font=font)
    bgr = np.asarray(image)[:,:,::-1].copy().astype(np.float32)
    bgr = np.clip(bgr*rng.uniform(.70,1.25)+rng.randint(-25,25),0,255)
    noise = np.random.default_rng(rng.randint(0,99999)).normal(0,6,bgr.shape)
    return np.clip(bgr+noise,0,255).astype(np.uint8)

def build_dataset(samples_per_class=250):
    rng = random.Random(42)
    X, y, sources, groups = [], [], [], []
    counts = {"real":0, "synthetic":0}
    for label in THEMES:
        folder = ROOT / "data" / "labeled_plates" / label
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                image = cv2.imread(str(path)) if path.is_file() else None
                if image is not None:
                    vector, _ = extract_plate_color_features(image)
                    group = str(path.parent.relative_to(folder))
                    if group == ".":
                        group = "ungrouped"
                    X.append(vector); y.append(label); sources.append("real"); groups.append(group); counts["real"] += 1
        for _ in range(samples_per_class):
            vector, _ = extract_plate_color_features(generate_synthetic_plate(label,rng))
            X.append(vector); y.append(label); sources.append("synthetic"); groups.append(""); counts["synthetic"] += 1
    if not X:
        raise RuntimeError("Không có dữ liệu huấn luyện.")
    return pd.DataFrame(X,columns=FEATURE_NAMES), np.asarray(y), np.asarray(sources), np.asarray(groups), counts

def split_color_dataset(X, y, sources, groups=None, test_size=0.2, random_state=42):
    """Keep real capture groups out of training when they are used for evaluation."""
    sources = np.asarray(sources)
    y = np.asarray(y)
    groups = np.arange(len(y)) if groups is None else np.asarray(groups)
    if len(X) != len(y) or len(y) != len(sources) or len(y) != len(groups):
        raise ValueError("X, y, sources và groups phải có cùng số lượng mẫu.")
    if not len(y):
        raise ValueError("Không có dữ liệu để chia.")
    if not set(sources).issubset({"real", "synthetic"}):
        raise ValueError("Nguồn dữ liệu phải là 'real' hoặc 'synthetic'.")

    real_indices = np.flatnonzero(sources == "real")
    synthetic_indices = np.flatnonzero(sources == "synthetic")
    if len(real_indices):
        real_X = X.iloc[real_indices]
        real_y = y[real_indices]
        real_groups = groups[real_indices]
        if len(np.unique(real_groups)) > 1:
            splitter = GroupShuffleSplit(
                n_splits=1,
                test_size=test_size,
                random_state=random_state,
            )
            train_positions, test_positions = next(
                splitter.split(real_X, real_y, groups=real_groups)
            )
            X_real_train = real_X.iloc[train_positions]
            X_test = real_X.iloc[test_positions]
            y_real_train = real_y[train_positions]
            y_test = real_y[test_positions]
        else:
            X_real_train = X.iloc[0:0]
            y_real_train = np.asarray([], dtype=y.dtype)
            X_test, y_test = real_X, real_y

        X_train = pd.concat([X.iloc[synthetic_indices], X_real_train])
        y_train = np.concatenate([y[synthetic_indices], y_real_train])
        return X_train, X_test, y_train, y_test, "real"

    X_train, X_test, y_train, y_test = split_train_test(
        X, y, test_size=test_size, random_state=random_state
    )
    return X_train, X_test, y_train, y_test, "synthetic_only"


def compare_metrics(metrics_by_algorithm, evaluation_source):
    """Rank by macro-F1, then use accuracy, precision, and recall as tie-breakers."""
    ranked = sorted(
        metrics_by_algorithm.items(),
        key=lambda item: (
            item[1]["f1_macro"],
            item[1]["accuracy"],
            item[1]["precision_macro"],
            item[1]["recall_macro"],
        ),
        reverse=True,
    )
    first_name, first_metrics = ranked[0]
    second_name, second_metrics = ranked[1]
    if (
        first_metrics["f1_macro"] == second_metrics["f1_macro"]
        and first_metrics["accuracy"] == second_metrics["accuracy"]
        and first_metrics["precision_macro"] == second_metrics["precision_macro"]
        and first_metrics["recall_macro"] == second_metrics["recall_macro"]
    ):
        winner = None
        outcome = "Hòa: hai thuật toán có cùng cả bốn chỉ số đánh giá."
    else:
        winner = first_name
        outcome = (
            f"{first_name} tốt hơn trên tập đánh giá theo macro-F1 "
            "(accuracy, macro-Precision, macro-Recall dùng lần lượt để phân xử khi hòa)."
        )

    if evaluation_source == "synthetic_only":
        caveat = (
            "Chỉ so sánh trên dữ liệu tổng hợp; chưa thể kết luận thuật toán nào "
            "tốt hơn trên ảnh camera thực tế."
        )
    else:
        caveat = (
            "Kết luận chỉ áp dụng cho tập ảnh thật được giữ riêng; cần kiểm tra "
            "thêm trên các phiên chụp độc lập khác."
        )
    return {
        "metric_priority": [
            "f1_macro",
            "accuracy",
            "precision_macro",
            "recall_macro",
        ],
        "winner": winner,
        "outcome": outcome,
        "evaluation_source": evaluation_source,
        "caveat": caveat,
    }


def main():
    print("1. Tạo dữ liệu và trích xuất 10 đặc trưng HSV...")
    X,y,sources,groups,counts = build_dataset(250)
    print(f"   Ảnh thật: {counts['real']} | ảnh tổng hợp: {counts['synthetic']}")
    X_train,X_test,y_train,y_test,evaluation_source = split_color_dataset(
        X,y,sources,groups,test_size=0.2,random_state=42
    )
    test_sources = sources[X_test.index.to_numpy()]
    test_real_samples = int(np.count_nonzero(test_sources == "real"))
    test_synthetic_samples = int(np.count_nonzero(test_sources == "synthetic"))
    print(f"   Nguồn đánh giá: {'dữ liệu thật' if evaluation_source == 'real' else 'chỉ dữ liệu tổng hợp'}")
    print("2. Huấn luyện Random Forest và KNN trên cùng dữ liệu...")
    model = train_classification_model(X_train.values,y_train,42)
    knn_model = train_knn_model(X_train.values,y_train)
    predictions = {
        "RandomForestClassifier": model.predict(X_test.values),
        "KNeighborsClassifier": knn_model.predict(X_test.values),
    }
    metrics_by_algorithm = {
        name: evaluate_classification(y_test, prediction)
        for name, prediction in predictions.items()
    }
    for name, metrics in metrics_by_algorithm.items():
        print(
            f"{name}: Accuracy={metrics['accuracy']} | "
            f"F1-macro={metrics['f1_macro']}"
        )
        print(metrics["report"])
    comparison = compare_metrics(metrics_by_algorithm, evaluation_source)
    print(f"Kết luận: {comparison['outcome']} {comparison['caveat']}")
    for path in (
        MODEL_PATH,
        KNN_MODEL_PATH,
        CSV_OUT,
        CM_FIG_OUT,
        FI_FIG_OUT,
        META_OUT,
        COMPARISON_OUT,
    ):
        path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,MODEL_PATH)
    joblib.dump(knn_model,KNN_MODEL_PATH)
    artifact_sha256 = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    knn_sha256 = hashlib.sha256(
        KNN_MODEL_PATH.read_bytes()
    ).hexdigest()
    model_config = model.get_params()
    result_rows = []
    model_hashes = {
        "RandomForestClassifier": artifact_sha256,
        "KNeighborsClassifier": knn_sha256,
    }
    for name, metrics in metrics_by_algorithm.items():
        is_random_forest = name == "RandomForestClassifier"
        config = model_config if is_random_forest else (
            knn_model.named_steps["classifier"].get_params()
        )
        result_rows.append({
            "model": name,
            "n_estimators": config.get("n_estimators") if is_random_forest else None,
            "max_depth": config.get("max_depth") if is_random_forest else None,
            "n_neighbors": config.get("n_neighbors"),
            "weights": config.get("weights"),
            "feature_scaling": "none" if is_random_forest else "StandardScaler",
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "real_samples": counts["real"],
            "synthetic_samples": counts["synthetic"],
            "evaluation_source": evaluation_source,
            "test_real_samples": test_real_samples,
            "test_synthetic_samples": test_synthetic_samples,
            "model_version": model_hashes[name][:16],
            "model_sha256": model_hashes[name],
            "accuracy": metrics["accuracy"],
            "precision_macro": metrics["precision_macro"],
            "recall_macro": metrics["recall_macro"],
            "f1_macro": metrics["f1_macro"],
        })
    pd.DataFrame(result_rows).to_csv(CSV_OUT,index=False)
    comparison_payload = {
        **comparison,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "test_real_samples": test_real_samples,
        "test_synthetic_samples": test_synthetic_samples,
        "algorithms": {
            name: {
                "model_version": model_hashes[name][:16],
                "metrics": {
                    key: value
                    for key, value in metrics.items()
                    if key not in ("report", "labels")
                },
            }
            for name, metrics in metrics_by_algorithm.items()
        },
    }
    COMPARISON_OUT.write_text(
        json.dumps(comparison_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metrics = metrics_by_algorithm["RandomForestClassifier"]
    labels = metrics["labels"]
    plt.figure(figsize=(6,5))
    sns.heatmap(np.asarray(metrics["confusion_matrix"]),annot=True,fmt="d",cmap="Blues",
                xticklabels=labels,yticklabels=labels)
    plt.title(f"Confusion Matrix - Random Forest ({evaluation_source})")
    plt.xlabel("Predicted"); plt.ylabel("Actual"); plt.tight_layout()
    plt.savefig(CM_FIG_OUT,dpi=150); plt.close()
    importance = pd.Series(model.feature_importances_,index=FEATURE_NAMES).sort_values()
    plt.figure(figsize=(7,4.5)); importance.plot(kind="barh")
    plt.title("Feature Importance - Random Forest"); plt.xlabel("Importance")
    plt.tight_layout(); plt.savefig(FI_FIG_OUT,dpi=150); plt.close()
    metadata = {
        "task":"Phân loại màu nền biển số xe (4 nhóm)",
        "algorithm":"RandomForestClassifier","classes":list(model.classes_),
        "model_artifact":MODEL_PATH.name,
        "comparison_model":{
            "algorithm":"KNeighborsClassifier",
            "model_artifact":KNN_MODEL_PATH.name,
            "model_version":knn_sha256[:16],
            "model_sha256":knn_sha256,
            "n_neighbors":knn_model.named_steps["classifier"].n_neighbors,
            "weights":knn_model.named_steps["classifier"].weights,
            "feature_scaling":"StandardScaler",
        },
        "class_labels_vi":COLOR_LABELS_VI,"features":FEATURE_NAMES,
        "dataset_source_counts":counts,
        "real_capture_groups":int(len(set(groups[sources == "real"]))),
        "evaluation_source":evaluation_source,
        "evaluation_sample_counts":{
            "real":test_real_samples,
            "synthetic":test_synthetic_samples,
        },
        "evaluation_note":(
            "Chỉ số tính trên các capture group ảnh thật đã giữ riêng; synthetic chỉ tham gia huấn luyện."
            if evaluation_source == "real"
            else "Chỉ số chỉ phản ánh dữ liệu tổng hợp, không đại diện độ chính xác trên camera thực tế."
        ),
        "model_version":artifact_sha256[:16],
        "model_sha256":artifact_sha256,
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "feature_schema_version":"plate-color-hsv-v1",
        "training_config":{
            "n_estimators":model_config["n_estimators"],
            "max_depth":model_config["max_depth"],
            "min_samples_split":model_config["min_samples_split"],
            "class_weight":model_config["class_weight"],
            "random_state":model_config["random_state"],
            "synthetic_samples_per_class":250,
        },
        "runtime":{
            "python":platform.python_version(),
            "scikit_learn":sklearn.__version__,
        },
        "confidence_calibration":"uncalibrated_random_forest_probabilities",
        "test_metrics":{k:v for k,v in metrics.items() if k not in ("report","labels")},
        "algorithm_comparison":comparison_payload,
    }
    META_OUT.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Đã lưu mô hình: {MODEL_PATH}")

if __name__ == "__main__":
    main()
