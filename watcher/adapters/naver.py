"""네이버 예약 (m.booking.naver.com) 어댑터.

URL 형식:
  https://m.booking.naver.com/booking/{businessTypeId}/bizes/{businessId}
  https://m.booking.naver.com/booking/{businessTypeId}/bizes/{businessId}/items/{bizItemId}

내부 GraphQL (로그인 불필요):
  - bizItems(input:{businessId})                         → 객실/사이트 목록
  - schedule(input:{businessId,businessTypeId,bizItemId,
                    startDateTime,endDateTime}) {
        bizItemSchedule { daily { date } } }           → 날짜별 {isSaleDay,isBusinessDay,stock,bookingCount,...}
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from ..models import Slot, Target
from .base import Adapter

GRAPHQL = "https://m.booking.naver.com/graphql"
URL_RE = re.compile(r"booking/(\d+)/bizes/(\d+)(?:/items/(\d+))?")
PLACE_RE = re.compile(r"(?:place|accommodation|restaurant|hospital|entry/place)/(\d{5,})")

Q_BIZ_ITEMS = """
query bizItems($input: BizItemsParams) {
  bizItems(input: $input) { bizItemId name businessId bizItemType stock price bookingAvailableCode }
}"""

Q_SCHEDULE = """
query schedule($scheduleParams: ScheduleParams) {
  schedule(input: $scheduleParams) { bizItemSchedule { daily { date } } }
}"""


class NaverAdapter(Adapter):
    site = "naver"

    # ---- helpers -------------------------------------------------------
    def parse_url(self, url: str) -> tuple[int, str, str | None]:
        m = URL_RE.search(url)
        if not m and "naver" in url:
            url = self.resolve_place_url(url)
            m = URL_RE.search(url)
        if not m:
            raise ValueError(f"네이버 예약 URL 형식이 아닙니다: {url}")
        return int(m.group(1)), m.group(2), m.group(3)

    def resolve_place_url(self, url: str) -> str:
        """네이버 지도/플레이스 링크(map.naver.com/p/entry/place/ID …)를 예약 URL 로 바꾼다."""
        m = PLACE_RE.search(url)
        if not m:
            return url
        html = self.client.get(f"https://m.place.naver.com/place/{m.group(1)}/home").text
        b = re.search(r'naverBookingUrl":"((?:[^"\\]|\\.)*)"', html)
        if not b:
            raise ValueError(f"이 장소에는 네이버 예약 링크가 없습니다: place {m.group(1)}")
        return json.loads('"' + b.group(1) + '"')

    def _gql(self, op: str, query: str, variables: dict) -> dict:
        r = self.client.post(
            f"{GRAPHQL}?opName={op}",
            json={"operationName": op, "query": query, "variables": variables},
            headers={"Referer": "https://m.booking.naver.com/", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        body = r.json()
        if body.get("errors") and not (body.get("data") or {}).get(op):
            raise RuntimeError(f"네이버 GraphQL 오류({op}): {body['errors'][0].get('message')}")
        return body["data"]

    def business_name(self, type_id: int, business_id: str) -> str | None:
        try:
            html = self.client.get(f"https://m.booking.naver.com/booking/{type_id}/bizes/{business_id}").text
            m = re.search(r'"Business:%s":\{.*?"name":"((?:[^"\\]|\\.)*)"' % business_id, html, re.S)
            if m:
                return json.loads('"' + m.group(1) + '"')
        except Exception:
            pass
        return None

    def list_items(self, target: Target) -> list[dict]:
        _, business_id, item_id = self.parse_url(target.url)
        items = self._gql("bizItems", Q_BIZ_ITEMS, {"input": {"businessId": business_id}})["bizItems"] or []
        if item_id:
            items = [i for i in items if str(i["bizItemId"]) == item_id]
        return [{"id": i["bizItemId"], "name": i["name"], "type": i.get("bizItemType")} for i in items]

    @staticmethod
    def available_slots(daily: dict, dates: list[date], nights: int) -> dict[date, int]:
        """daily: {"YYYY-MM-DD": {...}}. 입실일 → 남은 수량 (nights 연속 모두 가능할 때만)."""
        out: dict[date, int] = {}
        for d in dates:
            remain = None
            ok = True
            for k in range(nights):
                day = daily.get((d + timedelta(days=k)).isoformat())
                if not day or not day.get("isSaleDay") or not day.get("isBusinessDay"):
                    ok = False
                    break
                left = int(day.get("stock") or 0) - int(day.get("bookingCount") or 0)
                if left <= 0:
                    ok = False
                    break
                remain = left if remain is None else min(remain, left)
            if ok and remain:
                out[d] = remain
        return out

    # ---- main ----------------------------------------------------------
    def fetch(self, target: Target) -> list[Slot]:
        if not target.dates:
            return []
        type_id, business_id, item_id = self.parse_url(target.url)
        camp = target.name or self.business_name(type_id, business_id) or f"네이버예약 {business_id}"
        items = self._gql("bizItems", Q_BIZ_ITEMS, {"input": {"businessId": business_id}})["bizItems"] or []
        if item_id:
            items = [i for i in items if str(i["bizItemId"]) == item_id]
        items = [i for i in items if self.match_item(target, i["name"])]

        start = min(target.dates)
        end = max(target.dates) + timedelta(days=target.nights)
        slots: list[Slot] = []
        for item in items:
            data = self._gql("schedule", Q_SCHEDULE, {"scheduleParams": {
                "businessId": business_id,
                "businessTypeId": type_id,
                "bizItemId": str(item["bizItemId"]),
                "startDateTime": f"{start.isoformat()}T00:00:00",
                "endDateTime": f"{end.isoformat()}T23:59:59",
            }})
            daily = (((data.get("schedule") or {}).get("bizItemSchedule") or {}).get("daily") or {}).get("date") or {}
            for d, remain in self.available_slots(daily, target.dates, target.nights).items():
                slots.append(Slot(
                    target_id=target.id, site=self.site, camp_name=camp, item_name=item["name"],
                    checkin=d, nights=target.nights, remaining=remain,
                    url=f"https://m.booking.naver.com/booking/{type_id}/bizes/{business_id}/items/{item['bizItemId']}",
                ))
        return slots
