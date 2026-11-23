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


def render_plate_image(plate_text: str, layout: str = "two_line", path: str | Path | None = None) -> Path:
    """Vẽ ảnh biển số giả lập; layout chỉ điều khiển kích thước ảnh, không phân loại phương tiện."""
    if layout not in {"one_line", "two_line"}:
        raise ValueError("layout phải là 'one_line' hoặc 'two_line'.")

    PLATES_DIR.mkdir(parents=True, exist_ok=True)
    w, h = (520, 160) if layout == "one_line" else (420, 220)
    img = Image.new("RGB", (w, h), (245, 245, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 6, w - 7, h - 7], outline=(20, 20, 20), width=6)
    font = _font(48 if layout == "one_line" else 40)
    bbox = draw.textbbox((0, 0), plate_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, (h - th) / 2 - 4), plate_text, fill=(15, 15, 15), font=font)
    out = Path(path) if path else PLATES_DIR / f"{plate_text}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def generate_default_samples() -> list[Path]:
    samples = [
        ("59B112345", "two_line"),
        ("51A12345", "one_line"),
        ("30F56789", "one_line"),
        ("92C198765", "two_line"),
    ]
    paths = [render_plate_image(plate, layout) for plate, layout in samples]
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
    plate = plate.resize((int(pw * 0.55), int(ph * 0.55)))
    x = (scene.width - plate.width) // 2
    scene.paste(plate, (x, 360))
    out = out_path or (PLATES_DIR / f"scene_{plate_path.stem}.jpg")
    scene.save(out, quality=92)
    return out


if __name__ == "__main__":
    paths = generate_default_samples()
    print("Created:")
    for path in paths:
        print(str(path))
