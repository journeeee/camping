from __future__ import annotations

import re
from abc import ABC, abstractmethod

import httpx

from ..models import Slot, Target

DEFAULT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class Adapter(ABC):
    """사이트별 어댑터. Target 하나를 받아 현재 예약 가능한 Slot 목록을 돌려준다."""

    site: str = ""

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            headers={"User-Agent": DEFAULT_UA, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        )

    @abstractmethod
    def fetch(self, target: Target) -> list[Slot]:
        """예약 가능한 슬롯만 반환."""

    def list_items(self, target: Target) -> list[dict]:
        """사이트/객실 목록 (설정 작성 보조용). 지원하지 않으면 빈 리스트."""
        return []

    @staticmethod
    def match_item(target: Target, name: str) -> bool:
        if not target.item_filter:
            return True
        return re.search(target.item_filter, name) is not None
