import pytest
import math

from api.stats import regularized_incomplete_beta

def test_regularized_incomplete_beta_edge_cases():
    # x <= 0
    assert regularized_incomplete_beta(0.0, 1.0, 1.0) == 0.0
    assert regularized_incomplete_beta(-1.0, 1.0, 1.0) == 0.0

    # x >= 1
    assert regularized_incomplete_beta(1.0, 1.0, 1.0) == 1.0
    assert regularized_incomplete_beta(2.0, 1.0, 1.0) == 1.0

def test_regularized_incomplete_beta_invalid_params():
    with pytest.raises(ValueError, match="Parâmetros Beta devem ser positivos"):
        regularized_incomplete_beta(0.5, 0.0, 1.0)

    with pytest.raises(ValueError, match="Parâmetros Beta devem ser positivos"):
        regularized_incomplete_beta(0.5, 1.0, 0.0)

    with pytest.raises(ValueError, match="Parâmetros Beta devem ser positivos"):
        regularized_incomplete_beta(0.5, -1.0, 1.0)

def test_regularized_incomplete_beta_uniform():
    # Beta(1, 1) is Uniform(0, 1)
    # CDF of Uniform(0, 1) is just x
    assert math.isclose(regularized_incomplete_beta(0.1, 1.0, 1.0), 0.1, rel_tol=1e-5)
    assert math.isclose(regularized_incomplete_beta(0.5, 1.0, 1.0), 0.5, rel_tol=1e-5)
    assert math.isclose(regularized_incomplete_beta(0.9, 1.0, 1.0), 0.9, rel_tol=1e-5)

def test_regularized_incomplete_beta_first_branch():
    # Condition: x < (a + 1.0) / (a + b + 2.0)
    a = 2.0
    b = 5.0
    # Threshold = (2 + 1) / (2 + 5 + 2) = 3 / 9 = 0.333
    x = 0.1 # Takes first branch

    # We can test against a known approximation or just check it doesn't crash
    # For Beta(2, 5), PDF = x * (1-x)^4 / B(2, 5). B(2, 5) = 1/30
    # CDF(x) = 30 * int_0^x t(1-t)^4 dt = 30 * int_0^x (t - 4t^2 + 6t^3 - 4t^4 + t^5) dt
    # CDF(x) = 30 * (x^2/2 - 4x^3/3 + 6x^4/4 - 4x^5/5 + x^6/6)

    def cdf_beta_2_5(val):
        return 30 * (val**2 / 2 - 4 * val**3 / 3 + 1.5 * val**4 - 0.8 * val**5 + val**6 / 6)

    expected = cdf_beta_2_5(x)
    actual = regularized_incomplete_beta(x, a, b)
    assert math.isclose(actual, expected, rel_tol=1e-5)

def test_regularized_incomplete_beta_second_branch():
    # Condition: x >= (a + 1.0) / (a + b + 2.0)
    a = 2.0
    b = 5.0
    # Threshold = 0.333...
    x = 0.9 # Takes second branch

    def cdf_beta_2_5(val):
        return 30 * (val**2 / 2 - 4 * val**3 / 3 + 1.5 * val**4 - 0.8 * val**5 + val**6 / 6)

    expected = cdf_beta_2_5(x)
    actual = regularized_incomplete_beta(x, a, b)
    assert math.isclose(actual, expected, rel_tol=1e-5)
