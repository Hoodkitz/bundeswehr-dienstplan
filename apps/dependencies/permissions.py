"""Permission dependency for FastAPI."""
from fastapi import HTTPException, status


def require_permission(permission: str):
    """Dependency factory that checks if the current user has a permission."""
    def check_permission():
        # In production: check JWT token and user roles
        # For now: allow all (stub)
        return True
    return check_permission
