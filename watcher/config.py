from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from .models import Target

KST = timezone(timedelta(hours=9))  # 한국은 서머타임 없음
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
            "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}


def today_kst() -> date:
    return datetime.now(KST).date()


def _parse_date(v) -> date:
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if re.fullmatch(r"\d{8}", s):
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return date.fromisoformat(s)


def expand_dates(spec: dict, today: date | None = None) -> list[date]:
    """target 설정의 dates / date_range 를 실제 날짜 목록으로 펼친다. 지난 날짜는 제외."""
    today = today or today_kst()
    out: set[date] = set()
    for v in spec.get("dates") or []:
        out.add(_parse_date(v))
    rng = spec.get("date_range")
    if rng:
        start = _parse_date(rng.get("from") or today)
        if "to" in rng:
            end = _parse_date(rng["to"])
        else:
            end = start + timedelta(days=int(rng.get("days", 60)))
        wds = rng.get("weekdays")
        allowed = None
        if wds:
            allowed = {WEEKDAYS[str(w).lower()[:3]] if str(w).lower()[:3] in WEEKDAYS else WEEKDAYS[str(w)] for w in wds}
        d = start
        while d <= end:
            if allowed is None or d.weekday() in allowed:
                out.add(d)
            d += timedelta(days=1)
    return sorted(d for d in out if d >= today)


def load_targets(path: str | Path = "watch.yaml") -> tuple[dict, list[Target]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    settings = raw.get("settings") or {}
    targets: list[Target] = []
    for i, t in enumerate(raw.get("targets") or []):
        if t.get("enabled", True) is False:
            continue
        known = {"id", "site", "url", "name", "dates", "date_range", "nights", "item_filter", "enabled"}
        targets.append(Target(
            id=str(t.get("id") or f"target{i+1}"),
            site=str(t["site"]).lower(),
            url=str(t["url"]),
            name=t.get("name"),
            dates=expand_dates(t),
            nights=int(t.get("nights", 1)),
            item_filter=t.get("item_filter"),
            extra={k: v for k, v in t.items() if k not in known},
        ))
    return settings, targets
