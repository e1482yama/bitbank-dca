# app/config.py
from __future__ import annotations
import os
from dataclasses import dataclass

def _getenv(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if val is None and required:
        raise RuntimeError(f"環境変数 {name} が未設定です")
    return val


def _as_int(val: str | None, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except Exception:
        return default


def _as_float(val: str | None, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


@dataclass(frozen=True)
class Config:
    # bitbank
    bitbank_api_key: str
    bitbank_api_secret: str

    # LINE
    line_channel_access_token: str
    line_to_user_id: str

    # DCA 設定
    dca_total_jpy: int
    dca_ratio_btc: float
    dca_ratio_eth: float
    dca_dip_multiplier: float

    # ガード閾値
    guard_max_spread_pct: float
    guard_max_vol5m_pct: float
    guard_dip_threshold: float


def load_config() -> Config:
    return Config(
        # bitbank
        bitbank_api_key=_getenv("BITBANK_API_KEY", required=True),
        bitbank_api_secret=_getenv("BITBANK_API_SECRET", required=True),

        # LINE
        line_channel_access_token=_getenv("LINE_CHANNEL_ACCESS_TOKEN", required=True),
        line_to_user_id=_getenv("LINE_TO_USER_ID", required=True),

        # DCA
        dca_total_jpy=_as_int(_getenv("DCA_TOTAL_JPY"), 10000),
        dca_ratio_btc=_as_float(_getenv("DCA_RATIO_BTC"), 0.7),
        dca_ratio_eth=_as_float(_getenv("DCA_RATIO_ETH"), 0.3),
        dca_dip_multiplier=_as_float(_getenv("DCA_DIP_MULTIPLIER"), 1.5),

        # ガード
        guard_max_spread_pct=_as_float(_getenv("GUARD_MAX_SPREAD_PCT"), 0.004),
        guard_max_vol5m_pct=_as_float(_getenv("GUARD_MAX_VOL5M_PCT"), 0.02),
        guard_dip_threshold=_as_float(_getenv("GUARD_DIP_THRESHOLD"), 0.03),
    )
