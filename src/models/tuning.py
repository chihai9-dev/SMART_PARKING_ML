"""Tinh chỉnh siêu tham số (hyperparameter tuning) cho các mô hình."""

from __future__ import annotations

from typing import Any

from sklearn.base import BaseEstimator
from sklearn.model_selection import GridSearchCV


def tune_model(
    model: BaseEstimator,
    param_grid: dict[str, list[Any]],
    X_train,
    y_train,
    cv=5,
    scoring: str | None = None,
    n_jobs: int | None = -1,
    groups=None,
) -> BaseEstimator:
    """Return the best grid-search estimator.

    Pass capture-session ``groups`` together with a group-aware ``cv`` splitter
    when samples share a session. An integer ``cv`` uses default stratified folds.
    """
    if not param_grid:
        raise ValueError("param_grid must contain at least one parameter.")
    if isinstance(cv, int) and cv < 2:
        raise ValueError("cv must be at least 2.")

    search = GridSearchCV(
        estimator=model,
        param_grid=param_grid,
        cv=cv,
        scoring=scoring,
        n_jobs=n_jobs,
        error_score="raise",
        refit=True,
    )
    if groups is None:
        search.fit(X_train, y_train)
    else:
        search.fit(X_train, y_train, groups=groups)
    return search.best_estimator_
