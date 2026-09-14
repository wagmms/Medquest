import pytest
from api.stats import regularized_incomplete_beta

def test_regularized_incomplete_beta_edge_cases():
    # x <= 0
    assert regularized_incomplete_beta(0.0, 2.0, 2.0) == 0.0
    assert regularized_incomplete_beta(-1.0, 2.0, 2.0) == 0.0
    # x >= 1
    assert regularized_incomplete_beta(1.0, 2.0, 2.0) == 1.0
    assert regularized_incomplete_beta(2.0, 2.0, 2.0) == 1.0

def test_regularized_incomplete_beta_invalid_params():
    with pytest.raises(ValueError, match="Parâmetros Beta devem ser positivos"):
        regularized_incomplete_beta(0.5, 0.0, 2.0)
    with pytest.raises(ValueError, match="Parâmetros Beta devem ser positivos"):
        regularized_incomplete_beta(0.5, 2.0, -1.0)

def test_regularized_incomplete_beta_known_values():
    # Beta(1, 1) is Uniform(0, 1), so CDF is x
    assert regularized_incomplete_beta(0.3, 1.0, 1.0) == pytest.approx(0.3, abs=1e-7)
    assert regularized_incomplete_beta(0.7, 1.0, 1.0) == pytest.approx(0.7, abs=1e-7)

    # Beta(a, 1), CDF is x^a
    assert regularized_incomplete_beta(0.5, 2.0, 1.0) == pytest.approx(0.5**2, abs=1e-7)
    assert regularized_incomplete_beta(0.5, 3.0, 1.0) == pytest.approx(0.5**3, abs=1e-7)

    # Beta(1, b), CDF is 1 - (1-x)^b
    assert regularized_incomplete_beta(0.5, 1.0, 2.0) == pytest.approx(1 - 0.5**2, abs=1e-7)
    assert regularized_incomplete_beta(0.5, 1.0, 3.0) == pytest.approx(1 - 0.5**3, abs=1e-7)

    # Symmetry: I_x(a, b) = 1 - I_{1-x}(b, a)
    val1 = regularized_incomplete_beta(0.3, 2.0, 5.0)
    val2 = regularized_incomplete_beta(0.7, 5.0, 2.0)
    assert val1 == pytest.approx(1 - val2, abs=1e-7)

    # x = 0.5, a = b -> CDF is 0.5
    assert regularized_incomplete_beta(0.5, 2.0, 2.0) == pytest.approx(0.5, abs=1e-7)
    assert regularized_incomplete_beta(0.5, 10.0, 10.0) == pytest.approx(0.5, abs=1e-7)

def test_regularized_incomplete_beta_branch_coverage():
    # To test the branch `if x < (a + 1.0) / (a + b + 2.0):` vs else
    # condition: x < (a + 1.0) / (a + b + 2.0)

    # Branch 1 (True):
    # let a = 2, b = 5. (a+1)/(a+b+2) = 3 / 9 = 0.333
    # let x = 0.2
    val_true_branch = regularized_incomplete_beta(0.2, 2.0, 5.0)
    assert 0.0 < val_true_branch < 1.0

    # Branch 2 (False):
    # let x = 0.8
    val_false_branch = regularized_incomplete_beta(0.8, 2.0, 5.0)
    assert 0.0 < val_false_branch < 1.0
