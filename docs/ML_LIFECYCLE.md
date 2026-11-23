# ALPR and plate-color ML workflow

The application currently supports plate localization, OCR, white/yellow civilian plate-background color prediction, and saving scan results. Blue/red plates are outside this project's scope and are rejected when their color is clearly detected. A successful demo is not by itself a real-world accuracy measurement. Synthetic test scores must not be reported as camera performance.

## Collecting labeled color data

Put cropped plate images into the class folder and group images from the same camera session or capture condition under one shared group name:

```text
data/labeled_plates/
  White/camera_a_day_01/*.jpg
  White/camera_a_night_01/*.jpg
  Yellow/camera_a_day_01/*.jpg
  Yellow/camera_a_night_01/*.jpg
```

Only collect white and yellow plates for this project; do not collect or classify blue/red government or military plates. Use the same group name across the white/yellow folders for images from the same session. Avoid near-duplicate frames in different groups. Keep each label folder restricted to its named color and manually review ambiguous, covered, overexposed, or non-standard plates before training. Images directly in a class folder are treated as one `ungrouped` capture group, so the real-data holdout will keep that entire group separate.

Train and compare Random Forest with KNN on the same features and the same train/test split:

```powershell
python train_plate_color.py
```

The trainer uses generated plates for training augmentation, but when real labeled samples exist it holds out complete capture groups for evaluation. Random Forest and KNN use the exact same train and test samples. KNN applies a `StandardScaler` fitted only on the training data before using five distance-weighted neighbors. Accuracy, macro-Precision, macro-Recall, macro-F1 and per-class confusion matrices for both models are saved to `outputs/results/classification_results.csv` and `outputs/results/algorithm_comparison.json`. The report also includes mean maximum-class probability and median/P95 per-crop classifier latency; latency excludes feature extraction, plate detection and OCR. Confidence values are uncalibrated and are descriptive only. The comparison ranks macro-F1 first, then uses accuracy, macro-Precision and macro-Recall to break quality ties. If all four quality metrics tie, it selects a faster model only when its median latency is at least 5% lower; otherwise it reports a tie. Model artifacts are saved as `models/classification/plate_color_model.pkl` (Random Forest) and `models/classification/plate_color_knn_model.pkl` (KNN).

Each training run also performs 10 repeated group holdouts, holding out 20% of plate-identity groups per run, with paired splits for both algorithms. The split seed and Random Forest seed vary per run; all images of the same plate remain in one group. Mean and population standard deviation for accuracy, macro-Precision, macro-Recall, macro-F1 and per-crop latency are written into `outputs/results/algorithm_comparison.json`; individual results are written to `outputs/results/repeated_group_evaluation.csv`. The UI displays the repeated-run averages and standard deviations. Lower macro-F1 standard deviation is reported as lower observed variability, not proof of statistical significance: repeated holdouts use the same source dataset and their test sets can overlap. A separate camera dataset is still required to claim field performance.

The color-classification API continues to return Random Forest in its existing top-level fields and adds a `comparison` object containing the KNN prediction for the same crop. The upload result screen shows both predictions, shared-test metrics, confidence/latency summaries and each classifier's confusion matrix. A single image has no known correct label, so these two predictions alone cannot establish which algorithm performs better. Use the held-out labeled images and comparison report for that conclusion. If the report says `synthetic_only`, it explicitly cannot establish camera performance; collect and manually label real images first. Searching the web for a plate number may help identify an individual vehicle, but it does not provide a reliable ground-truth color label for model evaluation.

Metadata records sample counts, evaluation source, model SHA-256/version, training configuration and runtime versions. Probability outputs are not calibrated and should not be interpreted as statistically reliable confidence until calibration is evaluated with a separate real validation set.

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
