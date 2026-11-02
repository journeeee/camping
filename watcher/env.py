"""프로젝트 폴더의 .env 파일을 읽어 환경변수로 넣는다 (외부 패키지 없이).  .env 는 git 에 올라가지 않음."""
from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path(".env")


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def save_env(values: dict[str, str], path: Path = ENV_PATH) -> None:
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    existing.update(values)
    path.write_text("".join(f"{k}={v}\n" for k, v in existing.items()), encoding="utf-8")
