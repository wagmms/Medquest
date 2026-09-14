import pytest
import math

from api.stats import regularized_incomplete_beta

def test_regularized_incomplete_beta_edge_cases():
    # x <= 0.0
    assert regularized_incomplete_beta(0.0, 1.0, 1.0) == 0.0
    assert regularized_incomplete_beta(-1.0, 1.0, 1.0) == 0.0

    # x >= 1.0
    assert regularized_incomplete_beta(1.0, 1.0, 1.0) == 1.0
    assert regularized_incomplete_beta(2.0, 1.0, 1.0) == 1.0

def test_regularized_incomplete_beta_invalid_params():
    # a <= 0.0 or b <= 0.0
    with pytest.raises(ValueError):
        regularized_incomplete_beta(0.5, 0.0, 1.0)
    with pytest.raises(ValueError):
        regularized_incomplete_beta(0.5, 1.0, 0.0)
    with pytest.raises(ValueError):
        regularized_incomplete_beta(0.5, -1.0, 1.0)

def test_regularized_incomplete_beta_known_values():
    # Beta(1, 1) is a uniform distribution, so CDF is x
    assert math.isclose(regularized_incomplete_beta(0.5, 1.0, 1.0), 0.5, abs_tol=1e-7)
    assert math.isclose(regularized_incomplete_beta(0.25, 1.0, 1.0), 0.25, abs_tol=1e-7)

    # Beta(a, b) at x=0.5 where a=b is exactly 0.5 because it's symmetric
    assert math.isclose(regularized_incomplete_beta(0.5, 2.0, 2.0), 0.5, abs_tol=1e-7)
    assert math.isclose(regularized_incomplete_beta(0.5, 5.0, 5.0), 0.5, abs_tol=1e-7)

    # Check a specific known value
    # Beta(2, 2) CDF is x^2 * (3 - 2x)
    # For x = 0.25: 0.25^2 * (3 - 0.5) = 0.0625 * 2.5 = 0.15625
    assert math.isclose(regularized_incomplete_beta(0.25, 2.0, 2.0), 0.15625, abs_tol=1e-7)
