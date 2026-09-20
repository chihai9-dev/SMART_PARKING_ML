"""Làm sạch và tiền xử lý dữ liệu bãi đỗ xe."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vision.plate_ocr import normalize_plate
from src.vision.vehicle_type import canonicalize_vehicle_type


def clean_parking_data(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch dữ liệu thô: thời gian, ngoại lai, biển số, loại xe."""
    out = df.copy()

    if "student_id" in out.columns:
        out = out.dropna(subset=["student_id"])
        out["student_id"] = out["student_id"].astype(str).str.strip()

    for col in ("entry_time", "exit_time"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")

    if {"entry_time", "exit_time"} <= set(out.columns):
        out = out.dropna(subset=["entry_time", "exit_time"])
        inverted = out["exit_time"] < out["entry_time"]
        out = out.loc[~inverted].copy()
        computed = (out["exit_time"] - out["entry_time"]).dt.total_seconds() / 60
        if "duration_minutes" in out.columns:
            out["duration_minutes"] = out["duration_minutes"].fillna(computed)
        else:
            out["duration_minutes"] = computed
        out["duration_minutes"] = out["duration_minutes"].clip(lower=1, upper=7 * 24 * 60)

    if "vehicle_type" in out.columns:
        out["vehicle_type"] = out["vehicle_type"].map(canonicalize_vehicle_type)

    if "license_plate" in out.columns:
        out["license_plate"] = out["license_plate"].map(normalize_plate)
        out = out[out["license_plate"].str.len() > 0]

    out = out.drop_duplicates()
    return out.reset_index(drop=True)
