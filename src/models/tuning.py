"""Tinh chỉnh siêu tham số (hyperparameter tuning) cho các mô hình."""


def tune_model(model, param_grid, X_train, y_train, cv: int = 5):
    """Tìm siêu tham số tốt nhất cho mô hình bằng GridSearch/RandomizedSearch.

    Returns:
        Mô hình tốt nhất sau khi tinh chỉnh.
    """
    raise NotImplementedError
