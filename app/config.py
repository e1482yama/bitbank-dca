
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class Settings:
    total_jpy: int
    pairs: list[str]
    weights: list[float]
    slippage_pct: float
    spread_max_pct: float
    vol5m_max_pct: float
    dip_trigger_pct: float
    dip_multiplier: float
    low_balance_alert_jpy: int
    time_window_ms: int
    auth_mode: str
    api_key: str
    api_secret: str
    line_token: str

def load_settings() -> Settings:
    def parse_csv_str(s: str) -> list[str]:
        return [x.strip() for x in s.split(",") if x.strip()]

    def parse_csv_float(s: str) -> list[float]:
        return [float(x.strip()) for x in s.split(",") if x.strip()]

    pairs = parse_csv_str(os.getenv("PAIRS", "btc_jpy,eth_jpy"))
    weights = parse_csv_float(os.getenv("WEIGHTS", "0.7,0.3"))

    if len(pairs) != len(weights):
        raise ValueError("PAIRS と WEIGHTS の要素数が一致しません。")
    if abs(sum(weights) - 1.0) > 1e-6:
        raise ValueError("WEIGHTS の合計は 1.0 にしてください。")

    return Settings(
        total_jpy=int(os.getenv("TOTAL_JPY", "10000")),
        pairs=pairs,
        weights=weights,
        slippage_pct=float(os.getenv("SLIPPAGE_PCT", "0.008")),
        spread_max_pct=float(os.getenv("SPREAD_MAX_PCT", "0.005")),
        vol5m_max_pct=float(os.getenv("VOL5M_MAX_PCT", "0.03")),
        dip_trigger_pct=float(os.getenv("DIP_TRIGGER_PCT", "-0.03")),
        dip_multiplier=float(os.getenv("DIP_MULTIPLIER", "1.5")),
        low_balance_alert_jpy=int(os.getenv("LOW_BALANCE_ALERT_JPY", "20000")),
        time_window_ms=int(os.getenv("TIME_WINDOW_MS", "5000")),
        auth_mode=os.getenv("AUTH_MODE", "TIME_WINDOW").upper(),
        api_key=os.getenv("BITBANK_API_KEY", ""),
        api_secret=os.getenv("BITBANK_API_SECRET", ""),
        line_token=os.getenv("LINE_NOTIFY_TOKEN", ""),
    )
