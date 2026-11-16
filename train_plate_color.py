"""Huấn luyện Random Forest phân loại màu nền biển số Việt Nam."""
from __future__ import annotations
import json
import random
from pathlib import Path
import cv2
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from PIL import Image, ImageDraw, ImageFont
from src.data.split_data import split_train_test
from src.evaluation.metrics import evaluate_classification
from src.features.feature_engineering import FEATURE_NAMES, extract_plate_color_features
from src.models.classification import COLOR_LABELS_VI, MODEL_PATH, train_classification_model

ROOT = Path(__file__).resolve().parent
META_OUT = MODEL_PATH.parent / "model_metadata.json"
CSV_OUT = ROOT / "outputs" / "results" / "classification_results.csv"
CM_FIG_OUT = ROOT / "outputs" / "figures" / "confusion_matrix.png"
FI_FIG_OUT = ROOT / "outputs" / "figures" / "feature_importance.png"
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
    X, y = [], []
    counts = {"real":0, "synthetic":0}
    for label in THEMES:
        folder = ROOT / "data" / "labeled_plates" / label
        if folder.is_dir():
            for path in sorted(folder.glob("*")):
                image = cv2.imread(str(path)) if path.is_file() else None
                if image is not None:
                    vector, _ = extract_plate_color_features(image)
                    X.append(vector); y.append(label); counts["real"] += 1
        for _ in range(samples_per_class):
            vector, _ = extract_plate_color_features(generate_synthetic_plate(label,rng))
            X.append(vector); y.append(label); counts["synthetic"] += 1
    if not X:
        raise RuntimeError("Không có dữ liệu huấn luyện.")
    return pd.DataFrame(X,columns=FEATURE_NAMES), np.asarray(y), counts

def main():
    print("1. Tạo dữ liệu và trích xuất 10 đặc trưng HSV...")
    X,y,counts = build_dataset(250)
    print(f"   Ảnh thật: {counts['real']} | ảnh tổng hợp: {counts['synthetic']}")
    X_train,X_test,y_train,y_test = split_train_test(X,y,0.2,42)
    print("2. Huấn luyện RandomForestClassifier...")
    model = train_classification_model(X_train.values,y_train,42)
    pred = model.predict(X_test.values)
    metrics = evaluate_classification(y_test,pred)
    print(f"Accuracy={metrics['accuracy']} | F1-macro={metrics['f1_macro']}")
    print(metrics["report"])
    for path in (MODEL_PATH,CSV_OUT,CM_FIG_OUT,FI_FIG_OUT,META_OUT):
        path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(model,MODEL_PATH)
    pd.DataFrame([{
        "model":"RandomForestClassifier","n_estimators":120,"max_depth":12,
        "train_samples":len(X_train),"test_samples":len(X_test),
        "real_samples":counts["real"],"synthetic_samples":counts["synthetic"],
        "accuracy":metrics["accuracy"],"precision_macro":metrics["precision_macro"],
        "recall_macro":metrics["recall_macro"],"f1_macro":metrics["f1_macro"],
    }]).to_csv(CSV_OUT,index=False)
    labels = metrics["labels"]
    plt.figure(figsize=(6,5))
    sns.heatmap(np.asarray(metrics["confusion_matrix"]),annot=True,fmt="d",cmap="Blues",
                xticklabels=labels,yticklabels=labels)
    plt.title("Confusion Matrix - Random Forest (Plate Color)")
    plt.xlabel("Predicted"); plt.ylabel("Actual"); plt.tight_layout()
    plt.savefig(CM_FIG_OUT,dpi=150); plt.close()
    importance = pd.Series(model.feature_importances_,index=FEATURE_NAMES).sort_values()
    plt.figure(figsize=(7,4.5)); importance.plot(kind="barh")
    plt.title("Feature Importance - Random Forest"); plt.xlabel("Importance")
    plt.tight_layout(); plt.savefig(FI_FIG_OUT,dpi=150); plt.close()
    metadata = {
        "task":"Phân loại màu nền biển số xe (4 nhóm)",
        "algorithm":"RandomForestClassifier","classes":list(model.classes_),
        "class_labels_vi":COLOR_LABELS_VI,"features":FEATURE_NAMES,
        "dataset_source_counts":counts,
        "test_metrics":{k:v for k,v in metrics.items() if k not in ("report","labels")},
        "evaluation_note":"Nếu real_samples bằng 0, chỉ số test phản ánh dữ liệu tổng hợp, không đại diện độ chính xác trên camera thực tế.",
    }
    META_OUT.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Đã lưu mô hình: {MODEL_PATH}")

if __name__ == "__main__":
    main()
