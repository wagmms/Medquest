import pytest
from api.stats import beta_quantile, regularized_incomplete_beta

def test_beta_quantile_edge_cases():
    assert beta_quantile(0.0, 2.0, 2.0) == 0.0
    assert beta_quantile(-0.1, 2.0, 2.0) == 0.0
    assert beta_quantile(1.0, 2.0, 2.0) == 1.0
    assert beta_quantile(1.1, 2.0, 2.0) == 1.0

def test_beta_quantile_symmetry():
    # For a symmetric beta distribution (a=b), the 0.5 quantile should be 0.5
    assert pytest.approx(beta_quantile(0.5, 2.0, 2.0), abs=1e-5) == 0.5
    assert pytest.approx(beta_quantile(0.5, 5.0, 5.0), abs=1e-5) == 0.5

def test_beta_quantile_recovery():
    # If we find the quantile q for probability p, then CDF(q) should be close to p
    a, b = 2.0, 5.0
    for p in [0.1, 0.25, 0.5, 0.75, 0.9]:
        q = beta_quantile(p, a, b)
        assert pytest.approx(regularized_incomplete_beta(q, a, b), abs=1e-5) == p

def test_beta_quantile_known_values():
    # Beta(1, 1) is uniform(0,1), so quantile(p) = p
    assert pytest.approx(beta_quantile(0.2, 1.0, 1.0), abs=1e-5) == 0.2
    assert pytest.approx(beta_quantile(0.8, 1.0, 1.0), abs=1e-5) == 0.8
