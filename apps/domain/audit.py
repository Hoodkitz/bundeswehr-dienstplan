"""Append-only Audit-Log mit Hash-Kette (OPS.1.1.5, § 10 SG Dienstaufsicht)."""
import hashlib
import json
from datetime import datetime

GENESIS = "0" * 64


def entry_hash(prev_hash: str, seq: int, action: str, actor: str, payload: dict, ts: datetime) -> str:
    body = json.dumps(
        {"prev": prev_hash, "seq": seq, "action": action, "actor": actor, "payload": payload,
         "ts": ts.replace(microsecond=0).isoformat()},
        sort_keys=True, default=str, ensure_ascii=False,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def verify_chain(entries: list[dict]) -> tuple[bool, int | None]:
    """entries: sortiert nach seq. Rueckgabe (ok, erste_kaputte_seq)."""
    prev = GENESIS
    for e in entries:
        expected = entry_hash(prev, e["seq"], e["action"], e["actor"], e["payload"], e["ts"])
        if e["prev_hash"] != prev or e["hash"] != expected:
            return False, e["seq"]
        prev = e["hash"]
    return True, None
