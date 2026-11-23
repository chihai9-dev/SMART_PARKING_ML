# Labeled plate-color images

The `White` and `Yellow` folders contain plate crops from the Roboflow
Universe dataset `license-plate-color`, version 4:

- Dataset: https://universe.roboflow.com/nguyenluanai/license-plate-color
- Dataset license shown in the export: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Attribution: nguyenluanAI / Roboflow Universe
- Exported: 2024-02-09

Only images labeled `bien_trang` (White) and `bien_vang` (Yellow) were
included. Images labeled `bien_xanh` or `bien_unknown` were excluded. Images
are grouped by a stable hash of the plate identifier in the source filename,
so repeated images of the same plate stay together during evaluation. Each
filename is prefixed with its original `train`, `valid`, or `test` split. The
YOLO annotation files are not included; the model trainer uses the class
folders as color labels.

Included: 1,073 original train images, 299 validation images, and 130 test
images. Train RF and KNN with `python train_plate_color.py`.

The export identifies Roboflow as the provider but does not identify the
original photographers or image-level provenance. Retain this attribution and
review the upstream dataset terms before redistributing these images.
