"""땡큐캠핑 (m.thankqcamping.com) 어댑터.

URL 형식: https://m.thankqcamping.com/resv/view.hbb?cseq={캠핑장번호}
          (www. 도 m. 으로 리다이렉트됨)

내부 엔드포인트 (로그인 불필요):
  POST /resv/axResCampSite.hbb
       campseq, res_dt=YYYYMMDD, res_edt=YYYYMMDD, res_days, site_tp='', only_able_yn=''
  → 사이트별 HTML 조각. <span class="q_tip og">예약가능 <em>N</em></span> 이면 가능,
    <span class="q_tip">예약완료</span> 이면 마감.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from ..models import Slot, Target
from .base import Adapter

BASE = "https://m.thankqcamping.com"
CSEQ_RE = re.compile(r"[?&]cseq=(\d+)")


def parse_site_list(html: str) -> list[dict]:
    """axResCampSite 응답에서 사이트 목록을 뽑는다.
    각 항목: {"name", "available": bool, "remaining": int|None, "price": str|None, "siteseq": str|None}
    """
    out = []
    for blk in re.split(r'(?=<div class="site_div)', html)[1:]:
        name = re.search(r'<p class="na">(.*?)</p>', blk, re.S)
        if not name:
            continue  # 이름 없는 보조 블록은 건너뜀
        tip = re.search(r'<span class="q_tip([^"]*)">(.*?)</span>', blk, re.S)
        tip_cls = tip.group(1) if tip else ""
        tip_txt = re.sub(r"<[^>]+>|\s+", " ", tip.group(2)).strip() if tip else ""
        em = re.search(r"<em>\s*(\d+)\s*</em>", tip.group(2)) if tip else None
        price = re.search(r'<p class="pri">(.*?)</p>', blk, re.S)
        seq = re.search(r"\(\s*'(\d+)'", blk[:300])
        out.append({
            "name": re.sub(r"\s+", " ", name.group(1)).strip(),
            "available": "og" in tip_cls.split() or "예약가능" in tip_txt,
            "remaining": int(em.group(1)) if em else None,
            "price": price.group(1).strip() if price else None,
            "siteseq": seq.group(1) if seq else None,
            "status": tip_txt,
        })
    return out


class ThankQAdapter(Adapter):
    site = "thankq"

    @staticmethod
    def parse_url(url: str) -> str:
        m = CSEQ_RE.search(url)
        if not m:
            raise ValueError(f"땡큐캠핑 URL 에 cseq= 가 없습니다: {url}")
        return m.group(1)

    def camp_info(self, cseq: str) -> dict:
        """캠핑장 페이지에서 이름과 예약 가능 기간(res_able_max_dt)을 읽는다.

        땡큐캠핑은 아직 예약 오픈 전인 날짜도 사이트 목록에 '예약가능'으로 표시하므로
        res_able_max_dt(예약 가능한 마지막 입실일) 이후는 빈자리로 치지 않는다.
        """
        info: dict = {"name": None, "able_max": None, "next_open": None}
        try:
            html = self.client.get(f"{BASE}/resv/view.hbb", params={"cseq": cseq}).text
        except Exception:
            return info
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            parts = [p.strip() for p in m.group(1).split("|")]
            if len(parts) >= 2:
                info["name"] = parts[1]
        for key, out in (("res_able_max_dt", "able_max"), ("next_open_stime", "next_open")):
            m = re.search(r'name="%s"\s+value="(\d{8})' % key, html)
            if m:
                v = m.group(1)
                info[out] = date(int(v[:4]), int(v[4:6]), int(v[6:8]))
        return info

    def site_list(self, cseq: str, checkin: date, nights: int) -> list[dict]:
        r = self.client.post(f"{BASE}/resv/axResCampSite.hbb", data={
            "campseq": cseq,
            "res_dt": checkin.strftime("%Y%m%d"),
            "res_edt": (checkin + timedelta(days=nights)).strftime("%Y%m%d"),
            "res_days": str(nights),
            "site_tp": "",
            "only_able_yn": "",
        }, headers={"Referer": f"{BASE}/resv/view.hbb?cseq={cseq}", "X-Requested-With": "XMLHttpRequest"})
        r.raise_for_status()
        return parse_site_list(r.text)

    def list_items(self, target: Target) -> list[dict]:
        cseq = self.parse_url(target.url)
        info = self.camp_info(cseq)
        d = target.dates[0] if target.dates else date.today() + timedelta(days=7)
        items = [{"id": s["siteseq"], "name": s["name"], "status": s["status"], "price": s["price"]}
                 for s in self.site_list(cseq, d, target.nights)]
        if info["able_max"]:
            items.insert(0, {"info": f"{info['name']} · 예약 가능 입실일 ≤ {info['able_max']} · 다음 오픈 {info['next_open']}"})
        return items

    def fetch(self, target: Target) -> list[Slot]:
        if not target.dates:
            return []
        cseq = self.parse_url(target.url)
        info = self.camp_info(cseq)
        camp = target.name or info["name"] or f"땡큐캠핑 {cseq}"
        dates = target.dates
        if info["able_max"]:
            skipped = [d for d in dates if d > info["able_max"]]
            if skipped:
                print(f"[{target.id}] 예약 오픈 전 날짜 {len(skipped)}개 제외 (오픈된 마지막 입실일 {info['able_max']})")
            dates = [d for d in dates if d <= info["able_max"]]
        slots: list[Slot] = []
        for d in dates:
            for s in self.site_list(cseq, d, target.nights):
                if not s["available"] or not self.match_item(target, s["name"]):
                    continue
                slots.append(Slot(
                    target_id=target.id, site=self.site, camp_name=camp, item_name=s["name"],
                    checkin=d, nights=target.nights, remaining=s["remaining"],
                    url=f"{BASE}/resv/view.hbb?cseq={cseq}&res_dt={d.strftime('%Y%m%d')}",
                ))
        return slots
