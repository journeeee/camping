from __future__ import annotations

from .base import Adapter
from .generic import GenericAdapter
from .naver import NaverAdapter
from .thankq import ThankQAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "naver": NaverAdapter,
    "thankq": ThankQAdapter,
    "generic": GenericAdapter,
}


def get_adapter(site: str) -> Adapter:
    try:
        return ADAPTERS[site]()
    except KeyError:
        raise ValueError(f"지원하지 않는 site: {site!r} (가능: {', '.join(ADAPTERS)})")
