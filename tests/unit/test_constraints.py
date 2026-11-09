"""Tests for constraint validation."""
from packages.constraints.validator import ConstraintValidator


def test_validator_feasible():
    v = ConstraintValidator()
    result = v.validate({"shifts": []})
    assert result["feasible"] is True
    assert result["hard_violations"] == []


def test_hard_constraints_exist():
    from packages.constraints.hard import HARD_CONSTRAINTS
    assert len(HARD_CONSTRAINTS) == 4


def test_soft_constraints_exist():
    from packages.constraints.soft import SOFT_CONSTRAINTS
    assert len(SOFT_CONSTRAINTS) == 3
