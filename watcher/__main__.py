"""CLI.

  python -m watcher run                 # 감시 1회 실행 (크론에서 호출)
  python -m watcher run --dry-run       # 알림 보내지 않고 결과만 출력
  python -m watcher run --loop 120      # 2분 간격으로 계속 조회 (기본 최대 330분)
  python -m watcher list <target-id>    # 해당 target 의 사이트/객실 목록 출력 (item_filter 작성용)
  python -m watcher test-notify         # 알림 채널 설정 확인용 테스트 메시지
  python -m watcher setup-telegram 봇토큰   # chat id 자동 탐지 → .env 저장 → 테스트 메시지
"""
from __future__ import annotations

import argparse
import functools
import os
import sys

print = functools.partial(print, flush=True)  # noqa: A001  CI 로그 실시간 출력
import traceback

from .adapters import get_adapter
from .env import load_env, save_env
from .config import load_targets
from .models import Slot
from .notify import Notifier, format_message
from .state import State


def cmd_run(args) -> int:
    if not args.loop:
        return run_once(args)
    import time
    from datetime import datetime
    deadline = time.monotonic() + args.max_minutes * 60
    n = 0
    while True:
        n += 1
        print(f"\n===== {datetime.now().strftime('%H:%M:%S')} 조회 #{n} (간격 {args.loop}s, 최대 {args.max_minutes}분)", flush=True)
        try:
            run_once(args)
        except Exception as e:  # 설정 오류 등 치명적 문제만 여기로 옴
            print(f"실행 오류: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        if time.monotonic() + args.loop > deadline:
            print("최대 실행 시간 도달, 종료", flush=True)
            return 0
        time.sleep(args.loop)


def run_once(args) -> int:
    settings, targets = load_targets(args.config)
    state = State(args.state)
    notifier = Notifier()
    renotify = settings.get("renotify_after_minutes")
    found: list[Slot] = []
    errors: list[str] = []

    for t in targets:
        if not t.dates:
            print(f"[{t.id}] 감시할 날짜가 없음 (모두 지난 날짜?) - 건너뜀")
            continue
        try:
            slots = get_adapter(t.site).fetch(t)
            print(f"[{t.id}] {t.site} 날짜 {len(t.dates)}개 조회 → 빈자리 {len(slots)}개")
            for s in slots:
                print(f"    {s.checkin} {s.item_name} 잔여={s.remaining}")
            found.extend(slots)
            state.record_error(t.id, None)
        except Exception as e:  # 한 사이트 실패가 전체를 막지 않도록
            msg = f"{type(e).__name__}: {e}"
            print(f"[{t.id}] 오류: {msg}", file=sys.stderr)
            if args.verbose:
                traceback.print_exc()
            if state.record_error(t.id, msg):
                errors.append(f"[{t.id}] {msg}")

    new = [s for s in found if state.should_notify(s.key, renotify)]
    state.keep_only({s.key for s in found})

    if new:
        msg = format_message(new)
        print("\n" + msg)
        if args.dry_run:
            print("(dry-run: 알림 미전송)")
        elif notifier.configured:
            print("알림 전송:", notifier.send(msg))
            for s in new:
                state.mark_notified(s.key)
        else:
            print("알림 채널이 설정되지 않음 (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 또는 DISCORD_WEBHOOK_URL)")
    else:
        print("\n새로운 빈자리 없음")

    if errors and settings.get("notify_errors", True) and notifier.configured and not args.dry_run:
        notifier.send("⚠️ <b>감시 오류</b>\n" + "\n".join(errors))

    if not args.dry_run:
        state.save()
    return 0


def cmd_list(args) -> int:
    _, targets = load_targets(args.config)
    for t in targets:
        if args.target_id and t.id != args.target_id:
            continue
        print(f"== [{t.id}] {t.site} {t.url}")
        try:
            for it in get_adapter(t.site).list_items(t):
                print("   ", it)
        except Exception as e:
            print("    오류:", e)
    return 0


def cmd_test_notify(args) -> int:
    n = Notifier()
    if not n.configured:
        print("알림 채널 환경변수가 없습니다.")
        return 1
    print("전송:", n.send("✅ 캠핑 빈자리 감시 알림 테스트"))
    return 0


def cmd_setup_telegram(args) -> int:
    import httpx
    token = args.token.strip()
    api = f"https://api.telegram.org/bot{token}"
    me = httpx.get(f"{api}/getMe", timeout=15).json()
    if not me.get("ok"):
        print("토큰이 올바르지 않습니다:", me.get("description"))
        return 1
    bot = me["result"]["username"]
    print(f"봇 확인: @{bot}")
    chats: dict[str, str] = {}
    for u in httpx.get(f"{api}/getUpdates", timeout=15).json().get("result", []):
        m = u.get("message") or u.get("my_chat_member", {}).get("chat") and {"chat": u["my_chat_member"]["chat"]}
        if not m:
            continue
        c = m["chat"]
        chats[str(c["id"])] = c.get("title") or " ".join(x for x in (c.get("first_name"), c.get("last_name")) if x) or c.get("username", "")
    if not chats:
        print(f"아직 봇에게 온 메시지가 없습니다. 텔레그램에서 https://t.me/{bot} 을 열어 '시작' 또는 아무 메시지나 보낸 뒤 다시 실행하세요.")
        return 1
    if len(chats) == 1 or not args.chat_id:
        chat_id = args.chat_id or next(iter(chats))
        if len(chats) > 1 and not args.chat_id:
            print("여러 대화가 보입니다. --chat-id 로 하나를 고르세요:")
            for k, v in chats.items():
                print(f"   {k}  {v}")
            return 1
    else:
        chat_id = args.chat_id
    print(f"chat id: {chat_id} ({chats.get(chat_id, '')})")
    save_env({"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id})
    print(".env 에 저장했습니다 (git 에는 올라가지 않음). GitHub Secrets 에도 같은 값을 넣으세요.")
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    os.environ["TELEGRAM_CHAT_ID"] = chat_id
    print("테스트 전송:", Notifier().send("✅ 캠핑 빈자리 감시 봇 연결 완료"))
    return 0


def main(argv=None) -> int:
    load_env()
    p = argparse.ArgumentParser(prog="watcher")
    p.add_argument("--config", default="watch.yaml")
    p.add_argument("--state", default="state.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--dry-run", action="store_true"); r.add_argument("-v", "--verbose", action="store_true")
    r.add_argument("--loop", type=int, metavar="초", help="이 간격(초)으로 반복 조회 (미지정 시 1회)")
    r.add_argument("--max-minutes", type=int, default=330, help="--loop 사용 시 최대 실행 시간(분), 기본 330")
    r.set_defaults(fn=cmd_run)
    l = sub.add_parser("list"); l.add_argument("target_id", nargs="?"); l.set_defaults(fn=cmd_list)
    sub.add_parser("test-notify").set_defaults(fn=cmd_test_notify)
    t = sub.add_parser("setup-telegram"); t.add_argument("token"); t.add_argument("--chat-id"); t.set_defaults(fn=cmd_setup_telegram)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
