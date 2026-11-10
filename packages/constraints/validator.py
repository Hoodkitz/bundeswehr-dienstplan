"""Constraint validator with detailed violation reporting."""
from packages.constraints.hard import HARD_CONSTRAINTS, ConstraintViolation
from packages.constraints.soft import SOFT_CONSTRAINTS


class ConstraintValidator:
    def __init__(self):
        self.hard = HARD_CONSTRAINTS
        self.soft = SOFT_CONSTRAINTS

    def validate(self, roster: dict) -> dict:
        shifts = roster.get("shifts", [])
        hard_violations = []
        for constraint in self.hard:
            try:
                if not constraint(shifts):
                    hard_violations.append({
                        "constraint": constraint.__name__,
                        "severity": "HARD",
                        "message": f"Violation of {constraint.__name__}",
                    })
            except Exception as e:
                hard_violations.append({
                    "constraint": constraint.__name__,
                    "severity": "ERROR",
                    "message": str(e),
                })
        soft_scores = {}
        for c in self.soft:
            try:
                soft_scores[c.__name__] = c(shifts)
            except Exception:
                soft_scores[c.__name__] = 0.0
        return {
            "hard_violations": hard_violations,
            "soft_scores": soft_scores,
            "feasible": len(hard_violations) == 0,
            "total_shifts": len(shifts),
        }

    def validate_shift(self, shift: dict, existing_shifts: list) -> bool:
        """Validate a single shift against existing roster."""
        all_shifts = existing_shifts + [shift]
        result = self.validate({"shifts": all_shifts})
        return result["feasible"]
