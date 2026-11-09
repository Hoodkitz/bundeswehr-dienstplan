"""Constraint validator."""
from packages.constraints.hard import HARD_CONSTRAINTS
from packages.constraints.soft import SOFT_CONSTRAINTS


class ConstraintValidator:
    def validate(self, roster: dict) -> dict:
        hard_violations = []
        for constraint in HARD_CONSTRAINTS:
            if not constraint(roster.get("shifts", [])):
                hard_violations.append(constraint.__name__)
        soft_scores = {c.__name__: c(roster.get("shifts", [])) for c in SOFT_CONSTRAINTS}
        return {
            "hard_violations": hard_violations,
            "soft_scores": soft_scores,
            "feasible": len(hard_violations) == 0,
        }
