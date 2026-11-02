import json
from datetime import date
from pathlib import Path

from watcher.adapters.naver import NaverAdapter
from watcher.adapters.thankq import ThankQAdapter, parse_site_list
from watcher.config import expand_dates
from watcher.models import Slot
from watcher.notify import format_message
from watcher.state import State

FIX = Path(__file__).parent / "fixtures"


def test_thankq_parse_site_list():
    sites = parse_site_list((FIX / "thankq_sites.html").read_text(encoding="utf-8"))
    names = [s["name"] for s in sites]
    assert names == ["사이트 A", "사이트 B", "카라반 B", "카라반 C"]
    a = sites[0]
    assert a["available"] is True and a["remaining"] == 2 and a["siteseq"] == "113092"
    assert all(s["available"] is False for s in sites[1:])


def test_thankq_url():
    assert ThankQAdapter.parse_url("https://m.thankqcamping.com/resv/view.hbb?cseq=1&res_dt=20261107") == "1"


def test_naver_url():
    a = NaverAdapter()
    assert a.parse_url("https://m.booking.naver.com/booking/3/bizes/186791") == (3, "186791", None)
    assert a.parse_url("https://booking.naver.com/booking/10/bizes/5/items/77?x=1") == (10, "5", "77")


def test_naver_place_url_resolution(monkeypatch):
    a = NaverAdapter()
    monkeypatch.setattr(a, "resolve_place_url", lambda u: "https://m.booking.naver.com/booking/3/bizes/627922")
    assert a.parse_url("https://map.naver.com/p/entry/place/1995246261?lng=1") == (3, "627922", None)


def test_naver_available_slots_single_and_multi_night():
    daily = json.loads((FIX / "naver_daily.json").read_text(encoding="utf-8"))
    dates = [date(2026, 11, 13), date(2026, 11, 14), date(2026, 11, 15), date(2026, 11, 16)]
    one = NaverAdapter.available_slots(daily, dates, 1)
    assert one == {date(2026, 11, 13): 2, date(2026, 11, 15): 3}
    two = NaverAdapter.available_slots(daily, dates, 2)
    assert two == {}  # 13→14 는 14일 만석, 15→16 은 16일 휴무


def test_expand_dates_range_weekdays_and_past_filter():
    today = date(2026, 11, 2)
    ds = expand_dates({"dates": ["2026-10-31", "20261107"],
                       "date_range": {"from": "2026-11-01", "to": "2026-11-15", "weekdays": ["fri", "토"]}}, today)
    assert date(2026, 10, 31) not in ds
    assert ds == [date(2026, 11, 6), date(2026, 11, 7), date(2026, 11, 13), date(2026, 11, 14)]


def test_state_notify_once_then_renotify(tmp_path):
    st = State(tmp_path / "s.json")
    assert st.should_notify("k", None)
    st.mark_notified("k")
    assert not st.should_notify("k", None)
    assert not st.should_notify("k", 60)
    assert st.should_notify("k", 0)
    st.keep_only(set())
    assert st.should_notify("k", None)


def test_format_message():
    s = Slot("t", "thankq", "자라섬캠핑장", "사이트 A", date(2026, 11, 7), 1, 2, "https://x/y")
    msg = format_message([s])
    assert "자라섬캠핑장" in msg and "11/7(토)" in msg and "잔여 2" in msg and 'href="https://x/y"' in msg
