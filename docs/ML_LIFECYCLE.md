# ALPR and plate-color ML workflow

The application currently supports plate localization, OCR, four-class plate-background color prediction, and saving scan results. A successful demo is not by itself a real-world accuracy measurement. The current color model was trained with generated images; its synthetic test score must not be reported as camera performance.

## Collecting labeled color data

Put cropped plate images into the class folder and group images from the same camera session or capture condition under one shared group name:

```text
data/labeled_plates/
  White/camera_a_day_01/*.jpg
  White/camera_a_night_01/*.jpg
  Yellow/camera_a_day_01/*.jpg
  Yellow/camera_a_night_01/*.jpg
  Blue/camera_a_day_01/*.jpg
  Red/camera_a_day_01/*.jpg
```

Use the same group name across color folders for images from the same session. Avoid near-duplicate frames in different groups. Keep each label folder restricted to its named color and manually review ambiguous, covered, overexposed, or non-standard plates before training. Images directly in a class folder are treated as one `ungrouped` capture group, so the real-data holdout will keep that entire group separate.

Train and inspect the generated metadata:

```powershell
python train_plate_color.py
```

The trainer uses generated plates for training augmentation, but when real labeled samples exist it holds out complete capture groups for evaluation. Metadata records sample counts, evaluation source, model SHA-256/version, training configuration and runtime versions. Probability outputs are not calibrated and should not be interpreted as statistically reliable confidence until calibration is evaluated with a separate real validation set.

## Full ALPR benchmark on real images

Create a CSV manifest with one row per real camera image. `image_path` is relative to the manifest or absolute. `plate_true` is required; `color_true` and all four bounding-box columns are optional. Bounding boxes use pixel coordinates `x, y, width, height` in the original image. `group_id` identifies a capture session and `source` must be `real`; the benchmark refuses synthetic samples.

```csv
image_path,plate_true,color_true,source,group_id,bbox_x,bbox_y,bbox_width,bbox_height
images/entry_001.jpg,59B112345,White,real,gate_a_day_01,214,318,206,74
images/entry_002.jpg,51A12345,Yellow,real,gate_b_night_01,92,181,164,59
```

Run inference and save per-image results and aggregate metrics:

```powershell
python -m src.evaluation.alpr_benchmark --manifest data\real_eval\labels.csv --output-dir outputs\alpr_benchmark
```

The summary reports exact normalized plate match rate, character error rate (CER), optional detector box IoU, color-classification metrics, OCR engine counts, average inference latency, capture-group count and model hashes. Keep benchmark images separate from training and tuning. Do not compare scores across runs unless the same fixed manifest and labels are used.

## Database upgrade

For an existing SQL Server database, run `database/migrations/20261118_add_plate_color.sql` once. New databases receive the color fields from `database/init_smartparking_sqlserver.sql`. Existing history rows keep null color fields; new rows store color code, display label and model confidence as separate columns.

## Known validation limits

- The project does not include a real, labeled camera dataset; real-world metrics remain unavailable until one is collected and reviewed.
- The plate detector checkpoint is provided as a model artifact; a reproducible detector training pipeline and source training dataset are not currently part of this repository.
- OCR uses external OCR engines. The benchmark measures the configured inference path but does not train an OCR model.
- Deployable color probabilities are currently uncalibrated. Choose confidence/abstention thresholds only from a separate real validation set and document the expected error trade-off.
