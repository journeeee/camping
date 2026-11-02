from __future__ import annotations

import html
import os
from collections import defaultdict

import httpx

from .models import Slot

WEEKDAY_KO = "월화수목금토일"


def format_message(slots: list[Slot]) -> str:
    """텔레그램 HTML 형식 메시지. 캠핑장별로 묶는다."""
    by_camp: dict[str, list[Slot]] = defaultdict(list)
    for s in slots:
        by_camp[s.camp_name].append(s)
    lines = ["🏕 <b>캠핑 빈자리 발견!</b>"]
    for camp, ss in by_camp.items():
        lines.append("")
        lines.append(f"<b>{html.escape(camp)}</b> ({ss[0].site})")
        for s in sorted(ss, key=lambda x: (x.checkin, x.item_name)):
            d = f"{s.checkin.month}/{s.checkin.day}({WEEKDAY_KO[s.checkin.weekday()]})"
            n = f" {s.nights}박" if s.nights != 1 else ""
            r = f" · 잔여 {s.remaining}" if s.remaining is not None else ""
            lines.append(f"• {d}{n} <a href=\"{html.escape(s.url)}\">{html.escape(s.item_name)}</a>{r}")
    return "\n".join(lines)


def _strip_html(s: str) -> str:
    import re
    s = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"\2 (\1)", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


class Notifier:
    def __init__(self):
        self.tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.tg_chat = os.getenv("TELEGRAM_CHAT_ID")
        self.discord = os.getenv("DISCORD_WEBHOOK_URL")
        self.client = httpx.Client(timeout=15)

    @property
    def configured(self) -> bool:
        return bool((self.tg_token and self.tg_chat) or self.discord)

    @staticmethod
    def _chunks(text: str, limit: int) -> list[str]:
        """줄 단위로 limit 이하 조각으로 나눈다 (텔레그램 4096자, 디스코드 2000자 제한)."""
        out, cur = [], ""
        for line in text.split("\n"):
            if cur and len(cur) + 1 + len(line) > limit:
                out.append(cur)
                cur = line
            else:
                cur = f"{cur}\n{line}" if cur else line
        if cur:
            out.append(cur)
        return out

    def send(self, text_html: str) -> list[str]:
        sent = []
        if self.tg_token and self.tg_chat:
            for chunk in self._chunks(text_html, 3900):
                r = self.client.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", json={
                    "chat_id": self.tg_chat, "text": chunk, "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })
                r.raise_for_status()
            sent.append("telegram")
        if self.discord:
            for chunk in self._chunks(_strip_html(text_html), 1900):
                r = self.client.post(self.discord, json={"content": chunk})
                r.raise_for_status()
            sent.append("discord")
        return sent
