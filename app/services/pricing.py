# app/services/pricing.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from app.core.models import Quote
from app.core.ports import PublicPricePort

JST = timezone(timedelta(hours=9))


# ---------- 内部ユーティリティ ----------

def _yyyymmdd_jst(dt: datetime | None = None) -> str:
    dt = dt.astimezone(JST) if dt else datetime.now(JST)
    return dt.strftime("%Y%m%d")


def _spread_pct(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0:
        return 0.0
    mid = (bid + ask) / 2.0
    return (ask - bid) / mid if mid > 0 else 0.0


def _parse_depth_best(depth_json) -> Tuple[float, float]:
    data = depth_json.get("data", {}) if isinstance(depth_json, dict) else {}
    bids = data.get("bids", []) or []
    asks = data.get("asks", []) or []
    best_bid = float(bids[0][0]) if bids else 0.0
    best_ask = float(asks[0][0]) if asks else 0.0
    return best_bid, best_ask


def _parse_ticker_best(ticker_json) -> Tuple[float, float, float, int]:
    data = ticker_json.get("data", {}) if isinstance(ticker_json, dict) else {}
    # bitbank の public ticker は buy/sell or best_bid/best_ask/last を持つ
    best_bid = float(data.get("buy", data.get("best_bid", data.get("last", 0))))
    best_ask = float(data.get("sell", data.get("best_ask", data.get("last", 0))))
    last = float(data.get("last", 0))
    ts = int(data.get("timestamp", 0))  # ms
    return best_bid, best_ask, last, ts


def _latest_two_closes_from_candles(candles_json) -> List[float]:
    """
    candlestick APIの戻りから終値を新しい順に2つ取り出す。
    bitbankのcandlestickは:
    data: {
      "candlestick": [
         {"type": "5min", "ohlcv": [[o,h,l,c,v,ts], ...]}
      ],
      "timestamp": ...
    }
    """
    data = candles_json.get("data", {}) if isinstance(candles_json, dict) else {}
    cl = data.get("candlestick", []) or []
    if not cl:
        return []
    ohlcv = cl[0].get("ohlcv", []) or []
    closes = [float(x[3]) for x in ohlcv if isinstance(x, (list, tuple)) and len(x) >= 4]
    # 新しい順に後ろから2つ
    return closes[-2:]


# ---------- 公開関数 ----------

def get_quote(pub: PublicPricePort, pair: str) -> Quote:
    """
    価格参照（数量計算用の quote を返す）
    優先: depth のベスト → フォールバック: ticker
    - Quote.price は原則 best_ask
    """
    best_bid = best_ask = 0.0
    ts_ms = 0

    # depth 優先
    try:
        dj = pub.depth(pair)
        best_bid, best_ask = _parse_depth_best(dj)
        if best_bid > 0 and best_ask > 0:
            sp = _spread_pct(best_bid, best_ask)
            return Quote(pair=pair, price=best_ask, best_bid=best_bid, best_ask=best_ask,
                         spread_pct=sp, ts_ms=int(dj.get("data", {}).get("timestamp", 0)) or 0)
    except Exception:
        # depth 失敗時は ticker にフォールバック
        pass

    # ticker フォールバック
    tj = pub.ticker(pair)
    best_bid, best_ask, last, ts_ms = _parse_ticker_best(tj)
    price = best_ask or last
    sp = _spread_pct(best_bid, best_ask) if (best_bid and best_ask) else 0.0
    return Quote(pair=pair, price=price, best_bid=best_bid, best_ask=best_ask,
                 spread_pct=sp, ts_ms=ts_ms or 0)


def vol5m_pct(pub: PublicPricePort, pair: str) -> float:
    """
    直近5分足のボラティリティ（絶対値）。
    定義: abs(c[-1]/c[-2] - 1)
    - 当日分で2本未満なら、前日データも参照して2本揃える
    - データ不足時は 0.0
    """
    today = _yyyymmdd_jst()
    cj = pub.candlestick(pair, "5min", today)
    closes = _latest_two_closes_from_candles(cj)

    if len(closes) < 2:
        # 前日を追加で参照
        yday = _yyyymmdd_jst(datetime.now(JST) - timedelta(days=1))
        cj2 = pub.candlestick(pair, "5min", yday)
        closes2 = _latest_two_closes_from_candles(cj2)
        closes = (closes2 + closes)[-2:]  # 古い→新しいの順で2本に揃える

    if len(closes) < 2 or closes[-2] == 0:
        return 0.0

    return abs(closes[-1] / closes[-2] - 1.0)

def change24h_pct(pub: PublicPricePort, pair: str) -> float:
    """
    24時間変化率[%] を ticker の open/last から計算する。
    candlestick への依存を避けて 404 を防ぐ。
    """
    tj = pub.ticker(pair)
    data = tj.get("data", {}) if isinstance(tj, dict) else {}
    try:
        open_p = float(data.get("open"))
        last_p = float(data.get("last"))
        if open_p > 0:
            return (last_p - open_p) / open_p * 100.0
    except Exception:
        pass
    # フォールバック（計算不可のときは 0%）
    return 0.0