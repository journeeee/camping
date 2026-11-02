# 캠핑 빈자리 감시 에이전트

네이버 예약 · 땡큐캠핑 등 여러 예약 허브를 5분마다 확인해서 빈자리가 생기면 텔레그램/디스코드로 알려 줍니다.
GitHub Actions 크론으로 돌아가므로 PC 를 켜 둘 필요가 없습니다.

## 지원 사이트

| site | URL 예 | 방식 |
|---|---|---|
| `naver` | `https://m.booking.naver.com/booking/3/bizes/186791` (뒤에 `/items/객실ID` 가능) | 내부 GraphQL(`bizItems`, `schedule`) 호출, 로그인 불필요 |
| `thankq` | `https://m.thankqcamping.com/resv/view.hbb?cseq=1` | 사이트 목록 AJAX(`/resv/axResCampSite.hbb`) 호출 |
| `generic` | 아무 URL | 페이지 본문을 정규식으로 검사 (전용 어댑터 없는 사이트용) |

새 허브는 `watcher/adapters/` 에 어댑터 하나 추가하고 `ADAPTERS` 에 등록하면 됩니다.

## 빠른 시작 (로컬)

```bash
pip install -r requirements.txt
python -m watcher list              # watch.yaml 의 각 target 에서 사이트/객실 목록 확인
python -m watcher run --dry-run     # 알림 없이 1회 조회
```

알림을 보내려면 환경변수를 설정합니다.

```bash
# 1) 텔레그램 앱에서 @BotFather 에게 /newbot → 토큰 발급
# 2) 새 봇과의 대화방을 열고 아무 메시지나 보내기
# 3) 아래 명령: chat id 를 자동으로 찾아 .env 에 저장하고 테스트 메시지를 보냄
python -m watcher setup-telegram 123456:ABC...

python -m watcher run     # 이후 .env 를 자동으로 읽음
```

디스코드를 쓰려면 `.env` 에 `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...` 한 줄을 넣으면 됩니다.

## 로컬 PC 에서 상시 감시 (1~2분 간격)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_loop.ps1 -IntervalSec 120
```

창을 닫으면 멈춥니다. 맥/리눅스는 `bash scripts/watch_loop.sh 120`. 알림 환경변수를 먼저 설정해야 메시지가 옵니다.

## GitHub Actions 로 상시 감시

1. 이 폴더를 GitHub 저장소로 올립니다 (private 권장).
2. 저장소 **Settings → Secrets and variables → Actions** 에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   (또는 `DISCORD_WEBHOOK_URL`) 를 추가합니다.
3. **Settings → Actions → General → Workflow permissions** 를 *Read and write* 로 둡니다
   (`state.json` 을 커밋해 중복 알림을 막기 위해 필요).
4. **Actions** 탭에서 `camping-watch` 를 한 번 수동 실행(Run workflow)해 동작을 확인합니다.

이후 `.github/workflows/watch.yml` 의 크론(`*/5 * * * *`)대로 자동 실행됩니다.

알아 둘 점
- GitHub 크론은 최소 5분 간격이며, 혼잡 시간대에는 10~30분 지연될 수 있습니다. 더 촘촘히 보려면
  같은 코드를 집 PC/라즈베리파이/저가 VPS 의 cron 이나 Windows 작업 스케줄러에서 1~2분 간격으로 돌리면 됩니다.
- 공개 저장소는 60일간 커밋이 없으면 스케줄이 자동 비활성화되는데, 상태 파일 커밋이 계속 일어나므로 보통 문제 없습니다.
- 사이트 내부 API 는 예고 없이 바뀔 수 있습니다. 조회 오류가 새로 생기면 알림으로 알려 주니 그때 어댑터를 손보면 됩니다.

## 설정 페이지 (`docs/index.html`)

YAML 을 손으로 쓰지 않아도 됩니다. [docs/index.html](docs/index.html) 을 브라우저로 열면
주소·자리 이름 필터·요일·기간을 폼으로 입력해 `watch.yaml` 을 만들어 줍니다.

- 네이버 지도에서 공유한 링크를 그대로 붙여 넣으면 됩니다 (실행 시 예약 주소로 자동 변환).
- 만든 YAML 은 복사/내려받기 하거나, GitHub 토큰(해당 저장소 Contents 쓰기 권한)을 넣으면 바로 커밋됩니다.
- 저장소 Settings → Pages 에서 `main` 브랜치의 `/docs` 폴더를 소스로 지정하면 휴대폰에서도 열 수 있습니다.
- 입력 내용과 토큰은 브라우저 localStorage 에만 저장됩니다.

## 설정 (`watch.yaml`)

```yaml
settings:
  renotify_after_minutes: 180   # 계속 비어 있는 자리를 다시 알릴 간격 (null = 최초 1회만)
  notify_errors: true

targets:
  - id: naver-sample
    site: naver
    url: https://m.booking.naver.com/booking/3/bizes/186791
    item_filter: "A동"           # 사이트/객실 이름 정규식 (선택)
    nights: 1                    # 연박이면 2, 3 … (연속 날짜가 모두 비어야 알림)
    dates: [2026-11-14]          # 특정 입실일
    date_range:                  # 기간 + 요일
      from: 2026-11-07
      to: 2026-12-31
      weekdays: [fri, sat]
```

- 네이버 URL 은 네이버 지도/플레이스에서 **예약** 버튼을 눌렀을 때 열리는 주소를 그대로 넣으면 됩니다.
  `www.booking.naver.com/booking/…` 형태여도 됩니다.
- 땡큐캠핑 URL 은 캠핑장 상세 페이지 주소(`cseq=` 포함)를 넣습니다.
- 지난 날짜는 자동으로 건너뜁니다.
- 땡큐캠핑은 아직 예약 오픈 전인 날짜도 화면에 '예약가능'으로 보이므로, 캠핑장 페이지의 예약 가능 마지막 입실일
  (`res_able_max_dt`) 이후 날짜는 빈자리로 치지 않습니다. 오픈 일정은 `python -m watcher list <id>` 첫 줄에 표시됩니다.

## 동작 방식

1. `watch.yaml` 의 target 마다 어댑터가 날짜별 예약 가능 사이트를 조회합니다.
2. `state.json` 과 비교해 **새로 생긴** 빈자리만 알립니다. 자리가 다시 차면 상태에서 지우고, 다시 비면 또 알립니다.
3. `renotify_after_minutes` 가 지나도록 계속 비어 있으면 다시 한 번 알립니다.

## 테스트

```bash
pytest -q
```
