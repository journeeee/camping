from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class State:
    """마지막 실행에서 '예약 가능'이었던 슬롯 키와 마지막 알림 시각을 기억한다.

    - 새로 빈자리가 생긴 경우(이전 실행에 없던 키)만 알림
    - renotify_after_minutes 가 지나면 계속 비어 있는 자리도 다시 알림
    """

    def __init__(self, path: str | Path = "state.json"):
        self.path = Path(path)
        self.data: dict = {"available": {}, "errors": {}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        self.data.setdefault("available", {})
        self.data.setdefault("errors", {})

    def should_notify(self, key: str, renotify_after_minutes: int | None) -> bool:
        last = self.data["available"].get(key)
        if last is None:
            return True
        if renotify_after_minutes is None:
            return False
        last_dt = datetime.fromisoformat(last)
        age = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        return age >= renotify_after_minutes

    def mark_notified(self, key: str) -> None:
        self.data["available"][key] = datetime.now(timezone.utc).isoformat()

    def keep_only(self, keys: set[str]) -> None:
        """이번 실행에서 더 이상 비어 있지 않은 키는 지운다 (다시 비면 새 알림)."""
        self.data["available"] = {k: v for k, v in self.data["available"].items() if k in keys}

    def record_error(self, target_id: str, msg: str | None) -> bool:
        """오류 상태 기록. 새로 발생한 오류면 True (알림용)."""
        prev = self.data["errors"].get(target_id)
        if msg is None:
            self.data["errors"].pop(target_id, None)
            return False
        self.data["errors"][target_id] = msg
        return prev != msg

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
