r"""범용 HTTP 어댑터: 전용 어댑터가 없는 사이트를 정규식으로 감시한다.

watch.yaml 예:
  - id: some-camp
    site: generic
    url: https://example.com/reserve?date={date}      # {date}=YYYY-MM-DD, {date8}=YYYYMMDD
    method: GET                                        # 또는 POST
    data: {foo: bar, dt: "{date8}"}                    # POST 폼 데이터 (선택)
    available_regex: '예약가능|잔여\s*[1-9]'          # 이게 매칭되면 '빈자리'
    unavailable_regex: '예약마감'                      # 선택: 이게 매칭되면 무조건 마감
    dates: [...]
"""
from __future__ import annotations

import re

from ..models import Slot, Target
from .base import Adapter


class GenericAdapter(Adapter):
    site = "generic"

    def fetch(self, target: Target) -> list[Slot]:
        avail_re = target.extra.get("available_regex")
        if not avail_re:
            raise ValueError(f"[{target.id}] generic 어댑터는 available_regex 가 필요합니다")
        unavail_re = target.extra.get("unavailable_regex")
        method = str(target.extra.get("method", "GET")).upper()
        slots: list[Slot] = []
        for d in target.dates:
            fmt = {"date": d.isoformat(), "date8": d.strftime("%Y%m%d")}
            url = target.url.format(**fmt)
            data = {k: str(v).format(**fmt) for k, v in (target.extra.get("data") or {}).items()}
            r = self.client.request(method, url, data=data if method == "POST" else None,
                                    params=data if method == "GET" and data else None)
            r.raise_for_status()
            text = r.text
            if unavail_re and re.search(unavail_re, text):
                continue
            m = re.search(avail_re, text)
            if m:
                remain = None
                num = re.search(r"\d+", m.group(0))
                if num:
                    remain = int(num.group(0))
                slots.append(Slot(
                    target_id=target.id, site=self.site, camp_name=target.name or target.id,
                    item_name=target.extra.get("item_name", "빈자리"), checkin=d, nights=target.nights,
                    remaining=remain, url=url,
                ))
        return slots
