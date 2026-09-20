"""Sinh ảnh biển số giả lập để demo / test (không cần camera)."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATES_DIR = PROJECT_ROOT / "data" / "external" / "plates"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_plate_image(plate_text: str, vehicle_type: str = "Motorbike", path: str | Path | None = None) -> Path:
    """Vẽ biển trắng chữ đen, lưu PNG."""
    PLATES_DIR.mkdir(parents=True, exist_ok=True)
    w, h = (420, 220) if vehicle_type == "Motorbike" else (520, 160)
    img = Image.new("RGB", (w, h), (245, 245, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 6, w - 7, h - 7], outline=(20, 20, 20), width=6)
    font = _font(48 if vehicle_type == "Car" else 40)
    display = plate_text
    bbox = draw.textbbox((0, 0), display, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, (h - th) / 2 - 4), display, fill=(15, 15, 15), font=font)
    out = Path(path) if path else PLATES_DIR / f"{plate_text}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def generate_default_samples() -> list[Path]:
    samples = [
        ("59B112345", "Motorbike"),
        ("51A12345", "Car"),
        ("30F56789", "Car"),
        ("92C198765", "Motorbike"),
    ]
    paths = [render_plate_image(p, v) for p, v in samples]
    paths.append(embed_plate_in_scene(paths[0], PLATES_DIR / "scene_59B112345.jpg"))
    return paths


def embed_plate_in_scene(plate_path: Path, out_path: Path | None = None) -> Path:
    """Dán biển vào ảnh nền lớn, giả lập ảnh camera có chứa biển số."""
    plate = Image.open(plate_path).convert("RGB")
    scene = Image.new("RGB", (960, 640), (42, 48, 56))
    draw = ImageDraw.Draw(scene)
    draw.rectangle([80, 120, 880, 520], fill=(28, 30, 34), outline=(90, 90, 90), width=4)
    draw.rectangle([200, 180, 760, 420], fill=(18, 18, 20))
    pw, ph = plate.size
    scale = 0.55
    plate = plate.resize((int(pw * scale), int(ph * scale)))
    x = (scene.width - plate.width) // 2
    y = 360
    scene.paste(plate, (x, y))
    out = out_path or (PLATES_DIR / f"scene_{plate_path.stem}.jpg")
    scene.save(out, quality=92)
    return out


if __name__ == "__main__":
    paths = generate_default_samples()
    print("Created:")
    for p in paths:
        print(str(p))
