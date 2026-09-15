"""Chia dữ liệu thành tập train/test cho các bài toán khác nhau."""


def split_train_test(df, target_col: str, test_size: float = 0.2, random_state: int = 42):
    """Chia dữ liệu thành tập huấn luyện và kiểm tra.

    Args:
        df: pandas.DataFrame dữ liệu đầu vào.
        target_col: Tên cột mục tiêu.
        test_size: Tỷ lệ tập kiểm tra.
        random_state: Seed ngẫu nhiên.

    Returns:
        Tuple (X_train, X_test, y_train, y_test).
    """
    raise NotImplementedError
