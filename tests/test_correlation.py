import numpy as np
from unittest.mock import MagicMock
import datetime
from app.services.correlation import compute_correlation_matrix


def make_db_with_prices(symbols, n=50):
    def make_records(symbol):
        rng = np.random.default_rng(42)
        base = datetime.date(2024, 1, 1)
        records = []
        price = 100.0
        for i in range(n):
            ret = rng.normal(0, 0.01)
            price = max(1.0, price * (1 + ret))
            r = MagicMock()
            r.date = base + datetime.timedelta(days=i)
            r.close = price
            records.append(r)
        return records

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        def filter_side_effect(**kwargs):
            sym = list(kwargs.values())[0]
            f = MagicMock()
            f.order_by.return_value.all.return_value = make_records(sym)
            return f
        q.filter_by.side_effect = filter_side_effect
        return q

    db.query.side_effect = query_side_effect
    return db


def test_correlation_returns_dict():
    db = make_db_with_prices(["AAPL", "MSFT"])
    result = compute_correlation_matrix(db, ["AAPL", "MSFT"])
    assert isinstance(result, dict)


def test_correlation_has_required_keys():
    db = make_db_with_prices(["AAPL", "MSFT"])
    result = compute_correlation_matrix(db, ["AAPL", "MSFT"])
    assert "symbols" in result
    assert "matrix" in result


def test_correlation_diagonal_is_one():
    db = make_db_with_prices(["AAPL", "MSFT"])
    result = compute_correlation_matrix(db, ["AAPL", "MSFT"])
    matrix = result["matrix"]
    for i in range(len(matrix)):
        assert abs(matrix[i][i] - 1.0) < 0.01


def test_correlation_matrix_shape():
    db = make_db_with_prices(["AAPL", "MSFT", "TSLA"])
    result = compute_correlation_matrix(db, ["AAPL", "MSFT", "TSLA"])
    n = len(result["symbols"])
    assert len(result["matrix"]) == n
    for row in result["matrix"]:
        assert len(row) == n


def test_correlation_empty_symbols():
    db = MagicMock()
    result = compute_correlation_matrix(db, [])
    assert result == {"symbols": [], "matrix": []}


def test_correlation_values_between_minus_one_and_one():
    db = make_db_with_prices(["AAPL", "MSFT"])
    result = compute_correlation_matrix(db, ["AAPL", "MSFT"])
    for row in result["matrix"]:
        for val in row:
            assert -1.0 <= val <= 1.0
