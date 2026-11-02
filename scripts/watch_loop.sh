#!/usr/bin/env bash
# 맥/리눅스/라즈베리파이용 로컬 상시 감시.  사용: bash scripts/watch_loop.sh 120
cd "$(dirname "$0")/.." || exit 1
INTERVAL="${1:-120}"
export PYTHONIOENCODING=utf-8
echo "캠핑 빈자리 감시 시작 (간격 ${INTERVAL}초). 중지: Ctrl+C"
while true; do
  echo "---- $(date '+%F %T')"
  python -m watcher run
  sleep "$INTERVAL"
done
