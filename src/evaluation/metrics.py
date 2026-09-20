"""Các hàm đánh giá hiệu năng mô hình."""


def evaluate_classification(y_true, y_pred):
    """Tính các chỉ số đánh giá cho bài toán phân loại (accuracy, precision, recall, f1)."""
    raise NotImplementedError


def evaluate_regression(y_true, y_pred):
    """Tính các chỉ số đánh giá cho bài toán hồi quy (MAE, RMSE, R2)."""
    raise NotImplementedError
