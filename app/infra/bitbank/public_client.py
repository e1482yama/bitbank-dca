from __future__ import annotations

import requests
from typing import Any, Dict

from app.core.errors import InfraError
from app.core.ports import PublicPricePort


class BitbankPublicClient(PublicPricePort):
    """
    bitbank 公開APIクライアント（最小実装）
      - base: https://public.bitbank.cc
      - 例:
         /{pair}/ticker
         /{pair}/depth
         /{pair}/candlestick/{candle_type}/{yyyymmdd}
      - pair は "btc_jpy" / "eth_jpy" 形式を想定
      - candle_type は "1min","5min","15min","30min","1hour","4hour","8hour","12hour","1day","1week","1month" のいずれか
      - yyyymmdd は JST基準の "YYYYMMDD" 文字列
    """

    def __init__(self, timeout_sec: float = 10.0, session: requests.Session | None = None) -> None:
        self.base = "https://public.bitbank.cc"
        self.timeout = timeout_sec
        self.session = session or requests.Session()

    # --- Low-level ---

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        try:
            r = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise InfraError(f"public GET failed: {url} ({e})") from e

        if r.status_code != 200:
            raise InfraError(f"public GET {url} -> {r.status_code}")

        try:
            data = r.json()
        except ValueError as e:
            raise InfraError(f"public GET json decode error: {url}") from e

        # bitbank public API は {"success": 1, "data": {...}} の形
        if not isinstance(data, dict) or int(data.get("success", 0)) != 1:
            raise InfraError(f"public GET success!=1: {url} body={data}")

        return data

    # --- PublicPricePort ---

    def ticker(self, pair: str) -> Dict[str, Any]:
        """
        GET /{pair}/ticker
        Returns:
            dict: {"success":1,"data":{...}}
        """
        return self._get(f"/{pair}/ticker")

    def depth(self, pair: str) -> Dict[str, Any]:
        """
        GET /{pair}/depth
        Returns:
            dict: {"success":1,"data":{"bids":[[price,amount],...],"asks":[...],"timestamp":...}}
        """
        return self._get(f"/{pair}/depth")

    def candlestick(self, pair: str, candle_type: str, yyyymmdd: str) -> Dict[str, Any]:
        """
        GET /{pair}/candlestick/{candle_type}/{yyyymmdd}
        Args:
            pair: "btc_jpy" など
            candle_type: "5min", "1day" 等
            yyyymmdd: "YYYYMMDD"（JST基準）
        Returns:
            dict: {"success":1,"data":{"candlestick":[{"type":candle_type,"ohlcv":[[o,h,l,c,v,ts],...]}], "timestamp":...}}
        """
        return self._get(f"/{pair}/candlestick/{candle_type}/{yyyymmdd}")