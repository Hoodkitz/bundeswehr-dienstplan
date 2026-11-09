"""Append-only audit log."""
import hashlib
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4


class AuditEntry:
    def __init__(self, tenant_id: UUID, actor_id: UUID, action: str, object_type: str, object_id: UUID, payload: dict):
        self.id = uuid4()
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.action = action
        self.object_type = object_type
        self.object_id = object_id
        self.payload = payload
        self.created_at = datetime.utcnow()
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = f"{self.tenant_id}{self.actor_id}{self.action}{self.object_type}{self.object_id}{self.created_at}"
        return hashlib.sha256(data.encode()).hexdigest()
