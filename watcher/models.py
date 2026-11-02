from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Slot:
    """특정 캠핑장의 특정 사이트(객실)가 특정 입실일에 예약 가능함을 나타낸다."""

    target_id: str      # watch.yaml 의 target id
    site: str           # naver | thankq | generic
    camp_name: str      # 캠핑장 이름
    item_name: str      # 사이트/객실 이름 (예: "사이트 A", "A동1호")
    checkin: date
    nights: int
    remaining: int | None   # 남은 수량 (알 수 없으면 None)
    url: str                # 바로 예약하러 갈 링크

    @property
    def key(self) -> str:
        return f"{self.target_id}|{self.item_name}|{self.checkin.isoformat()}|{self.nights}"


@dataclass
class Target:
    id: str
    site: str
    url: str
    name: str | None = None
    dates: list[date] = field(default_factory=list)
    nights: int = 1
    item_filter: str | None = None      # 사이트/객실 이름 정규식 (없으면 전체)
    extra: dict = field(default_factory=dict)   # 어댑터별 추가 옵션
