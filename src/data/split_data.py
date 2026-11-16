"""Chia tập huấn luyện và kiểm thử có phân tầng theo nhãn."""
from sklearn.model_selection import train_test_split


def split_train_test(X, y, test_size: float = 0.2, random_state: int = 42):
    """Chia dữ liệu, giữ tỷ lệ các lớp nhãn tương đương ở train/test."""
    if len(X) != len(y):
        raise ValueError("X và y phải có cùng số lượng mẫu.")
    if len(set(y)) < 2:
        raise ValueError("Cần ít nhất hai lớp để chia dữ liệu phân tầng.")
    return train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
